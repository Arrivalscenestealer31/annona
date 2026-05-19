"""
Tests for the local-first / skip-login behaviour.

Coverage:
- RunnerDaemon boots without auth.
- BrainManager is fully usable offline (CRUD + FTS search).
- SyncEngine.push_pending() short-circuits with `not_authenticated` and does
  not construct any httpx client (no network call).
- /api/runner/mode endpoint reports `mode=local` and the vault path.
"""
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from runner.auth import AuthManager
from runner.brain.manager import BrainManager
from runner.sync.engine import SyncEngine, SyncError
from runner.local_api import create_app
from runner.main import RunnerDaemon


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_daemon_config(tmp_path: Path, cloud_enabled: bool = False) -> dict:
    return {
        "cloud": {
            "enabled":          cloud_enabled,
            "api_url":          "http://localhost:8080",
            "polling_interval": 5,
            "timeout":          30,
        },
        "permissions": {
            "filesystem": {"allowed_paths": [str(tmp_path)], "denied_paths": [], "max_file_size_mb": 50},
            "shell":      {"enabled": True,  "allowed_commands": []},
            "network":    {"enabled": True},
        },
        "tools":   {"enabled": []},
        "ai":      {"provider": "akaion"},
        "runner":  {"max_concurrent_tasks": 1, "capture_to_brain": False},
        "logging": {"level": "WARNING", "file": str(tmp_path / "runner.log")},
        "brain":   {"dir": str(tmp_path / "brain")},
    }


@pytest.fixture
def unauthed_auth(tmp_path, monkeypatch):
    """AuthManager pointing at an empty config dir → not authenticated."""
    monkeypatch.delenv("AKAION_API_KEY",   raising=False)
    monkeypatch.delenv("AKAION_RUNNER_ID", raising=False)
    return AuthManager(config_dir=tmp_path / ".akaion")


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_daemon_boots_without_auth(tmp_path, unauthed_auth, monkeypatch):
    """
    With cloud.enabled=False AND no credentials, the daemon must construct
    cleanly in local-only mode — no errors, no network.
    """
    monkeypatch.setattr("runner.main.AuthManager", lambda: unauthed_auth)
    cfg = _make_daemon_config(tmp_path, cloud_enabled=False)

    # Don't actually start uvicorn during construction.
    with patch("runner.main.LocalAPIServer") as fake_local_api:
        fake_local_api.return_value = MagicMock()
        daemon = RunnerDaemon(cfg, brain_dir=tmp_path / "brain", local_port=0)

    assert daemon._cloud_enabled is False
    assert daemon._cloud_authed is False

    # stop() must not blow up.
    daemon.running = True
    daemon.stop()


def test_daemon_local_when_enabled_but_unauthed(tmp_path, unauthed_auth, monkeypatch):
    """cloud.enabled=True but no credentials ⇒ daemon still local-only flags."""
    monkeypatch.setattr("runner.main.AuthManager", lambda: unauthed_auth)
    cfg = _make_daemon_config(tmp_path, cloud_enabled=True)

    with patch("runner.main.LocalAPIServer") as fake_local_api:
        fake_local_api.return_value = MagicMock()
        daemon = RunnerDaemon(cfg, brain_dir=tmp_path / "brain", local_port=0)

    assert daemon._cloud_enabled is True
    assert daemon._cloud_authed is False


def test_brain_offline_crud_and_search(tmp_path):
    """BrainManager must work fully offline."""
    brain = BrainManager(tmp_path / "brain")
    n1 = brain.create(title="Note one", content="hello world", tags=["lab"])
    n2 = brain.create(title="Pasta",    content="ricetta cacio e pepe", tags=["food"])

    assert brain.get(n1.id) is not None

    notes = brain.list()
    assert {n.id for n in notes} == {n1.id, n2.id}

    hits = brain.search("cacio")
    assert any(h.id == n2.id for h in hits)

    assert brain.delete(n1.id) is True
    assert brain.get(n1.id) is None

    brain.close()


def test_sync_push_pending_skips_when_unauthenticated(tmp_path, unauthed_auth):
    """push_pending() must NOT build an httpx client when there's no token."""
    brain = BrainManager(tmp_path / "brain")
    n = brain.create(title="todo", content="ship local-first", tags=[])
    brain.mark_pending(n.id)

    engine = SyncEngine(brain=brain, cot_url="http://localhost:9999", auth=unauthed_auth)

    # Spy on httpx.Client to make sure it's never constructed.
    with patch("runner.sync.engine.httpx.Client") as fake_client:
        result = engine.push_pending()
        fake_client.assert_not_called()

    assert result["synced"] == 0
    assert result["errors"] == 0
    assert result.get("error") == "not_authenticated"

    # push_note (singolo) stesso comportamento
    with patch("runner.sync.engine.httpx.Client") as fake_client:
        ok = engine.push_note(n.id)
        fake_client.assert_not_called()
    assert ok is False

    brain.close()


def test_sync_client_raises_sync_error_when_no_token(tmp_path, unauthed_auth):
    """_client() must raise SyncError('not_authenticated') without a token."""
    brain  = BrainManager(tmp_path / "brain")
    engine = SyncEngine(brain=brain, cot_url="http://localhost:9999", auth=unauthed_auth)

    with pytest.raises(SyncError) as ei:
        engine._client()
    assert "not_authenticated" in str(ei.value)
    brain.close()


def test_no_cloud_flag_overrides_enabled(tmp_path, unauthed_auth, monkeypatch):
    """The --no-cloud override (cloud.enabled=False) keeps the daemon local-only."""
    monkeypatch.setattr("runner.main.AuthManager", lambda: unauthed_auth)
    cfg = _make_daemon_config(tmp_path, cloud_enabled=True)
    cfg["cloud"]["enabled"] = False  # simulate --no-cloud flag

    with patch("runner.main.LocalAPIServer") as fake_local_api:
        fake_local_api.return_value = MagicMock()
        daemon = RunnerDaemon(cfg, brain_dir=tmp_path / "brain", local_port=0)

    assert daemon._cloud_enabled is False


def test_runner_mode_endpoint_reports_local(tmp_path, unauthed_auth):
    """GET /api/runner/mode → mode=local, vault_path set."""
    brain  = BrainManager(tmp_path / "brain")
    engine = SyncEngine(brain=brain, cot_url="http://localhost:9999", auth=unauthed_auth)
    app    = create_app(brain, engine, unauthed_auth, cloud_enabled=False)
    client = TestClient(app)

    r = client.get("/api/runner/mode")
    assert r.status_code == 200
    data = r.json()
    assert data["mode"]          == "local"
    assert data["cloud_enabled"] is False
    assert data["authenticated"] is False
    assert str(tmp_path / "brain") in data["vault_path"]

    # /api/auth/status must include `mode`
    r = client.get("/api/auth/status")
    assert r.status_code == 200
    assert r.json()["mode"] == "local"
    assert r.json()["authenticated"] is False

    brain.close()
