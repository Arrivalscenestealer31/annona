"""
Service URL Resolver

Resolves the URL of each Akaion backend the runner talks to:

  - AKAION_API_BASE   (default: https://api.akaion.com)
  - ENVIRONMENT       (development | production, default: production)
  - Per-service override: AKAION_MAIN_URL / AKAION_AI_URL / AKAION_COT_URL

Production model (reverse-proxy single host + path prefix):
  - main → {AKAION_API_BASE}/api/service1
  - cot  → {AKAION_API_BASE}/api/service3
  - ai   → {AKAION_API_BASE}/api/service4

Development model (each backend on its own port):
  - main=8080, cot=8083, ai=8084

The runner only consumes these three backends:
  - main: auth check + identity
  - cot:  push thoughts (the Brain sync endpoint)
  - ai:   optional cloud LLM inference

Explicit per-service overrides win over the resolver.
"""
import os
from typing import Dict


_SERVICE_PATH: Dict[str, str] = {
    "main": "/api/service1",
    "cot":  "/api/service3",
    "ai":   "/api/service4",
}

_SERVICE_DEV_PORT: Dict[str, int] = {
    "main": 8080,
    "cot":  8083,
    "ai":   8084,
}

_SERVICE_OVERRIDE_ENV: Dict[str, str] = {
    "main": "AKAION_MAIN_URL",
    "cot":  "AKAION_COT_URL",
    "ai":   "AKAION_AI_URL",
}

DEFAULT_API_BASE = "https://api.akaion.com"


def _is_dev() -> bool:
    env = os.getenv("ENVIRONMENT", "production").strip().lower()
    return env in ("development", "dev", "local")


def resolve_service_url(service: str) -> str:
    """
    Returns the full URL (no trailing slash) of the requested backend.

    Args:
        service: one of main | cot | ai

    Raises:
        ValueError: if the service is not recognized.
    """
    key = service.strip().lower()
    if key not in _SERVICE_PATH:
        raise ValueError(
            f"Unknown service '{service}'. "
            f"Valid: {', '.join(_SERVICE_PATH.keys())}"
        )

    override = os.getenv(_SERVICE_OVERRIDE_ENV[key])
    if override:
        return override.rstrip("/")

    if _is_dev():
        return f"http://localhost:{_SERVICE_DEV_PORT[key]}"

    base = os.getenv("AKAION_API_BASE", DEFAULT_API_BASE).rstrip("/")
    return f"{base}{_SERVICE_PATH[key]}"
