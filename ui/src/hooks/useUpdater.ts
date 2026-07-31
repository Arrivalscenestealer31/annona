import { useEffect, useState, useCallback, useRef } from "react";

// ─────────────────────────────────────────────────────────────────────────────
// Tauri auto-updater hook.
//
// In a Tauri desktop bundle: on mount, asks the updater plugin to hit the
// GitHub `latest.json` manifest (configured in tauri.conf.json). If a newer
// version is available, exposes it to the UI so a non-blocking banner can
// prompt the user. The Rust plugin verifies the bundle signature against the
// embedded public key before installing.
//
// In a browser (Vite `npm run dev`, or any non-Tauri host): no-op, no banner,
// no network call.
// ─────────────────────────────────────────────────────────────────────────────

function isTauri(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as Record<string, unknown>;
  return "__TAURI__" in w || "__TAURI_INTERNALS__" in w;
}

export type UpdateAvailable = {
  version: string;
  currentVersion: string;
  notes: string | null;
  date: string | null;
};

export type UpdaterPhase =
  | "idle"          // never checked yet
  | "checking"      // GET manifest in flight
  | "up-to-date"    // checked, no update
  | "available"     // update found, awaiting user action
  | "downloading"   // user accepted, download in progress
  | "installing"    // download done, applying
  | "check-failed"  // could not reach the manifest — never shown to the user
  | "error";        // an update the user asked for failed to install

// Tauri Update object shape we actually use. Keep a loose type so the build
// doesn't break if @tauri-apps/plugin-updater isn't installed yet (e.g. on a
// dev machine that hasn't run `npm install` after Step 7c).
type TauriUpdate = {
  version: string;
  currentVersion: string;
  body?: string | null;
  date?: string | null;
  downloadAndInstall: (
    onEvent?: (e: { event: string; data?: { contentLength?: number; chunkLength?: number } }) => void,
  ) => Promise<void>;
};

export interface UseUpdaterResult {
  phase: UpdaterPhase;
  available: UpdateAvailable | null;
  /** % 0..100 during downloading, otherwise null. */
  progress: number | null;
  error: string | null;
  /** User-dismissed the banner for this session. Resets on next launch. */
  dismissed: boolean;
  dismiss: () => void;
  installAndRestart: () => Promise<void>;
  /** Manual re-check (e.g. from a menu item). */
  recheck: () => Promise<void>;
}

const CHECK_TIMEOUT_MS = 10_000;

function withTimeout<T>(p: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms);
    p.then(
      (v) => { clearTimeout(t); resolve(v); },
      (e) => { clearTimeout(t); reject(e); },
    );
  });
}

export function useUpdater(): UseUpdaterResult {
  const [phase, setPhase]         = useState<UpdaterPhase>("idle");
  const [available, setAvailable] = useState<UpdateAvailable | null>(null);
  const [progress, setProgress]   = useState<number | null>(null);
  const [error, setError]         = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  // Keep the actual Tauri Update object out of React state — it's not
  // serializable and triggering renders on it serves no purpose.
  const pendingRef = useRef<TauriUpdate | null>(null);

  const doCheck = useCallback(async () => {
    if (!isTauri()) return; // web mode: silently skip
    setPhase("checking");
    setError(null);
    try {
      const mod = await import("@tauri-apps/plugin-updater");
      const update = (await withTimeout(mod.check(), CHECK_TIMEOUT_MS, "updater check")) as TauriUpdate | null;
      // Tauri 2 returns null when no update is available.
      if (!update) {
        pendingRef.current = null;
        setAvailable(null);
        setPhase("up-to-date");
        return;
      }
      pendingRef.current = update;
      setAvailable({
        version:        update.version,
        currentVersion: update.currentVersion,
        notes:          update.body ?? null,
        date:           update.date ?? null,
      });
      setPhase("available");
    } catch (e: unknown) {
      // A check that fails is not the user's problem: they are offline, GitHub
      // is rate-limiting, or — as during the beta — no manifest is published
      // yet. The app works exactly as well either way, so this stays in the
      // console. Only an update the user *asked* for reaches the screen.
      console.warn("[updater] check failed:", e);
      setError(e instanceof Error ? e.message : String(e));
      setPhase("check-failed");
    }
  }, []);

  // Check once on mount in Tauri mode. No retries — we'll try again next launch.
  useEffect(() => {
    void doCheck();
  }, [doCheck]);

  const dismiss = useCallback(() => {
    setDismissed(true);
  }, []);

  const installAndRestart = useCallback(async () => {
    if (!isTauri()) return;
    const update = pendingRef.current;
    if (!update) {
      setError("No pending update to install");
      setPhase("error");
      return;
    }
    setPhase("downloading");
    setProgress(0);
    setError(null);

    let total = 0;
    let downloaded = 0;
    try {
      await update.downloadAndInstall((evt) => {
        switch (evt.event) {
          case "Started":
            total = evt.data?.contentLength ?? 0;
            downloaded = 0;
            setProgress(total > 0 ? 0 : null);
            break;
          case "Progress":
            downloaded += evt.data?.chunkLength ?? 0;
            if (total > 0) setProgress(Math.min(100, Math.round((downloaded / total) * 100)));
            break;
          case "Finished":
            setProgress(100);
            setPhase("installing");
            break;
        }
      });

      // downloadAndInstall returns after the new binary has been written.
      // We still need to relaunch the app to swap in the new version.
      const proc = await import("@tauri-apps/plugin-process");
      await proc.relaunch();
    } catch (e: unknown) {
      console.error("[updater] install failed:", e);
      setError(e instanceof Error ? e.message : String(e));
      setPhase("error");
      setProgress(null);
    }
  }, []);

  return {
    phase,
    available,
    progress,
    error,
    dismissed,
    dismiss,
    installAndRestart,
    recheck: doCheck,
  };
}
