// Prevents additional console window on Windows in release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::{Arc, Mutex, OnceLock};
use std::time::Duration;

use tauri::{
    AppHandle, Manager, RunEvent, State, WebviewUrl, WebviewWindowBuilder, Emitter,
};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const SIDECAR_NAME: &str = "annona";
const HEALTH_URL: &str = "http://127.0.0.1:7070/health";
const HEALTH_RETRY_MAX: u32 = 60; // 60 * 500ms = 30s
const HEALTH_RETRY_DELAY_MS: u64 = 500;

// Shared handle to the running sidecar. We keep it both in Tauri's `State`
// (for the UI commands) and in this process-wide OnceLock so the OS signal
// handler — which runs outside the Tauri runtime — can also reach it.
type SharedSidecar = Arc<Mutex<Option<CommandChild>>>;
static SIDECAR: OnceLock<SharedSidecar> = OnceLock::new();

fn sidecar_slot() -> &'static SharedSidecar {
    SIDECAR.get_or_init(|| Arc::new(Mutex::new(None)))
}

struct SidecarState(SharedSidecar);

impl Default for SidecarState {
    fn default() -> Self {
        SidecarState(sidecar_slot().clone())
    }
}

fn kill_sidecar_now() {
    if let Ok(mut g) = sidecar_slot().lock() {
        if let Some(child) = g.take() {
            let _ = child.kill();
        }
    }
}

fn install_signal_handler() {
    // `ctrlc` covers SIGINT + SIGTERM (with the `termination` feature) on Unix,
    // and Ctrl+C / Ctrl+Break / console-close on Windows. We can only install
    // one handler per process; ignore the error if a test harness already did.
    let _ = ctrlc::set_handler(|| {
        log::warn!("termination signal received — killing sidecar before exit");
        kill_sidecar_now();
        // Mirror conventional shell exit codes: 130 for SIGINT-style termination.
        std::process::exit(130);
    });
}

#[derive(serde::Serialize)]
struct RunnerStatus {
    process_alive: bool,
    http_ok: bool,
    url: &'static str,
}

#[tauri::command]
fn start_runner() -> Result<&'static str, String> {
    // No-op: sidecar is spawned at app startup. Kept for UI symmetry.
    Ok("already-running")
}

