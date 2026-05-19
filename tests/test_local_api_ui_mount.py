"""
Tests for the static UI mount in runner/local_api.py.

Covers:
- /api/* routes are NOT shadowed by the static mount.
- GET / serves index.html when ui/dist exists.
- App startup does not error when ui/dist is missing.
"""
from pathlib import Path

from fastapi.testclient import TestClient

from runner.brain.manager import BrainManager
from runner.sync.engine import SyncEngine
from runner.auth import AuthManager
from runner import local_api as local_api_module
from runner.local_api import create_app


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_app(tmp_path: Path, ui_dist: Path | None):
    """
    Costruisce un'app FastAPI con BrainManager/SyncEngine reali (su tmp_path)
    e patcha _UI_DIST per puntare a `ui_dist` (None = path inesistente).
    """
    brain_dir = tmp_path / "brain"
    brain_dir.mkdir()
    brain = BrainManager(brain_dir)

    auth = AuthManager(config_dir=tmp_path / ".akaion")
    sync = SyncEngine(brain=brain, cot_url="http://localhost:9999", auth=auth)

    # Patch UI dist path in the module BEFORE create_app
    original_dist = local_api_module._UI_DIST
    local_api_module._UI_DIST = ui_dist if ui_dist is not None else (tmp_path / "nonexistent_dist")

    try:
        app = create_app(brain, sync, auth)
    finally:
        local_api_module._UI_DIST = original_dist

    return app


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_app_startup_without_ui_dist(tmp_path):
    """If ui/dist doesn't exist, app must still start and serve /api/*."""
    app = _build_app(tmp_path, ui_dist=None)
    client = TestClient(app)

    # /health works
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # GET / returns 404 (no static mount when dist missing)
    r = client.get("/")
    assert r.status_code == 404


def test_static_mount_serves_index(tmp_path):
    """When ui/dist/index.html exists, GET / returns it as text/html."""
    fake_dist = tmp_path / "ui_dist"
    fake_dist.mkdir()
    (fake_dist / "index.html").write_text(
        "<!doctype html><html><body><div id='root'>akaion-ui</div></body></html>",
        encoding="utf-8",
    )
    (fake_dist / "assets").mkdir()
    (fake_dist / "assets" / "app.js").write_text("console.log('akaion');", encoding="utf-8")

    app = _build_app(tmp_path, ui_dist=fake_dist)
    client = TestClient(app)

    # GET / serves the index
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "akaion-ui" in r.text

    # Asset is served too
    r = client.get("/assets/app.js")
    assert r.status_code == 200
    assert "akaion" in r.text


def test_static_mount_does_not_shadow_api(tmp_path):
    """The static mount at / must NOT intercept /api/* routes."""
    fake_dist = tmp_path / "ui_dist"
    fake_dist.mkdir()
    (fake_dist / "index.html").write_text(
        "<!doctype html><html><body>SHOULD-NOT-LEAK</body></html>",
        encoding="utf-8",
    )

    app = _build_app(tmp_path, ui_dist=fake_dist)
    client = TestClient(app)

    # /api/brain/notes still returns JSON (not the HTML)
    r = client.get("/api/brain/notes")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "SHOULD-NOT-LEAK" not in r.text

    # /health still works
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "akaion-local"
