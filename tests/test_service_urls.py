"""
Test for runner/service_urls.resolve_service_url
"""

import pytest

from runner.service_urls import resolve_service_url

# ── env hygiene ───────────────────────────────────────────────────────────────

_ENV_KEYS = (
    "ENVIRONMENT",
    "AKAION_API_BASE",
    "AKAION_MAIN_URL",
    "AKAION_COT_URL",
    "AKAION_AI_URL",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Clear the relevant environment variables before each test."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield


# ── Production defaults ───────────────────────────────────────────────────────


def test_prod_default_cot(monkeypatch):
    """In prod default, COT → https://api.prod.akaion.com/api/service3."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert resolve_service_url("cot") == "https://api.prod.akaion.com/api/service3"


def test_prod_default_all_services(monkeypatch):
    """Prod default: il runner OSS conosce solo main/cot/ai."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    base = "https://api.prod.akaion.com"
    assert resolve_service_url("main") == f"{base}/api/service1"
    assert resolve_service_url("cot") == f"{base}/api/service3"
    assert resolve_service_url("ai") == f"{base}/api/service4"


def test_prod_custom_api_base(monkeypatch):
    """A custom AKAION_API_BASE, e.g. staging, is honoured."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AKAION_API_BASE", "https://staging.akaion.com")
    assert resolve_service_url("ai") == "https://staging.akaion.com/api/service4"


def test_prod_api_base_trailing_slash_stripped(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AKAION_API_BASE", "https://api.prod.akaion.com/")
    assert resolve_service_url("main") == "https://api.prod.akaion.com/api/service1"


# ── Per-service overrides win ─────────────────────────────────────────────────


def test_override_cot_wins(monkeypatch):
    """AKAION_COT_URL esplicito vince sul resolver."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AKAION_COT_URL", "https://foo.bar")
    assert resolve_service_url("cot") == "https://foo.bar"


def test_override_in_dev_wins_too(monkeypatch):
    """The override wins in dev mode too."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("AKAION_AI_URL", "https://my-tunnel.ngrok.io")
    assert resolve_service_url("ai") == "https://my-tunnel.ngrok.io"


def test_override_trailing_slash_stripped(monkeypatch):
    monkeypatch.setenv("AKAION_MAIN_URL", "https://foo.bar/")
    assert resolve_service_url("main") == "https://foo.bar"


# ── Development → localhost ───────────────────────────────────────────────────


def test_dev_localhost_main(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert resolve_service_url("main") == "http://localhost:8080"


def test_dev_localhost_all_services(monkeypatch):
    """Dev mode: local ports for main, cot and ai."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert resolve_service_url("main") == "http://localhost:8080"
    assert resolve_service_url("cot") == "http://localhost:8083"
    assert resolve_service_url("ai") == "http://localhost:8084"


def test_dev_aliases(monkeypatch):
    """ENVIRONMENT=dev e =local sono trattati come development."""
    monkeypatch.setenv("ENVIRONMENT", "dev")
    assert resolve_service_url("cot") == "http://localhost:8083"
    monkeypatch.setenv("ENVIRONMENT", "local")
    assert resolve_service_url("cot") == "http://localhost:8083"


# ── Errors ────────────────────────────────────────────────────────────────────


def test_unknown_service_raises():
    with pytest.raises(ValueError):
        resolve_service_url("nonexistent")
