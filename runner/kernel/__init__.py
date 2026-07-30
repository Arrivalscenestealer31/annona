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
    PlacementHeldError,
    PolicyError,
    RunnerError,
    ToolNotFoundError,
)
from runner.kernel.ports import (
    Classifier,
    InferenceBackend,
    Ledger,
    PlacementEngine,
    PolicyGate,
    ToolExecutor,
)
from runner.kernel.types import (
    AgentResult,
    Capabilities,
    Clearance,
    Completion,
    CompletionRequest,
    GrammarSupport,
    Outcome,
    Placement,
    Requirement,
    Role,
    SensitivityClass,
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
    "PlacementHeldError",
    "PolicyError",
    "RunnerError",
    "ToolNotFoundError",
    # ports
    "Classifier",
    "InferenceBackend",
    "Ledger",
    "PlacementEngine",
    "PolicyGate",
    "ToolExecutor",
    # types
    "AgentResult",
    "Capabilities",
    "Clearance",
    "Completion",
    "CompletionRequest",
    "GrammarSupport",
    "Outcome",
    "Placement",
    "Requirement",
    "Role",
    "SensitivityClass",
    "StopReason",
    "ToolCall",
    "ToolInvocation",
    "ToolResult",
    "ToolSpec",
    "Transcript",
    "Turn",
]
