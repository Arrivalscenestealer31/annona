"""Canonical value types for the runner core (layer L0).

Everything here is immutable and free of I/O. These types are the vocabulary
that the agent loop (L3) and the inference adapters (L1) both speak, so that
neither has to know anything about the other.

The message vocabulary itself is *not* redefined here: a transcript is a
sequence of :class:`datapizza.type.Block` values. Adopting that vocabulary
rather than inventing a parallel one is the point of
``docs/adr/0001-adopt-datapizza-ai.md`` — provider translation already lives in
datapizza's clients, and duplicating it would mean maintaining two dialects.

Legacy interoperability: :meth:`AgentResult.to_dict` and
:meth:`ToolInvocation.to_dict` emit the exact dictionary shape that
``AIClient.reason_and_execute`` has always returned. Callers and the existing
test suite are unaffected by the refactor.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from datapizza.type import Block

__all__ = [
    "AgentResult",
    "Capabilities",
    "Completion",
    "CompletionRequest",
    "GrammarSupport",
    "Role",
    "StopReason",
    "ToolCall",
    "ToolInvocation",
    "ToolResult",
    "ToolSpec",
    "Transcript",
    "Turn",
]

# ── Primitive vocabulary ──────────────────────────────────────────────────────

Role = Literal["user", "assistant", "system", "tool"]

StopReason = Literal["end_turn", "tool_use", "max_tokens", "error"]

GrammarSupport = Literal["none", "json_schema", "gbnf", "guided"]
"""How strongly a backend can constrain its own output.

``none``
    Free text only. Tool calls have to be parsed hopefully (tier 3).
``json_schema``
    Output can be shaped, but not provably constrained (e.g. Ollama ``format``).
``gbnf`` / ``guided``
    Generation can be constrained by a compiled grammar, which makes a
    malformed tool call structurally impossible (tier 2).

Only relevant from Phase 2 onward; declared now so backends can be honest about
themselves from the start.
"""


# ── Tools ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A tool as advertised to a model: a name, a description, a JSON Schema."""

    name: str
    description: str
    schema: Mapping[str, Any]

    @property
    def properties(self) -> Mapping[str, Any]:
        """The schema's ``properties`` object, or an empty mapping."""
        props = self.schema.get("properties", {})
        return props if isinstance(props, Mapping) else {}

    @property
    def required(self) -> Sequence[str]:
        """The schema's ``required`` list, or an empty sequence."""
        req = self.schema.get("required", [])
        return list(req) if isinstance(req, list | tuple) else []


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A model's request to run a tool.

    ``id`` is the provider's correlation identifier. It is echoed back with the
    result so multi-call turns can be matched up.
    """

    id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The outcome of a single tool call, successful or not."""

    call_id: str
    name: str
    content: Any
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    """A tool call paired with its outcome, as recorded in the run log."""

    tool: str
    input: Mapping[str, Any]
    result: Any
    error: bool

    def to_dict(self) -> dict[str, Any]:
        """Legacy dictionary shape consumed by the executor and the local API."""
        return {
            "tool": self.tool,
            "input": dict(self.input),
            "result": self.result,
            "error": self.error,
        }


# ── Conversation ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Turn:
    """One conversational turn: a role and the blocks it contributed."""

    role: Role
    blocks: tuple[Block, ...]


Transcript = tuple[Turn, ...]
"""The full conversation so far, provider-neutral.

Each L1 adapter encodes this into its own wire format. Keeping the canonical
form here — rather than retaining provider response objects and replaying them —
means a transcript can be serialised, inspected, hashed and replayed, which is
what Phase 3's tamper-evident trace needs.
"""


# ── Inference ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Capabilities:
    """What a backend can actually do.

    Probed rather than hardcoded: a static matrix of model capabilities is wrong
    within a month.

    ``is_local`` is the field the perimeter reads to decide whether calling this
    backend constitutes egress. It is declared once, by the adapter that knows,
    instead of being inferred at each call site — which is what makes the
    single-chokepoint property of Phase 1 statable at all.
    """

    native_tools: bool = False
    grammar: GrammarSupport = "none"
    parallel_tool_calls: bool = False
    context_window: int = 0
    is_local: bool = False


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    """Everything a backend needs for one turn of inference."""

    system: str
    transcript: Transcript
    tools: tuple[ToolSpec, ...] = ()
    temperature: float = 0.7
    max_tokens: int = 4096
    model: str | None = None


@dataclass(frozen=True, slots=True)
class Completion:
    """The result of one turn of inference, normalised across providers."""

    text_parts: tuple[str, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    stop_reason: StopReason = "end_turn"

    @property
    def text(self) -> str:
        """All text blocks of this turn, joined.

        Joining rather than keeping only the last block matters when a model
        interleaves commentary with tool calls: the earlier fragments are part
        of the answer, not noise.
        """
        return " ".join(self.text_parts)

    @property
    def wants_tools(self) -> bool:
        """Whether the loop should execute tools and continue."""
        return self.stop_reason == "tool_use" and bool(self.tool_calls)


# ── Run result ────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AgentResult:
    """The outcome of a complete agentic run."""

    response: str
    iterations: int
    tool_calls: tuple[ToolInvocation, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Legacy dictionary shape returned by ``AIClient.reason_and_execute``."""
        return {
            "response": self.response,
            "iterations": self.iterations,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
        }
