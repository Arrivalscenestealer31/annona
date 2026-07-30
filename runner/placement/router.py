"""The backend that enforces placement (layer L2).

:class:`RoutingBackend` is an :class:`~runner.kernel.ports.InferenceBackend`
that owns no wire format. It decides *which* backend serves a turn, checks the
payload one last time before it leaves, records the decision, and — when the
policy allows it — produces a local brief instead of sending the material.

Putting it behind the backend port is what makes the loop untouched by any of
this: the loop asks for a completion, and whether that completion came from a
GPU in the rack, a cluster in Frankfurt, or nowhere at all is a question it
never has to ask. The seam was declared in ``kernel/ports.py`` in Phase 0 for
exactly this.

Two behaviours are the point of the module:

**Failover never widens the permitted set.** When a substrate fails mid-run it
is marked down and placement is recomputed — against the same rule. If the only
survivor is a substrate the policy does not allow for this class, the step is
held. Every gateway retries; this one retries inside the wall.

**Egress is checked against the bytes, not the plan.** The class used for
placement is the maximum of the working set and the classification of the
rendered payload, so a prompt that itself contains identifiers is placed on the
strength of what it contains rather than on where it came from.
"""

from __future__ import annotations

from collections.abc import Mapping

from loguru import logger

from runner.audit.ledger import Ledger
from runner.kernel.blocks import text_block
from runner.kernel.errors import BackendUnavailableError, PlacementHeldError
from runner.kernel.types import (
    Capabilities,
    Completion,
    CompletionRequest,
    Placement,
    Requirement,
    SensitivityClass,
    ToolCall,
    Turn,
)
from runner.placement.engine import PlacementDecisionEngine
from runner.placement.registry import SubstrateRegistry
from runner.policy.classifier import PolicyClassifier, WorkingSet
from runner.policy.models import Policy
from runner.policy.redaction import Redaction, Redactor, class_for_labels, restore

__all__ = ["BRIEF_SYSTEM_PROMPT", "RoutingBackend"]

BRIEF_SYSTEM_PROMPT = (
    "You are producing a BRIEF that will be sent outside this organisation's "
    "perimeter, in place of the material it summarises.\n\n"
    "Rules, in order of importance:\n"
    "1. Never reproduce identifiers: names, tax codes, IBANs, addresses, phone "
    "numbers, email addresses, case or file numbers, dates of birth.\n"
    "2. Never quote more than a few consecutive words from any source document.\n"
    "3. State the question to be answered and the facts needed to answer it, in "
    "general terms. Refer to people and organisations by role ('the client', "
    "'the supplier'), never by name.\n"
    "4. If the question cannot be stated without an identifier, say so and stop.\n\n"
    "Write plain prose. No preamble, no apology, no markdown."
)
"""What the local model is told when it writes a brief.

The instruction is not the control — the brief is reclassified afterwards and
held if it still carries identifiers. It is the first of two layers, and the
cheap one.
"""

MAX_FAILOVER_ATTEMPTS = 4
"""Placement recomputations per turn before giving up.

Bounded because each attempt costs a real call. Four is above the number of
substrates any sane policy allows for one class, and low enough that a network
partition does not turn one turn into a minute of retries.
"""


