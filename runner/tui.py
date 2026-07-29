"""
Akaion Runner — Interactive Dashboard

TUI interattiva costruita con Textual.
Layout:
  ┌────────────────── Header ──────────────────┐
  │ sidebar (status + backends) │  logs live   │
  └────────────────── Footer ──────────────────┘
"""

from __future__ import annotations

from datetime import datetime

import httpx
from dotenv import load_dotenv
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Label, RichLog, Static

from .service_urls import resolve_service_url

load_dotenv()


# ─────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────

CSS = """
Screen {
    background: #06090f;
}

Header {
    background: #0b1422;
    color: #00d9ff;
    text-style: bold;
}

Footer {
    background: #0b1422;
    color: #334155;
}

/* ── Layout ── */
#layout {
    layout: horizontal;
    height: 1fr;
}

#sidebar {
    width: 34;
    height: 100%;
    layout: vertical;
    padding: 1 1;
    border-right: solid #1e3a5f;
}

#main-area {
    height: 100%;
    layout: vertical;
    padding: 0 1;
}

/* ── Info card ── */
InfoCard {
    height: auto;
    padding: 1 2;
    border: round #1e3a5f;
    background: #0b1422;
    margin-bottom: 1;
}

InfoCard .card-title {
    color: #334155;
    text-style: bold;
    margin-bottom: 1;
}

InfoCard .card-row {
    color: #94a3b8;
}

InfoCard .card-row .key {
    color: #00d9ff;
}

/* ── Backends card ── */
BackendsCard {
    height: auto;
    padding: 1 2;
    border: round #1e3a5f;
    background: #0b1422;
}

BackendsCard .card-title {
    color: #334155;
    text-style: bold;
    margin-bottom: 1;
}

/* ── Logs ── */
#log-title {
    color: #334155;
    padding: 0 1;
    height: 1;
}

RichLog {
    height: 1fr;
    border: round #1e3a5f;
    background: #06090f;
    padding: 0 1;
    scrollbar-color: #1e3a5f;
    scrollbar-background: #06090f;
}

/* ── Controls ── */
#controls {
    height: auto;
    layout: horizontal;
    padding: 1 0 0 0;
}

#controls Button {
    margin-right: 1;
}

Button {
    min-width: 14;
    background: #0b1422;
    color: #94a3b8;
    border: solid #1e3a5f;
}

Button:hover {
    background: #1e3a5f;
    color: #e2e8f0;
}

Button.primary {
    background: #0e3a6e;
    color: #00d9ff;
    border: solid #1e6abf;
}

Button.danger {
    background: #3a0e0e;
    color: #f87171;
    border: solid #7f1d1d;
}
"""


# ─────────────────────────────────────────────────────────────
# Widgets
# ─────────────────────────────────────────────────────────────


class InfoCard(Static):
    """Card con informazioni runner."""

    def __init__(self, email: str, runner_id: str, **kwargs):
        super().__init__(**kwargs)
        self._email = email
        self._runner_id = runner_id
        self._started_at = datetime.now()

    def compose(self) -> ComposeResult:
        yield Label("RUNNER", classes="card-title")
        short_id = (self._runner_id[:20] + "…") if len(self._runner_id) > 20 else self._runner_id
        yield Label(f"[bold #00d9ff]id    [/] {short_id}", classes="card-row", id="info-id")
        yield Label(f"[bold #00d9ff]email [/] {self._email}", classes="card-row", id="info-email")
        yield Label(
            "[bold #00d9ff]status[/] [green]● running[/]", classes="card-row", id="info-status"
        )
        yield Label("[bold #00d9ff]uptime[/] 00:00:00", classes="card-row", id="info-uptime")

    def tick(self):
        delta = datetime.now() - self._started_at
        h, r = divmod(int(delta.total_seconds()), 3600)
        m, s = divmod(r, 60)
        try:
            self.query_one("#info-uptime", Label).update(
                f"[bold #00d9ff]uptime[/] {h:02d}:{m:02d}:{s:02d}"
            )
        except Exception:
            pass

    def set_status(self, running: bool):
        color, text = ("green", "● running") if running else ("red", "● stopped")
        try:
            self.query_one("#info-status", Label).update(
                f"[bold #00d9ff]status[/] [{color}]{text}[/]"
            )
        except Exception:
            pass