#[tauri::command]
fn stop_runner(state: State<'_, SidecarState>) -> Result<&'static str, String> {
    let mut guard = state.0.lock().map_err(|e| e.to_string())?;
    if let Some(child) = guard.take() {
        child.kill().map_err(|e| e.to_string())?;
    }
    Ok("stopped")
}

#[tauri::command]
async fn runner_status(state: State<'_, SidecarState>) -> Result<RunnerStatus, String> {
    let process_alive = {
        let guard = state.0.lock().map_err(|e| e.to_string())?;
        guard.is_some()
    };
    let http_ok = ping_health().await;
    Ok(RunnerStatus {
        process_alive,
        http_ok,
        url: HEALTH_URL,
    })
}

async fn ping_health() -> bool {
    // Use a minimal stdlib-only TCP check to avoid pulling in a full HTTP client.
    // We try a TCP connect to 127.0.0.1:7070; the daemon binds before it accepts
    // requests, so this is enough to signal "ready".
    use std::net::ToSocketAddrs;
    let addr = match "127.0.0.1:7070".to_socket_addrs() {
        Ok(mut it) => it.next(),
        Err(_) => None,
    };
    if let Some(addr) = addr {
        tokio::task::spawn_blocking(move || {
            std::net::TcpStream::connect_timeout(&addr, Duration::from_millis(300)).is_ok()
        })
        .await
        .unwrap_or(false)
    } else {
        false
    }
}

fn spawn_sidecar(app: &AppHandle) -> Result<CommandChild, String> {
    let sidecar = app
        .shell()
        .sidecar(SIDECAR_NAME)
        .map_err(|e| format!("sidecar lookup failed: {e}"))?
        .args(["run", "--no-cloud", "--port", "7070"]);

    let (mut rx, child) = sidecar
        .spawn()
        .map_err(|e| format!("sidecar spawn failed: {e}"))?;

    let app_handle = app.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(ev) = rx.recv().await {
            match ev {
                CommandEvent::Stdout(line) => {
                    let s = String::from_utf8_lossy(&line).to_string();
                    log::info!("[sidecar] {s}");
                    let _ = app_handle.emit("runner://log", s);
                }
                CommandEvent::Stderr(line) => {
                    let s = String::from_utf8_lossy(&line).to_string();
                    log::warn!("[sidecar:err] {s}");
                    let _ = app_handle.emit("runner://err", s);
                }
                CommandEvent::Error(err) => {
                    log::error!("[sidecar:error] {err}");
                    let _ = app_handle.emit("runner://err", err);
                }
                CommandEvent::Terminated(payload) => {
                    log::warn!("[sidecar] terminated: code={:?}", payload.code);
                    let _ = app_handle.emit("runner://terminated", payload.code);
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(child)
}

fn build_main_window(app: &AppHandle, url: WebviewUrl) {
    // The configuration declares a `main` window with `visible: false`, so
    // nothing flashes on screen while the daemon is still starting. Tauri
    // creates it at launch, which means it always exists by the time we get
    // here — and this function used to see that and return, leaving a hidden
    // window pointing at nothing.
    //
    // The app has therefore never shown a window in a packaged build: daemon
    // healthy, port open, no error anywhere, and nothing on screen. Showing and
    // navigating the existing window is the whole fix.
    if let Some(window) = app.get_webview_window("main") {
        if let WebviewUrl::External(target) = &url {
            if let Err(e) = window.navigate(target.clone()) {
                log::error!("could not point the window at the daemon: {e}");
            }
        }
        if let Err(e) = window.show() {
            log::error!("could not show the window: {e}");
        }
        let _ = window.set_focus();
        log::info!("main window shown and pointed at the daemon");
        return;
    }
    let res = WebviewWindowBuilder::new(app, "main", url)
        .title("Annona")
        .inner_size(1280.0, 800.0)
        .min_inner_size(900.0, 600.0)
        .resizable(true)
        .visible(true)
        .build();
    if let Err(e) = res {
        log::error!("window build failed: {e}");
    }
}

fn show_error_window(app: &AppHandle, message: &str) {
    let html = format!(
        "<html><head><title>Annona — error</title>\
        <style>body{{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;\
        background:#0b0f14;color:#e6edf3;padding:24px;line-height:1.4}}\
        code{{background:#161b22;padding:2px 6px;border-radius:4px}}</style>\
        </head><body><h2>Annona couldn't start</h2><p>{}</p>\
        <p>Check logs at <code>~/Library/Logs/com.akaion.runner/</code> (macOS) \
        or the terminal output if launched via <code>./start.sh</code>.</p></body></html>",
        message
    );
    let data_url = format!("data:text/html;charset=utf-8,{}", urlencoding_minimal(&html));
    build_main_window(app, WebviewUrl::External(data_url.parse().unwrap_or_else(|_| {
        "about:blank".parse().unwrap()
    })));
}

// Minimal URL-encoding for data: URLs (no extra dep)
fn urlencoding_minimal(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for b in s.as_bytes() {
        match b {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                out.push(*b as char)
            }
            _ => out.push_str(&format!("%{:02X}", b)),
        }
    }
    out
}

fn main() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info"))
        .try_init()
        .ok();

    install_signal_handler();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .manage(SidecarState::default())
        .invoke_handler(tauri::generate_handler![start_runner, stop_runner, runner_status])
        .setup(|app| {
            let handle = app.handle().clone();

            // Spawn sidecar; on failure, show error window and bail out gracefully.
            match spawn_sidecar(&handle) {
                Ok(child) => {
                    if let Ok(mut g) = app.state::<SidecarState>().0.lock() {
                        *g = Some(child);
                    }
                }
                Err(e) => {
                    log::error!("sidecar spawn error: {e}");
                    show_error_window(&handle, &format!("Failed to spawn sidecar: {e}"));
                    return Ok(());
                }
            }

            // Wait for the daemon to bind :7070, then navigate the webview.
            //
            // The window is built through `run_on_main_thread`, and that is not
            // ceremony: on macOS a window may only be created on the main
            // thread, and this runs inside an async task. Built from here
            // directly the call returned Ok and produced nothing — a daemon
            // running happily, no window, no error in the log, and a user
            // reporting "I opened it and nothing happened".
            tauri::async_runtime::spawn(async move {
                for i in 0..HEALTH_RETRY_MAX {
                    if ping_health().await {
                        log::info!("daemon ready after {} attempts", i + 1);
                        let url = WebviewUrl::External(
                            HEALTH_URL.replace("/health", "").parse().unwrap(),
                        );
                        let for_window = handle.clone();
                        if let Err(e) = handle.run_on_main_thread(move || {
                            build_main_window(&for_window, url);
                        }) {
                            log::error!("could not reach the main thread to build the window: {e}");
                        }
                        return;
                    }
                    tokio::time::sleep(Duration::from_millis(HEALTH_RETRY_DELAY_MS)).await;
                }
                log::error!("daemon failed to bind :7070 within {}s", HEALTH_RETRY_MAX / 2);
                let for_error = handle.clone();
                let _ = handle.run_on_main_thread(move || {
                    show_error_window(
                        &for_error,
                        "The Annona daemon failed to start on port 7070 within 30 seconds.",
                    );
                });
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("failed to build Tauri app")
        .run(|app_handle, event| {
            if let RunEvent::ExitRequested { .. } = event {
                // Best-effort kill on exit.
                if let Some(state) = app_handle.try_state::<SidecarState>() {
                    if let Ok(mut g) = state.0.lock() {
                        if let Some(child) = g.take() {
                            let _ = child.kill();
                        }
                    }
                }
            }
        });
}
