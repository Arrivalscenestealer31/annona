"""L2 — policy: classification, rules, and the decision to permit or refuse.

The layer that turns a document the customer owns into an answer the runtime
must obey. It depends on the kernel (L0) and on nothing else: no provider SDK,
no tool implementation, no HTTP client on the import path.

- :mod:`runner.policy.models` — the validated shape of a policy
- :mod:`runner.policy.loader` — reading, validating and generating one
- :mod:`runner.policy.classifier` — what class material has, and the working set
- :mod:`runner.policy.gate` — default-deny clearance for tool calls
- :mod:`runner.policy.tracking` — the executor decorator that keeps the working
  set honest about everything a run has read
- :mod:`runner.policy.redaction` — pseudonymisation: the types, the label→class
  translation, and putting the real values back afterwards
"""

from runner.policy.classifier import PolicyClassifier, WorkingSet
from runner.policy.gate import DefaultDenyGate
from runner.policy.loader import (
    default_policy,
    default_policy_document,
    load_policy,
    parse_policy,
    write_default_policy,
)
from runner.policy.models import (
    ClassSpec,
    EgressPolicy,
    Policy,
    Rule,
    Substrate,
    ToolPolicy,
)
from runner.policy.redaction import (
    Redaction,
    RedactionPolicy,
    Redactor,
    class_for_labels,
    restore,
)
from runner.policy.tracking import TrackingExecutor

__all__ = [
    "ClassSpec",
    "DefaultDenyGate",
    "EgressPolicy",
    "Policy",
    "PolicyClassifier",
    "Redaction",
    "RedactionPolicy",
    "Redactor",
    "Rule",
    "Substrate",
    "ToolPolicy",
    "TrackingExecutor",
    "WorkingSet",
    "class_for_labels",
    "default_policy",
    "default_policy_document",
    "load_policy",
    "parse_policy",
    "restore",
    "write_default_policy",
]
