"""
Cloud Client

HTTP clients for the Akaion backends. The runner supports one sync
direction only: local -> remote, pushing notes from the local vault.

I client esposti qui servono per:
  - verificare la salute del backend (health_check)
  - verificare il token Firebase (verify_auth)
  - optional inference through AIBackendClient (chat completion / agent turn)

Tutto ciò che riguarda polling-task / heartbeat / runner control-plane è
out of scope: the local vault never receives tasks from the cloud.
"""

from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from .service_urls import resolve_service_url


class AkaionBackendClient:
    """Base HTTP client (Bearer auth via Firebase ID token)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        runner_id: Optional[str] = None,
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.runner_id = runner_id
        self.timeout = timeout

        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Runner-ID": runner_id or "unknown",
                "Content-Type": "application/json",
            },
        )

    def verify_auth(self) -> bool:
        try:
            response = self.client.get("/api/v1/users/me")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Auth verification failed: {e}")
            return False

    def health_check(self) -> bool:
        try:
            response = self.client.get("/health")
            return response.status_code == 200
        except Exception:
            return False

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class MainBackendClient(AkaionBackendClient):
    """Main backend client (identity, health, user lookup)."""

    def __init__(
        self,
        api_key: str,
        runner_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url or resolve_service_url("main"),
            runner_id=runner_id,
            timeout=timeout,
        )


class AIBackendClient(AkaionBackendClient):
    """AI backend client — optional cloud-LLM inference."""

    def __init__(
        self,
        api_key: str,
        runner_id: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 30,
    ):
        super().__init__(
            api_key=api_key,
            base_url=base_url or resolve_service_url("ai"),
            runner_id=runner_id,
            timeout=timeout,
        )

    def runner_agent_turn(
        self,
        runner_id: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Optional[Dict[str, Any]]:
        """One turn of the agentic loop via the backend AI endpoint."""
        try:
            payload: Dict[str, Any] = {
                "runner_id": runner_id,
                "messages": messages,
                "tools": tools or [],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if system_prompt:
                payload["system_prompt"] = system_prompt
            if model:
                payload["model"] = model

            response = self.client.post(
                "/api/v1/runner/agent/turn",
                json=payload,
                headers={
                    **dict(self.client.headers),
                    "X-Runner-ID": runner_id,
                },
            )

            if response.status_code == 200:
                return response.json()
            logger.error(f"runner_agent_turn failed: {response.status_code} — {response.text}")
            return None
        except Exception as e:
            logger.error(f"runner_agent_turn error: {e}")
            return None


# Backward compatibility alias
CloudClient = MainBackendClient