class RoutingBackend:
    """Places each turn, then delegates. Satisfies ``kernel.ports.InferenceBackend``."""

    def __init__(
        self,
        *,
        policy: Policy,
        engine: PlacementDecisionEngine,
        registry: SubstrateRegistry,
        backends: Mapping[str, object],
        classifier: PolicyClassifier,
        working_set: WorkingSet,
        ledger: Ledger | None = None,
        redactor: Redactor | None = None,
    ) -> None:
        self._policy = policy
        self._engine = engine
        self._registry = registry
        self._backends = dict(backends)
        self._classifier = classifier
        self._working_set = working_set
        self._ledger = ledger
        self._redactor = redactor
        self._last_placement: Placement | None = None
        self._last_redaction: Redaction | None = None

    # ── Port ──────────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "annona"

    @property
    def capabilities(self) -> Capabilities:
        """The conservative intersection of what could serve a turn.

        ``is_local`` is true only when *every* registered backend is local,
        because a capability that is true for some placements and false for
        others must be reported as false. This field is read to decide whether
        calling the runtime constitutes egress; optimism here is a leak.
        """
        caps = [b.capabilities for b in self._backends.values()]  # type: ignore[attr-defined]
        if not caps:
            return Capabilities()
        return Capabilities(
            native_tools=any(c.native_tools for c in caps),
            grammar=next((c.grammar for c in caps if c.grammar != "none"), "none"),
            parallel_tool_calls=all(c.parallel_tool_calls for c in caps),
            context_window=min(c.context_window for c in caps),
            is_local=all(c.is_local for c in caps),
        )

    @property
    def last_placement(self) -> Placement | None:
        """The most recent decision, for callers that report on a run."""
        return self._last_placement

    def complete(self, request: CompletionRequest) -> Completion:
        """Serve one turn, wherever the policy says it may be served.

        Raises:
            PlacementHeldError: no permitted substrate could take this step. The
                loop stops and returns partial results; the ledger holds the
                reason. This is the error that must never be retried elsewhere.
        """
        klass = self._effective_class(request)
        requirement = Requirement(tools=bool(request.tools))

        for attempt in range(1, MAX_FAILOVER_ATTEMPTS + 1):
            placement = self._engine.place(klass, requirement)
            self._last_placement = placement

            if placement.outcome == "briefed":
                return self._complete_via_brief(request, placement, requirement)

            if placement.outcome == "redacted":
                return self._complete_via_redaction(request, placement, requirement)

            if not placement.permitted:
                self._record(placement, request, kind="inference")
                raise PlacementHeldError(placement.reason, placement)

            step_id = self._record(placement, request, kind="inference")

            try:
                return self._call(placement.substrate, request)
            except BackendUnavailableError as exc:
                self._registry.mark_down(placement.substrate, f"{type(exc).__name__}: {exc}")
                self._record_failure(placement, str(exc), step_id)
                logger.warning(
                    f"substrate {placement.substrate} failed on attempt {attempt}; "
                    "recomputing placement within the same rule"
                )

        held = Placement(
            outcome="held",
            klass=klass,
            reason=(
                f"every permitted substrate failed {MAX_FAILOVER_ATTEMPTS} times; "
                "the step is held rather than placed outside the rule"
            ),
        )
        self._last_placement = held
        self._record(held, request, kind="inference")
        raise PlacementHeldError(held.reason, held)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _effective_class(self, request: CompletionRequest) -> SensitivityClass:
        """Class of what is actually about to be sent.

        The maximum of what the run has touched and what the payload contains.
        A canary is treated as restricted material by definition: it exists to
        prove that something which must never leave did not leave, so finding
        one in an outbound payload is not a signal to think about, it is a stop.
        """
        payload = self._render(request)
        klass = max(self._working_set.klass, self._classifier.classify_text(payload))

        for canary in self._policy.egress.canaries:
            if canary and canary in payload:
                self._working_set.observe("canary in outbound payload", SensitivityClass.RESTRICTED)
                return SensitivityClass.RESTRICTED

        return klass

    @staticmethod
    def _render(request: CompletionRequest) -> str:
        """Flatten a request into the text that would cross the wire."""
        parts = [request.system]
        for turn in request.transcript:
            for block in turn.blocks:
                parts.append(str(getattr(block, "content", block)))
        return "\n".join(p for p in parts if p)

    def _call(self, substrate_id: str, request: CompletionRequest) -> Completion:
        backend = self._backends.get(substrate_id)
        if backend is None:
            raise BackendUnavailableError(
                f"substrate {substrate_id!r} is permitted by policy but no backend is wired"
            )

        completion: Completion = backend.complete(request)  # type: ignore[attr-defined]
        self._registry.mark_up(substrate_id)
        return completion

    def _complete_via_brief(
        self,
        request: CompletionRequest,
        placement: Placement,
        requirement: Requirement,
    ) -> Completion:
        """Summarise locally, reclassify, and only then consider crossing.

        The brief is classified as freshly arrived material, not trusted because
        a local model produced it. A model told not to write identifiers writes
        them anyway often enough that trusting the instruction would make this
        the weakest point in the system.
        """
        producer = placement.substrate
        self._record(placement, request, kind="brief")

        brief_request = CompletionRequest(
            system=BRIEF_SYSTEM_PROMPT,
            transcript=request.transcript,
            tools=(),
            temperature=0.0,
            max_tokens=self._policy.egress.brief_max_tokens,
        )
        brief = self._call(producer, brief_request).text.strip()

        if not brief:
            held = Placement(
                outcome="held",
                klass=placement.klass,
                rule_id=placement.rule_id,
                reason=f"the brief producer '{producer}' returned nothing to send",
            )
            self._last_placement = held
            self._record(held, request, kind="brief")
            raise PlacementHeldError(held.reason, held)

        brief_class = self._classifier.classify_content(brief)
        for canary in self._policy.egress.canaries:
            if canary and canary in brief:
                brief_class = SensitivityClass.RESTRICTED

        if brief_class >= placement.klass:
            # The brief exists to lower the class of what crosses. One that is no
            # less sensitive than the material has not done that, and sending it
            # anyway would be an egress with a summary's reputation. Hold.
            held = Placement(
                outcome="held",
                klass=brief_class,
                rule_id=placement.rule_id,
                reason=(
                    f"the brief is still {brief_class.label} after reclassification, "
                    "so it may not cross either"
                ),
                brief_of=producer,
            )
            self._last_placement = held
            self._record(held, request, kind="egress", payload=brief)
            raise PlacementHeldError(held.reason, held)

        onward = self._engine.place(brief_class, requirement)
        self._last_placement = onward

        if not onward.permitted:
            held = Placement(
                outcome="held",
                klass=brief_class,
                rule_id=onward.rule_id,
                reason=(
                    f"the brief is still {brief_class.label} after reclassification, "
                    "so it may not cross either"
                ),
                rejected=onward.rejected,
                brief_of=producer,
            )
            self._last_placement = held
            self._record(held, request, kind="egress", payload=brief)
            raise PlacementHeldError(held.reason, held)

        cleared, why = self._engine.clears_egress(brief_class, onward.substrate)
        if not cleared:  # pragma: no cover - defence in depth, place() already checked
            held = Placement(outcome="held", klass=brief_class, reason=why, brief_of=producer)
            self._last_placement = held
            self._record(held, request, kind="egress", payload=brief)
            raise PlacementHeldError(why, held)

        self._record(
            Placement(
                outcome="placed",
                klass=brief_class,
                substrate=onward.substrate,
                rule_id=onward.rule_id,
                reason=f"brief produced by {producer}, reclassified {brief_class.label}, cleared",
                brief_of=producer,
            ),
            request,
            kind="egress",
            payload=brief,
        )

        briefed_request = CompletionRequest(
            system=request.system,
            transcript=(Turn(role="user", blocks=(text_block(brief),)),),
            tools=request.tools,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            model=request.model,
        )
        return self._call(onward.substrate, briefed_request)

    def _complete_via_redaction(
        self,
        request: CompletionRequest,
        placement: Placement,
        requirement: Requirement,
    ) -> Completion:
        """Replace the identifiers locally, send the rest, put them back after.

        The sequence is the whole point, and every step of it is a control:

        1. a local model finds the identifiers and returns the text without
           them, plus the mapping — which never leaves this process;
        2. the redacted text is **reclassified from scratch**. A redactor that
           missed something produces text that merely looks safe, so its output
           is treated as freshly arrived material rather than as a promise;
        3. only then is placement recomputed, against the lower class;
        4. the answer comes back with placeholders in it, and is re-identified
           here. If the model invented a placeholder nobody can resolve, that is
           recorded rather than shipped as if it were a name.

        Pseudonymous is not anonymous: the mapping exists, so this reduces
        exposure rather than removing it. That distinction belongs in the
        conversation with a DPO, and it is why the ledger records that a
        redaction happened, how many identifiers of which kinds, and nothing
        else.
        """
        if self._redactor is None:  # pragma: no cover - the loader refuses this
            held = Placement(
                outcome="held",
                klass=placement.klass,
                rule_id=placement.rule_id,
                reason="the rule asks for redaction and no redactor is wired",
            )
            self._last_placement = held
            self._record(held, request, kind="egress")
            raise PlacementHeldError(held.reason, held)

        payload = self._render(request)

        try:
            redaction = self._redactor.analyse(payload)
        except BackendUnavailableError as exc:
            if self._policy.redaction.fails_closed:
                held = Placement(
                    outcome="held",
                    klass=placement.klass,
                    rule_id=placement.rule_id,
                    reason=f"the redactor is unavailable and the policy holds on error: {exc}",
                )
                self._last_placement = held
                self._record(held, request, kind="egress")
                raise PlacementHeldError(held.reason, held) from exc
            raise

        self._last_redaction = redaction

        redacted_class = max(
            self._classifier.classify_text(redaction.text),
            class_for_labels({}, self._policy.redaction),
        )
        for canary in self._policy.egress.canaries:
            if canary and canary in redaction.text:
                redacted_class = SensitivityClass.RESTRICTED

        if redacted_class >= placement.klass:
            held = Placement(
                outcome="held",
                klass=redacted_class,
                rule_id=placement.rule_id,
                reason=(
                    f"after redaction the payload is still {redacted_class.label}; "
                    f"{redaction.count} identifier(s) were replaced and something "
                    "sensitive remains"
                ),
            )
            self._last_placement = held
            self._record(held, request, kind="egress", payload=redaction.text)
            raise PlacementHeldError(held.reason, held)

        onward = self._engine.place(redacted_class, requirement)
        if not onward.permitted or onward.outcome != "placed":
            held = Placement(
                outcome="held",
                klass=redacted_class,
                rule_id=onward.rule_id,
                reason="the redacted payload has nowhere permitted to go either",
                rejected=onward.rejected,
            )
            self._last_placement = held
            self._record(held, request, kind="egress", payload=redaction.text)
            raise PlacementHeldError(held.reason, held)

        cleared, why = self._engine.clears_egress(redacted_class, onward.substrate)
        if not cleared:  # pragma: no cover - defence in depth
            held = Placement(outcome="held", klass=redacted_class, reason=why)
            self._last_placement = held
            self._record(held, request, kind="egress", payload=redaction.text)
            raise PlacementHeldError(why, held)

        crossing = Placement(
            outcome="redacted",
            klass=redacted_class,
            substrate=onward.substrate,
            rule_id=onward.rule_id,
            reason=(
                f"{redaction.count} identifier(s) replaced by {self._redactor.name}; "
                f"reclassified {redacted_class.label} and cleared for {onward.substrate}"
            ),
            candidates=onward.candidates,
        )
        self._last_placement = crossing
        self._record(
            crossing,
            request,
            kind="egress",
            payload=redaction.text,
            extra={"redacted": redaction.summary(), "redactor": self._redactor.name},
        )

        redacted_request = CompletionRequest(
            system=request.system,
            transcript=(Turn(role="user", blocks=(text_block(redaction.text),)),),
            tools=request.tools,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            model=request.model,
        )
        completion = self._call(onward.substrate, redacted_request)

        return self._reidentify(completion, redaction)

    def _reidentify(self, completion: Completion, redaction: Redaction) -> Completion:
        """Put the real values back into the answer, here and nowhere else."""
        if not redaction.mapping:
            return completion

        restored = tuple(restore(part, redaction.mapping) for part in completion.text_parts)
        calls = tuple(
            ToolCall(
                id=call.id,
                name=call.name,
                arguments={
                    key: restore(value, redaction.mapping) if isinstance(value, str) else value
                    for key, value in call.arguments.items()
                },
            )
            for call in completion.tool_calls
        )
        return Completion(
            text_parts=restored,
            tool_calls=calls,
            stop_reason=completion.stop_reason,
        )

    # ── Recording ─────────────────────────────────────────────────────────────

    def _record(
        self,
        placement: Placement,
        request: CompletionRequest,
        *,
        kind: str,
        payload: str | None = None,
        extra: Mapping[str, object] | None = None,
    ) -> str:
        if self._ledger is None:
            return ""
        return self._ledger.record(
            kind,
            outcome=placement.outcome,
            klass=placement.klass,
            substrate=placement.substrate,
            rule_id=placement.rule_id,
            payload=payload if payload is not None else self._render(request),
            detail={
                "reason": placement.reason,
                "candidates": list(placement.candidates),
                "rejected": [list(r) for r in placement.rejected],
                "working_set": self._working_set.reason,
                "brief_of": placement.brief_of,
                **(dict(extra) if extra else {}),
            },
        )

    def _record_failure(self, placement: Placement, error: str, step_id: str) -> None:
        if self._ledger is None:
            return
        self._ledger.record(
            "inference",
            outcome="held",
            klass=placement.klass,
            substrate=placement.substrate,
            rule_id=placement.rule_id,
            detail={
                "reason": f"substrate failed: {error}",
                "retry_of": step_id,
                "note": "placement is recomputed within the same rule; the rule is not widened",
            },
        )
