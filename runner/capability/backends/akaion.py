"""Akaion control-plane inference backend (layer L1).

The Akaion backend proxies inference: the runner holds the transcript and calls
``/runner/agent/turn``, which invokes Claude with native tool use and returns the
next turn. Tools then execute locally.

A sovereignty note that belongs next to the code rather than only in a document:
**this backend is egress for the whole transcript.** The transcript accumulates
tool results, so a plan that reads a file sends that file's contents on the next
turn. Tools executing locally is not the same as data staying local, and
``Capabilities.is_local`` is ``False`` here for exactly that reason. Phase 1's
perimeter reads that field and gates the call; today nothing does, which is the
gap the README documents.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from runner.capability.backends.wire import decode_completion, encode_tools, encode_transcript
from runner.kernel.errors import BackendUnavailableError
from runner.kernel.types import Capabilities, Completion, CompletionRequest

__all__ = ["AkaionBackend"]


class AkaionBackend:
    """Inference through the Akaion control plane."""

    def __init__(self, client: Any, runner_id: str | None = None) -> None:
        """
        Args:
            client: A constructed ``AIBackendClient``.
            runner_id: Identity to present. Falls back to the client's own
                ``runner_id``, then to ``"unknown"``, matching prior behaviour.

        There is deliberately no ``model`` parameter. ``runner_agent_turn``
        accepts one, but the runner has never sent it: the control plane selects
        the model, and adding it here would change what is on the wire while
        claiming to change nothing. It belongs in the same conversation as
        routing, in Phase 1.
        """
        self._client = client
        self._runner_id = runner_id

    @property
    def name(self) -> str:
        return "akaion"

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(
            native_tools=True,
            grammar="none",
            parallel_tool_calls=True,
            context_window=200_000,
            is_local=False,
        )

    @property
    def runner_id(self) -> str:
        """Identity presented to the control plane.

        Resolved per call rather than cached: the runner id is assigned during
        registration, which can complete after this backend is constructed.
        """
        return self._runner_id or getattr(self._client, "runner_id", None) or "unknown"

    def complete(self, request: CompletionRequest) -> Completion:
        turn_result = self._client.runner_agent_turn(
            runner_id=self.runner_id,
            messages=encode_transcript(request.transcript),
            tools=encode_tools(request.tools),
            system_prompt=request.system,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        if not turn_result:
            # The control plane being unreachable is an expected condition on a
            # laptop, not an exception to escalate: the loop stops and returns
            # whatever it already has.
            logger.error("runner_agent_turn returned nothing — aborting loop")
            raise BackendUnavailableError("Akaion control plane returned no turn")

        return decode_completion(
            turn_result.get("content") or [],
            turn_result.get("stop_reason", "end_turn"),
        )
