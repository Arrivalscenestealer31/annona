"""Offline scripted inference backend (layer L1).

No network, no credentials, no model. A script of turns is played back in order,
which makes it two useful things at once:

- **A test double.** Loop behaviour — iteration budgets, parallel calls, policy
  denials, error propagation — can be tested without mocking a vendor SDK.
- **A runnable demonstration.** ``make demo`` drives a real agentic loop with
  real tool execution on a fresh checkout, so a reader can see what the runner
  does before deciding whether to trust it with credentials.

It is not a model and does not pretend to be one: it neither reads nor reasons
about the transcript. When the script runs out it says so and stops, because a
test double that improvises is a test double that hides bugs.

Phase 2 replaces this with real local inference (Ollama, llama.cpp, vLLM). The
:class:`~runner.kernel.ports.InferenceBackend` port does not change, which is
the point of having one.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from loguru import logger

from runner.kernel.errors import ConfigurationError
from runner.kernel.types import Capabilities, Completion, CompletionRequest, ToolCall

__all__ = ["EchoBackend", "script_from_config"]


class EchoBackend:
    """Plays back a fixed script of completions, one per turn."""

    def __init__(self, script: Sequence[Completion] | None = None) -> None:
        """
        Args:
            script: Completions to return, in order. An empty script means "reply
                once with the prompt echoed back", which keeps the zero-config
                case useful.
        """
        self._script: tuple[Completion, ...] = tuple(script or ())
        self._turn = 0

    @property
    def name(self) -> str:
        return "echo"

    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(
            native_tools=True,
            grammar="none",
            parallel_tool_calls=True,
            context_window=0,
            # Nothing leaves the process. This is the only backend shipped in
            # Phase 0 for which that is true.
            is_local=True,
        )

    @property
    def turns_played(self) -> int:
        """How many scripted turns have been consumed so far."""
        return self._turn

    def reset(self) -> None:
        """Rewind the script so the backend can be reused across runs."""
        self._turn = 0

    def complete(self, request: CompletionRequest) -> Completion:
        index = self._turn
        self._turn += 1

        if index < len(self._script):
            completion = self._script[index]
            logger.debug(
                f"echo backend: turn {index + 1}/{len(self._script)} "
                f"({len(completion.tool_calls)} tool call(s))"
            )
            return completion

        return Completion(
            text_parts=(self._describe_exhausted(request, index),),
            stop_reason="end_turn",
        )

    def _describe_exhausted(self, request: CompletionRequest, index: int) -> str:
        if not self._script:
            return f"[echo] {_last_text(request)}"
        return (
            f"[echo] script exhausted after {len(self._script)} turn(s); "
            f"turn {index + 1} was requested"
        )


def _last_text(request: CompletionRequest) -> str:
    """The most recent text in the transcript, for the zero-config echo reply."""
    for turn in reversed(request.transcript):
        for block in reversed(turn.blocks):
            content = getattr(block, "content", None)
            if isinstance(content, str) and content:
                return content
    return ""


def script_from_config(raw: Iterable[Any] | None) -> tuple[Completion, ...]:
    """Build a script from plain configuration data.

    Each entry is a mapping with optional ``text`` and optional ``tools``::

        ai:
          provider: echo
          echo:
            script:
              - text: "Let me look at that directory."
                tools:
                  - name: explorer
                    arguments: { operation: map, path: "~/Documents" }
              - text: "Done — the tree is above."

    A turn carrying tools continues the loop; a turn without them ends it. That
    is the same rule the real backends follow, so a script exercises the loop
    the way a model would drive it.

    Raises:
        ConfigurationError: the script is not shaped as described. Configuration
            that cannot be honoured is refused rather than half-applied.
    """
    if not raw:
        return ()

    script: list[Completion] = []

    for position, entry in enumerate(raw, start=1):
        if not isinstance(entry, Mapping):
            raise ConfigurationError(
                f"ai.echo.script[{position}] must be a mapping, got {type(entry).__name__}"
            )

        text = entry.get("text")
        if text is not None and not isinstance(text, str):
            raise ConfigurationError(f"ai.echo.script[{position}].text must be a string")

        calls = _parse_calls(entry.get("tools"), position)

        script.append(
            Completion(
                text_parts=(text,) if text else (),
                tool_calls=calls,
                stop_reason="tool_use" if calls else "end_turn",
            )
        )

    return tuple(script)


def _parse_calls(raw: Any, position: int) -> tuple[ToolCall, ...]:
    if not raw:
        return ()

    if not isinstance(raw, list | tuple):
        raise ConfigurationError(f"ai.echo.script[{position}].tools must be a list")

    calls: list[ToolCall] = []
    for offset, call in enumerate(raw, start=1):
        if not isinstance(call, Mapping) or not call.get("name"):
            raise ConfigurationError(f"ai.echo.script[{position}].tools[{offset}] needs a 'name'")

        arguments = call.get("arguments", {})
        if not isinstance(arguments, Mapping):
            raise ConfigurationError(
                f"ai.echo.script[{position}].tools[{offset}].arguments must be a mapping"
            )

        calls.append(
            ToolCall(
                id=f"echo_{position}_{offset}",
                name=str(call["name"]),
                arguments=dict(arguments),
            )
        )

    return tuple(calls)
