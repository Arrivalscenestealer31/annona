"""Ollama inference backend — local models with native tool calling (layer L1).

The first backend where `Capabilities.is_local` is `True` *and* a real model is
doing the work. Everything stays on the machine: no credentials, no egress, no
account.

Ollama's `/api/chat` speaks its own dialect rather than Anthropic's, so this
adapter carries its own encoder instead of sharing `wire.py`:

- the system prompt is a message with `role: "system"`, not a separate field;
- tools are OpenAI-shaped — `{"type": "function", "function": {...}}`;
- tool results come back as `role: "tool"` messages, one per call;
- there is no `stop_reason`: the presence of `tool_calls` is the signal.

**Tier 1 of three.** This uses the model's native tool calling, which works well
on models trained for it and produces confidently malformed arguments on models
that are not. Observed on an M1 Pro with `qwen2.5:3b`: the right tool, the right
path, and a missing required field. Tier 2 — compiling each tool's JSON Schema
into a grammar so a malformed call is structurally impossible — is what makes
small models dependable, and is the next piece of work.

Until then, a missing required argument surfaces as a tool error the model can
read and retry from, which is the loop working as designed rather than a crash.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx
from loguru import logger

from runner.kernel.blocks import ToolResultBlock
from runner.kernel.errors import BackendUnavailableError
from runner.kernel.types import (
    Capabilities,
    Completion,
    CompletionRequest,
    ToolCall,
    ToolSpec,
    Transcript,
)

__all__ = ["DEFAULT_ENDPOINT", "OllamaBackend"]

DEFAULT_ENDPOINT = "http://localhost:11434"

# Local models are slower than an API and the first call pays for loading the
# weights. A minute is patient enough for a 14B on a laptop and short enough that
# a wedged server does not hang a run forever.
DEFAULT_TIMEOUT = 120.0


class OllamaBackend:
    """Inference through a local Ollama server."""

    def __init__(
        self,
        model: str,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = DEFAULT_TIMEOUT,
        client: Any = None,
        context_window: int = 32_768,
    ) -> None:
        """
        Args:
            model: An Ollama model tag, e.g. ``qwen2.5:3b``.
            endpoint: Where the Ollama server listens.
            timeout: Seconds to wait for one completion.
            client: An injected HTTP client, for tests.
            context_window: Declared context size; informational in Phase 2.
        """
        self._model = model
        self._endpoint = endpoint.rstrip("/")
        self._timeout = timeout
        self._client = client
        self._context_window = context_window

    @property
    def name(self) -> str:
        return f"ollama:{self._model}"

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(
            native_tools=True,
            # Ollama can shape output with `format`, but cannot yet constrain it
            # with a compiled grammar. Declared honestly: over-claiming here would
            # make the perimeter trust a guarantee that does not exist.
            grammar="json_schema",
            parallel_tool_calls=True,
            context_window=self._context_window,
            # The whole point.
            is_local=True,
        )

    def complete(self, request: CompletionRequest) -> Completion:
        payload = {
            "model": request.model or self._model,
            "stream": False,
            "messages": _encode_transcript(request.system, request.transcript),
            "options": {"temperature": request.temperature},
        }

        tools = _encode_tools(request.tools)
        if tools:
            payload["tools"] = tools

        try:
            response = self._http().post(f"{self._endpoint}/api/chat", json=payload)
        except httpx.HTTPError as exc:
            # A local server that is not running is the common case, not an
            # exceptional one: someone forgot `ollama serve`. Report it as
            # unavailable so the loop stops cleanly with a readable message.
            raise BackendUnavailableError(
                f"Ollama at {self._endpoint} is unreachable: {exc}"
            ) from exc

        if response.status_code == 404:
            raise BackendUnavailableError(
                f"Ollama has no model {payload['model']!r}. Pull it with: "
                f"ollama pull {payload['model']}"
            )
        if response.status_code >= 400:
            raise BackendUnavailableError(
                f"Ollama returned {response.status_code}: {response.text[:200]}"
            )

        return _decode(response.json())

    def _http(self) -> Any:
        return self._client or httpx.Client(timeout=self._timeout)


# ── Wire format ───────────────────────────────────────────────────────────────


def _encode_tools(specs: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    """Encode tool specs in the OpenAI function shape Ollama expects."""
    return [
        {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": dict(spec.schema),
            },
        }
        for spec in specs
    ]


def _encode_transcript(system: str, transcript: Transcript) -> list[dict[str, Any]]:
    """Encode a transcript as an Ollama message array.

    Tool results become individual ``role: "tool"`` messages rather than blocks
    inside a user turn, which is what Ollama's chat format expects.
    """
    messages: list[dict[str, Any]] = []
    if system:
        messages.append({"role": "system", "content": system})

    for turn in transcript:
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []

        for block in turn.blocks:
            kind = getattr(block, "type", "")

            if kind == "text":
                text_parts.append(block.content)
            elif kind == "function":
                tool_calls.append(
                    {
                        "function": {
                            "name": block.name,
                            "arguments": dict(block.arguments),
                        }
                    }
                )
            elif kind == "function_call_result":
                results.append(
                    {
                        "role": "tool",
                        "content": _describe_result(block),
                    }
                )

        if text_parts or tool_calls:
            message: dict[str, Any] = {"role": turn.role, "content": " ".join(text_parts)}
            if tool_calls:
                message["tool_calls"] = tool_calls
            messages.append(message)

        messages.extend(results)

    return messages


def _describe_result(block: Any) -> str:
    """Render a tool result for the model, flagging failures in words.

    Ollama has no `is_error` field, so a failure has to be legible in the text —
    otherwise a small model reads an error payload as data and carries on
    cheerfully.
    """
    body = getattr(block, "result", "")
    if isinstance(block, ToolResultBlock) and block.is_error:
        return f"ERROR: {body}"
    return str(body)


def _decode(payload: dict[str, Any]) -> Completion:
    """Decode an Ollama chat response."""
    message = payload.get("message") or {}
    text = message.get("content") or ""

    calls: list[ToolCall] = []
    for index, raw in enumerate(message.get("tool_calls") or []):
        function = raw.get("function") or {}
        arguments = function.get("arguments")
        calls.append(
            ToolCall(
                # Recent Ollama emits an id; older builds do not. Synthesising a
                # stable one keeps results matchable either way.
                id=str(raw.get("id") or f"ollama_{index}"),
                name=str(function.get("name") or ""),
                arguments=arguments if isinstance(arguments, dict) else {},
            )
        )

    if calls:
        logger.debug(f"ollama: {len(calls)} tool call(s): {[c.name for c in calls]}")

    return Completion(
        text_parts=(text,) if text else (),
        tool_calls=tuple(calls),
        # Ollama has no stop reason: tool calls mean continue, their absence ends
        # the turn. That is the same rule the other backends normalise to.
        stop_reason="tool_use" if calls else "end_turn",
    )
