"""Ports: the interfaces the core depends on (layer L0).

This is a ports-and-adapters boundary. The agent loop depends on the protocols
declared here and on nothing else; concrete inference backends, tool registries
and policy engines are adapters that satisfy them and are injected by the
composition root.

Two consequences worth stating, because they are the reason the indirection
exists rather than decoration:

1. The loop cannot import a provider SDK. That is asserted mechanically in
   ``.importlinter``, so "the loop is provider-agnostic" is a checked fact.
2. Phase 1 can insert the perimeter between the loop and a backend by supplying
   a different :class:`InferenceBackend` — one that classifies and gates before
   delegating — without either side changing. The seam already exists.

Protocols are structural: an adapter satisfies one by shape, with no base class
to inherit and no registration step.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from runner.kernel.types import (
    Capabilities,
    Completion,
    CompletionRequest,
    ToolCall,
    ToolResult,
    ToolSpec,
)

__all__ = ["InferenceBackend", "PolicyGate", "ToolExecutor"]


@runtime_checkable
class InferenceBackend(Protocol):
    """A single turn of model inference, normalised.

    Implementations own their wire format and nothing else: they translate a
    :class:`~runner.kernel.types.CompletionRequest` into a provider call and the
    provider's answer back into a :class:`~runner.kernel.types.Completion`. They
    hold no conversation state and make no control-flow decisions — the loop
    decides whether to continue, and the perimeter decides whether it may.
    """

    @property
    def name(self) -> str:
        """Stable identifier used in logs, traces and configuration."""
        ...

    @property
    def capabilities(self) -> Capabilities:
        """What this backend can do, including whether it is local."""
        ...

    def complete(self, request: CompletionRequest) -> Completion:
        """Perform one turn of inference.

        Raises:
            runner.kernel.errors.BackendUnavailableError: the backend could not
                be reached or returned nothing usable. The loop treats this as
                "stop and report what you have", never as a crash.
        """
        ...


@runtime_checkable
class ToolExecutor(Protocol):
    """Advertises tools and runs them.

    Implementations are expected to be *total*: :meth:`invoke` returns a
    :class:`~runner.kernel.types.ToolResult` for every input, including for
    unknown tools and for tools that raise. A model must always receive an
    answer it can reason about — an unhandled exception would end the run and
    tell the model nothing.
    """

    def specs(self) -> tuple[ToolSpec, ...]:
        """The tools to advertise to the model this turn."""
        ...

    def invoke(self, call: ToolCall) -> ToolResult:
        """Run one tool call and capture its outcome, error included."""
        ...


@runtime_checkable
class PolicyGate(Protocol):
    """Decides whether a tool call may proceed.

    In Phase 0 this wraps the existing permission manager, which is
    allow-by-default (see the gap table in the README). Phase 1 replaces the
    adapter with a default-deny capability kernel; the port does not change,
    which is the point of declaring it now.
    """

    def permits(self, call: ToolCall) -> bool:
        """Return ``True`` if the call is allowed to run."""
        ...
