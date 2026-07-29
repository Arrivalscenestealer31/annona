"""L0 — the runner core: value types, ports, errors.

No I/O, no provider SDKs, no dependencies on the outer layers. Everything in
here is safe to import from anywhere in the codebase, which is precisely why it
is kept small.

Layer map and the reasoning behind it:
``docs/design/sovereign-runtime.md``.
"""

from runner.kernel.errors import (
    BackendUnavailableError,
    ConfigurationError,
    PermissionDeniedError,
    RunnerError,
    ToolNotFoundError,
)
from runner.kernel.ports import InferenceBackend, PolicyGate, ToolExecutor
from runner.kernel.types import (
    AgentResult,
    Capabilities,
    Completion,
    CompletionRequest,
    GrammarSupport,
    Role,
    StopReason,
    ToolCall,
    ToolInvocation,
    ToolResult,
    ToolSpec,
    Transcript,
    Turn,
)

__all__ = [
    # errors
    "BackendUnavailableError",
    "ConfigurationError",
    "PermissionDeniedError",
    "RunnerError",
    "ToolNotFoundError",
    # ports
    "InferenceBackend",
    "PolicyGate",
    "ToolExecutor",
    # types
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
