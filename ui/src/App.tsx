import { useState, useEffect, useRef } from "react";
import { useRunner } from "./hooks/useRunner";
import { BrainIcon, SyncIcon, TasksIcon, PluginsIcon, SettingsIcon } from "./components/ui/Icons";
import LogoAkaion from "./components/brand/LogoAkaion";
import BrainView    from "./components/views/BrainView";
import SyncView     from "./components/views/SyncView";
import TasksView    from "./components/views/TasksView";
import PluginsView  from "./components/views/PluginsView";
import WelcomeView, { ONBOARDING_FLAG } from "./components/views/WelcomeView";
import UpdateBanner from "./components/UpdateBanner";
import { fbAuth, gProvider, signInWithPopup } from "./lib/firebase";
import { auth as authApi, runner as runnerApi, sync as syncApi, AuthStatus, RunnerMode } from "./api/runner";
import "./App.css";
import "./css/auth-animations.css";

type View = "brain" | "sync" | "tasks" | "plugins"

const NAV: { id: View; label: string; icon: React.FC<{ size?: number }> }[] = [
  { id: "brain",   label: "Brain",   icon: BrainIcon },
  { id: "sync",    label: "Sync",    icon: SyncIcon },
  { id: "tasks",   label: "Runner",  icon: TasksIcon },
  { id: "plugins", label: "Plugin",  icon: PluginsIcon },
]

function readOnboardingDone(): boolean {
  try { return localStorage.getItem(ONBOARDING_FLAG) === "true"; } catch { return false; }
}