class BackendsCard(Static):
    """Card con stato dei 4 backend."""

    # Mappa logica → (label, service-key per resolve_service_url)
    BACKENDS: dict[str, tuple[str, str]] = {
        "main": ("Main", "main"),
        "ai": ("AI", "ai"),
        "calendar": ("Calendar", "calendar"),
        "cot": ("CoT", "cot"),
    }

    def compose(self) -> ComposeResult:
        yield Label("BACKENDS", classes="card-title")
        for key, (name, _) in self.BACKENDS.items():
            yield Label(f"[#334155]◌[/] {name}", id=f"be-{key}")

    def set_status(self, key: str, ok: bool | None):
        name = self.BACKENDS[key][0]
        if ok is None:
            icon, color = "◌", "#334155"
        elif ok:
            icon, color = "●", "green"
        else:
            icon, color = "●", "red"
        try:
            self.query_one(f"#be-{key}", Label).update(f"[{color}]{icon}[/] {name}")
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────


class AkaionDashboard(App):
    """Dashboard interattiva Akaion Runner."""

    CSS = CSS
    TITLE = "Akaion Runner"
    BINDINGS = [
        Binding("r", "refresh", "Refresh", show=True),
        Binding("c", "clear_logs", "Clear logs", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, email: str, runner_id: str, token: str):
        super().__init__()
        self._email = email
        self._runner_id = runner_id
        self._token = token

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="layout"):
            with Vertical(id="sidebar"):
                yield InfoCard(self._email, self._runner_id, id="info-card")
                yield BackendsCard(id="backends-card")
            with Vertical(id="main-area"):
                yield Label("  LOGS", id="log-title")
                yield RichLog(id="logs", auto_scroll=True, markup=True, highlight=True)
                with Horizontal(id="controls"):
                    yield Button("⟳  Refresh", id="btn-refresh", classes="primary")
                    yield Button("✕  Clear logs", id="btn-clear")
                    yield Button("✕  Quit", id="btn-quit", classes="danger")
        yield Footer()

    def on_mount(self):
        self.sub_title = self._email
        log = self.query_one(RichLog)
        ts = datetime.now().strftime("%H:%M:%S")
        log.write(f"[#334155]{ts}[/]  Akaion Runner started")
        log.write(f"[#334155]{ts}[/]  Runner ID: [#00d9ff]{self._runner_id}[/]")
        log.write(f"[#334155]{ts}[/]  Checking backends...")
        self.set_interval(1, self._tick)
        self.set_interval(30, self.check_backends)
        self.check_backends()

    def _tick(self):
        self.query_one(InfoCard).tick()

    # ── Actions ─────────────────────────

    def action_refresh(self):
        self.check_backends()

    def action_clear_logs(self):
        self.query_one(RichLog).clear()

    def action_quit(self):
        self.exit()

    # ── Button events ────────────────────

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-refresh":
            self.check_backends()
        elif event.button.id == "btn-clear":
            self.query_one(RichLog).clear()
        elif event.button.id == "btn-quit":
            self.exit()

    # ── Backend health check (background thread) ─────────

    @work(thread=True)
    def check_backends(self):
        bc: BackendsCard = self.query_one(BackendsCard)
        log: RichLog = self.query_one(RichLog)
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}

        for key, (name, service_key) in BackendsCard.BACKENDS.items():
            try:
                url = resolve_service_url(service_key)
            except Exception:
                url = ""
            ts = datetime.now().strftime("%H:%M:%S")
            if not url:
                self.call_from_thread(bc.set_status, key, None)
                continue
            ok = False
            status_code = 0
            try:
                resp = httpx.get(f"{url}/health", headers=headers, timeout=5)
                status_code = resp.status_code
                ok = status_code < 500
            except Exception:
                ok = False
            self.call_from_thread(bc.set_status, key, ok)
            color = "green" if ok else "red"
            icon = "✓" if ok else "✗"
            suffix = f" [#334155]({status_code})[/]" if ok else "  [red]unreachable[/]"
            self.call_from_thread(
                log.write, f"[#334155]{ts}[/]  [{color}]{icon}[/] {name} backend{suffix}"
            )


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────


def run_dashboard(email: str, runner_id: str, token: str):
    AkaionDashboard(email=email, runner_id=runner_id, token=token).run()
