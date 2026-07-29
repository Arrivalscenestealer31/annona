"""Error taxonomy for the runner core.

One base class so a caller can catch everything from this package, and narrow
subclasses so a caller can catch precisely what it knows how to handle.

The distinction that matters here is between *recoverable* and *fatal*:

- ``BackendUnavailableError`` is recoverable. The agent loop stops early and
  returns whatever it has, which is how the runner behaves when a remote
  backend is unreachable — a laptop that lost Wi-Fi mid-task should return a
  partial answer, not a stack trace.
- ``ConfigurationError`` is fatal. A misconfigured perimeter must never
  degrade into a working-but-unsafe one (invariant I7, fail closed).
"""

from __future__ import annotations


class RunnerError(Exception):
    """Base class for every error raised by the runner core."""


class ConfigurationError(RunnerError):
    """The runner is configured in a way that cannot be honoured.

    Fatal by design: we would rather refuse to start than run with a policy or
    a backend that does not mean what the operator thinks it means.
    """


class BackendUnavailableError(RunnerError):
    """An inference backend could not be reached, or returned nothing usable.

    Recoverable: the agent loop treats this as "stop here and report what you
    have" rather than as a crash.
    """


class ToolNotFoundError(RunnerError):
    """A tool was requested by name and no such tool is registered."""


class PermissionDeniedError(RunnerError):
    """Policy refused a tool call.

    Raised by policy adapters that prefer exceptions; the loop also accepts a
    boolean refusal from :class:`runner.kernel.ports.PolicyGate`. Both paths
    produce the same recorded outcome.
    """