export default function App() {
  const { status, start } = useRunner();
  const [view, setView]               = useState<View>("brain");
  const [authStatus, setAuthStatus]   = useState<AuthStatus | null>(null);
  const [mode, setMode]               = useState<RunnerMode | null>(null);
  const [bootChecked, setBootChecked] = useState(false);
  const [showWelcome, setShowWelcome] = useState(false);
  const [cloudSyncing, setCloudSyncing] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [noteCount, setNoteCount]       = useState<number | null>(null);
  const settingsRef = useRef<HTMLDivElement | null>(null);

  // Close popover when clicking outside.
  useEffect(() => {
    if (!settingsOpen) return;
    const onClick = (e: MouseEvent) => {
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) {
        setSettingsOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [settingsOpen]);

  // Listen to BrainView count updates (statusbar info).
  useEffect(() => {
    const onCount = (e: Event) => {
      const ce = e as CustomEvent<{ count: number }>;
      if (ce?.detail && typeof ce.detail.count === "number") setNoteCount(ce.detail.count);
    };
    window.addEventListener("akaion:note-count", onCount);
    return () => window.removeEventListener("akaion:note-count", onCount);
  }, []);

  // Probe runner and decide if we need the welcome screen.
  useEffect(() => {
    if (status === "stopped") start();
  }, []); // eslint-disable-line

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const [s, m] = await Promise.all([authApi.status(), runnerApi.mode()]);
        if (cancelled) return;
        setAuthStatus(s);
        setMode(m);
        // Welcome rule: only first launch AND not yet authenticated.
        setShowWelcome(!readOnboardingDone() && !s.authenticated);
        setBootChecked(true);
      } catch {
        if (!cancelled) setTimeout(check, 1000);
      }
    };
    check();
    return () => { cancelled = true; };
  }, []);

  const handleLoginFromWelcome = (s: AuthStatus) => {
    setAuthStatus(s);
    setShowWelcome(false);
    refreshMode();
  };

  const handleSkipFromWelcome = () => {
    setShowWelcome(false);
  };

  const refreshMode = async () => {
    try { setMode(await runnerApi.mode()); } catch { /* offline */ }
  };

  const handleLogout = async () => {
    await authApi.logout();
    setAuthStatus({ authenticated: false, email: null, runner_id: null });
    refreshMode();
  };

  const handleSidebarCloudLogin = async () => {
    setCloudSyncing(true);
    try {
      const cred    = await signInWithPopup(fbAuth, gProvider);
      const token   = await cred.user.getIdToken();
      const refresh = (cred.user as any).stsTokenManager?.refreshToken ?? "";
      const s = await authApi.save({
        firebase_token: token,
        refresh_token:  refresh,
        expires_in:     3600,
        email:          cred.user.email ?? "",
      });
      setAuthStatus(s);
      try { localStorage.setItem(ONBOARDING_FLAG, "true"); } catch { /* */ }
      refreshMode();

      // Auto-push once auth lands: send every pending local note to the cloud.
      // Failure here must never roll back the login.
      try {
        const res = await syncApi.push();
        console.info(`Auto-push after login: synced=${res.synced} errors=${res.errors}`);
      } catch (syncErr) {
        console.warn("Auto-push after login failed (login still ok):", syncErr);
      }
    } catch (e: any) {
      if (e?.code !== "auth/popup-closed-by-user" && e?.code !== "auth/cancelled-popup-request") {
        // No noisy alert; logged silently — sidebar will retry on next click.
        console.warn("Cloud login failed:", e?.message ?? e);
      }
    } finally {
      setCloudSyncing(false);
    }
  };

  const handleShowWelcomeAgain = () => {
    try { localStorage.removeItem(ONBOARDING_FLAG); } catch { /* */ }
    setShowWelcome(true);
  };

  const statusLabel: Record<string, string> = {
    running: "Daemon active",
    stopped: "Runner fermo",
    starting: "Avvio…",
    error: "Runner error",
  };

  // ── Render ──────────────────────────────────────────────────────────────────
  if (showWelcome) {
    return (
      <>
        <UpdateBanner />
        <WelcomeView
          vaultPath={mode?.vault_path}
          onLogin={handleLoginFromWelcome}
          onSkip={handleSkipFromWelcome}
        />
      </>
    );
  }

  const isAuthed = !!authStatus?.authenticated;

  return (
    <div className="app-shell">
      {/* Auto-update banner (Tauri-only; web mode = no-op). Position:fixed so
          it doesn't disturb the grid layout. */}
      <UpdateBanner />
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="ak-sidebar-logo">
          <span className="ak-sidebar-logo__badge">
            <LogoAkaion variant="glow" size={24} rounded={6} />
          </span>
          <div>
            <div className="ak-sidebar-logo__name">Annona</div>
            <div className="ak-sidebar-logo__sub">{isAuthed ? "Cloud" : "Local"}</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="ak-nav-section">Workspace</div>
          {NAV.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              className={`ak-nav-item ${view === id ? "active" : ""}`}
              onClick={() => setView(id)}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}

          <div style={{ flex: 1 }} />

          {/* Cloud sync badge — visible when in local mode */}
          {!isAuthed && (
            <div className="ak-cloud-badge" role="region" aria-label="Local mode">
              <div className="ak-cloud-badge__row">
                <span className="ak-cloud-badge__dot" />
                <span style={{ fontSize: 12, fontWeight: 500 }}>Local</span>
              </div>
              <div style={{ fontSize: 11, color: "rgba(255,255,255,0.45)", lineHeight: 1.4, marginTop: -2 }}>
                Notes stay on this machine
              </div>
              <button
                className="ak-cloud-badge__cta"
                onClick={handleSidebarCloudLogin}
                disabled={cloudSyncing}
              >
                {cloudSyncing ? "Connecting…" : "Sync →"}
              </button>
            </div>
          )}

          {/* Account block — authed */}
          {isAuthed && (
            <div className="ak-cloud-badge" role="region" aria-label="Modalità cloud">
              <div className="ak-cloud-badge__row">
                <span className="ak-cloud-badge__dot ak-cloud-badge__dot--online" />
                <span style={{ fontSize: 12, fontWeight: 500 }}>Cloud sync</span>
              </div>
              {authStatus?.email && (
                <div style={{ fontSize: 11, color: "rgba(255,255,255,0.45)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginTop: -2 }}>
                  {authStatus.email}
                </div>
              )}
              <button
                className="ak-cloud-badge__cta"
                onClick={handleLogout}
                style={{ borderColor: "rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.04)" }}
              >
                Logout
              </button>
            </div>
          )}
        </nav>

        {/* Settings row (gear popover) */}
        <div className="ak-settings-row" ref={settingsRef}>
          <button
            className="ak-icon-btn"
            onClick={() => setSettingsOpen((v) => !v)}
            title="Impostazioni"
            aria-label="Impostazioni"
          >
            <SettingsIcon size={14} />
          </button>
          <span style={{ fontSize: 11, color: "rgba(255,255,255,0.4)" }}>
            v0.1.0
          </span>
          {settingsOpen && (
            <div className="ak-settings-popover" role="menu">
              <button
                className="ak-settings-item"
                onClick={() => { setSettingsOpen(false); handleShowWelcomeAgain(); }}
              >
                Mostra benvenuto
              </button>
              <button
                className="ak-settings-item ak-settings-item--sub"
                disabled
                title="Coming soon"
                style={{ cursor: "not-allowed", opacity: 0.55 }}
              >
                Open vault folder
              </button>
              <button
                className="ak-settings-item ak-settings-item--sub"
                disabled
                title="Coming soon"
                style={{ cursor: "not-allowed", opacity: 0.55 }}
              >
                About Annona
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <main className="main">
        {!bootChecked ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-sub)", fontSize: 13 }}>
            Connessione al runner…
          </div>
        ) : (
          <>
            {view === "brain"   && <BrainView />}
            {view === "sync"    && <SyncView />}
            {view === "tasks"   && <TasksView />}
            {view === "plugins" && <PluginsView />}
          </>
        )}
      </main>

      {/* Status bar */}
      <footer className="ak-statusbar">
        <div className="ak-statusbar__item">
          <span className={`status-dot ${status}`} />
          <span>{statusLabel[status] ?? status}</span>
        </div>
        <div className="ak-statusbar__sep" />
        <div className="ak-statusbar__item ak-statusbar__item--muted">
          <span>127.0.0.1:7070</span>
        </div>
        <div className="ak-statusbar__sep" />
        <div className="ak-statusbar__item">
          <span style={{ color: isAuthed ? "var(--green)" : "rgba(255,255,255,0.45)" }}>
            {isAuthed ? "● cloud" : "● local"}
          </span>
        </div>

        <div className="ak-statusbar__item ak-statusbar__item--right ak-statusbar__item--muted" title={mode?.vault_path ?? ""}>
          <span style={{ maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {mode?.vault_path ?? "~/akaion-brain"}
          </span>
        </div>
        {noteCount !== null && (
          <>
            <div className="ak-statusbar__sep" />
            <div className="ak-statusbar__item ak-statusbar__item--muted">
              <span>{noteCount} {noteCount === 1 ? "note" : "notes"}</span>
            </div>
          </>
        )}
        <div className="ak-statusbar__sep" />
        <div className="ak-statusbar__item ak-statusbar__item--muted">
          <span>Annona v0.1.0</span>
        </div>
      </footer>
    </div>
  );
}
