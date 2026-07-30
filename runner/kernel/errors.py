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


class PlacementHeldError(BackendUnavailableError):
    """No permitted substrate could take this step, so it was not taken.

    Deliberately a subclass of :class:`BackendUnavailableError`: to the agent
    loop, "the policy will not let this run anywhere" and "the backend is down"
    have the same correct response — stop, keep what you have, do not improvise.
    Everything that distinguishes the two lives in the ledger and in the
    attached :class:`~runner.kernel.types.Placement`.

    This is the error that must never be caught and retried against a different
    substrate. Failover may cost latency, money or model quality; it may not
    cost jurisdiction.
    """

    def __init__(self, message: str, placement: object | None = None) -> None:
        super().__init__(message)
        self.placement = placement


class PolicyError(ConfigurationError):
    """A policy file is missing, malformed, or internally inconsistent.

    Fatal, like every configuration error: a perimeter that starts with a policy
    it could not parse is worse than one that refuses to start, because it looks
    like it is working.
    """


class ToolNotFoundError(RunnerError):
    """A tool was requested by name and no such tool is registered."""


class PermissionDeniedError(RunnerError):
    """Policy refused a tool call.

    Raised by policy adapters that prefer exceptions; the loop also accepts a
    boolean refusal from :class:`runner.kernel.ports.PolicyGate`. Both paths
    produce the same recorded outcome.
    """
