"""HTTP surface for the kernel: policy, substrates, ledger, and asking it things.

Until this module existed, everything the product claims to do was reachable only
from a terminal. The desktop window showed notes and a sync status — a person
could install Annona, use it all day, and never once see a placement decision or
a refusal. A guarantee nobody can watch is indistinguishable from a slogan, so
the read side of the kernel is now an API and the window can show it.

Four reads and one write:

``GET  /api/kernel/policy``       the document, as the runtime understands it
``GET  /api/kernel/substrates``   what is registered, and whether it answers
``GET  /api/kernel/ledger``       recent decisions, refusals included
``GET  /api/kernel/ledger/verify``the chain, checked offline
``POST /api/kernel/ask``          run one request through the perimeter

``ask`` returns the answer *and* the decisions the answer required, because the
two are one fact: an answer that arrived without saying where it was computed is
exactly what this product exists to replace.

Nothing here mutates the policy. Editing the perimeter from a web page reachable
by every process on the machine is a larger decision than it looks, and it can be
made later; being unable to read the perimeter was the defect.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from runner.audit.ledger import read_entries, verify_file
from runner.kernel.errors import ConfigurationError, PolicyError
from runner.policy.loader import load_policy
from runner.services.enforcement import policy_path

__all__ = ["AskRequest", "kernel_router"]


# ── I/O models ────────────────────────────────────────────────────────────────


class AskRequest(BaseModel):
    """One request to run through the perimeter."""

    prompt: str = Field(min_length=1)
    max_iterations: int = Field(default=8, ge=1, le=30)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _ledger_path() -> Path:
    return policy_path().parent / "ledger.jsonl"


def _entry_json(entry: Any) -> dict[str, Any]:
    """One ledger entry, flattened for a UI that has to render it in a row.

    ``detail`` is passed through rather than summarised: it carries the rejected
    candidates and the reason, which is the part an operator actually reads. It
    contains digests, never payloads — that is a property of what the ledger
    records, not something this function has to enforce.
    """
    return {
        "seq": entry.seq,
        "ts": entry.ts,
        "run_id": entry.run_id,
        "step_id": entry.step_id,
        "kind": entry.kind,
        "outcome": entry.outcome,
        "class": entry.klass,
        "substrate": entry.substrate,
        "rule_id": entry.rule_id,
        "payload_digest": entry.payload_digest,
        "detail": dict(entry.detail),
        "hash": entry.hash,
    }


def _load_policy_or_404():
    """The policy, or an HTTP error that says how to create one."""
    target = policy_path()
    if not target.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"no policy at {target}. Run `annona policy init` to write one — "
                "until then nothing is enforced."
            ),
        )
    try:
        return load_policy(target), target
    except PolicyError as exc:
        # 422, not 500: the file is there and this is what is wrong with it. A
        # policy that fails to load must never be reported as "no policy".
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ── Router ────────────────────────────────────────────────────────────────────


def kernel_router(executor: Any | None = None) -> APIRouter:
    """Build the kernel routes.

    Args:
        executor: The daemon's :class:`~runner.executor.TaskExecutor`. Supplies
            the tools, the permissions and the AI client that ``ask`` runs
            through. When absent — a daemon started without one, or a test —
            the reads still work and ``ask`` answers 503 rather than pretending.
    """
    router = APIRouter(prefix="/api/kernel", tags=["kernel"])

    @router.get("/policy")
    def get_policy() -> dict[str, Any]:
        """The policy as the runtime understands it, not as it is written."""
        policy, target = _load_policy_or_404()
        return {
            "source": str(target),
            "version": policy.version,
            "default_class": policy.default_class.label,
            # What earns a class, not just its name: the paths and patterns are
            # the answer to "why was my document restricted?", and that question
            # is asked far more often than "which classes exist?".
            "classes": [
                {
                    "label": klass.label,
                    "paths": list(spec.paths),
                    "patterns": [p.pattern for p in spec.patterns],
                    "default": spec.default,
                }
                for klass, spec in policy.classes.items()
            ],
            "substrates": [
                {
                    "id": s.id,
                    "kind": s.kind,
                    "jurisdiction": s.jurisdiction,
                    "max_class": s.max_class.label,
                    "endpoint": s.endpoint or "",
                    "model": s.model or "",
                    "tools": s.tools,
                    "vision": s.vision,
                    "distance": s.distance,
                }
                for s in policy.substrates
            ],
            "rules": [
                {
                    "id": r.id,
                    "class": r.klass.label,
                    "allow": list(r.allow),
                    "on_unavailable": r.on_unavailable,
                    "prefer": r.prefer,
                }
                for r in policy.rules
            ],
            "tools": {
                "allow": {tool: list(paths) for tool, paths in sorted(policy.tools.allow.items())},
                "deny_paths": list(policy.tools.deny_paths),
            },
            "skills": list(policy.skills.allow),
            "redaction": {
                "enabled": policy.redaction.enabled,
                "provider": policy.redaction.provider,
                "endpoint": policy.redaction.endpoint,
            },
        }

    @router.get("/substrates")
    def get_substrates(probe: bool = Query(True, description="Check liveness over HTTP")):
        """What is registered, where it is, and whether it answers right now."""
        from runner.placement.registry import SubstrateRegistry, http_prober

        policy, _ = _load_policy_or_404()
        registry = SubstrateRegistry.from_substrates(
            policy.substrates, prober=http_prober() if probe else None
        )
        out = []
        for sid, health in registry.snapshot().items():
            sub = registry.substrates[sid]
            out.append(
                {
                    "id": sid,
                    "kind": sub.kind,
                    "jurisdiction": sub.jurisdiction,
                    "max_class": sub.max_class.label,
                    "endpoint": sub.endpoint or "",
                    "model": sub.model or "",
                    "up": health.up,
                    "reason": health.reason,
                    "latency_ms": health.latency_ms,
                }
            )
        return {"probed": probe, "substrates": out}

    @router.get("/ledger")
    def get_ledger(
        limit: int = Query(60, ge=1, le=500),
        held: bool = Query(False, description="Refusals only"),
        run_id: str = Query("", description="One run"),
    ):
        """Recent decisions, newest last, refusals included.

        Refusals are not an error condition to be filtered out of a happy path:
        a held step is the product working. They come back in the same list, and
        `held=true` narrows to them rather than revealing them.
        """
        target = _ledger_path()
        if not target.exists():
            return {"path": str(target), "total": 0, "entries": []}

        entries = list(read_entries(target))
        selected = entries
        if run_id:
            selected = [e for e in selected if e.run_id == run_id]
        if held:
            selected = [e for e in selected if e.outcome == "held"]

        return {
            "path": str(target),
            "total": len(entries),
            "shown": len(selected[-limit:]),
            "entries": [_entry_json(e) for e in selected[-limit:]],
        }

    @router.get("/ledger/verify")
    def verify_ledger():
        """Check the chain. Reads the file; contacts nobody."""
        target = _ledger_path()
        if not target.exists():
            return {"path": str(target), "ok": True, "entries": 0, "problem": "", "empty": True}
        result = verify_file(target)
        return {
            "path": str(target),
            "ok": result.ok,
            "entries": result.entries,
            "problem": result.problem or "",
            "empty": False,
        }

    @router.get("/status")
    def kernel_status():
        """One call for a header: is a policy enforcing, and is anything up."""
        target = policy_path()
        if not target.exists():
            return {"enforcing": False, "policy": str(target), "reason": "no policy file"}
        try:
            policy = load_policy(target)
        except PolicyError as exc:
            return {"enforcing": False, "policy": str(target), "reason": str(exc)}

        ledger = _ledger_path()
        decisions = sum(1 for _ in read_entries(ledger)) if ledger.exists() else 0
        return {
            "enforcing": True,
            "policy": str(target),
            "reason": "",
            "substrates": len(policy.substrates),
            "rules": len(policy.rules),
            "default_class": policy.default_class.label,
            "decisions": decisions,
        }

    @router.post("/ask")
    def ask(req: AskRequest):
        """Run one request through the perimeter and return what it decided.

        Deliberately synchronous: `def`, not `async def`, so FastAPI runs it in a
        worker thread. The agent loop is blocking and calls a local model that
        can take tens of seconds; running it on the event loop would freeze every
        other request, including the health check the window uses to decide
        whether the daemon is alive.
        """
        if executor is None:
            raise HTTPException(
                status_code=503,
                detail="this daemon has no executor; start it with `annona run`",
            )

        ledger = _ledger_path()
        # Where the ledger stood before the run, so the response can carry the
        # decisions *this* request caused rather than the whole history.
        before = sum(1 for _ in read_entries(ledger)) if ledger.exists() else 0

        try:
            result = executor.ai_client.reason_and_execute(
                prompt=req.prompt,
                context={"source": "desktop", "surface": "kernel-api"},
                tools=executor.tools,
                permissions=executor.permissions,
                max_iterations=req.max_iterations,
            )
        except ConfigurationError as exc:
            # The perimeter could not be assembled. 409, not 500: nothing is
            # broken, the configuration refuses to run — and the run correctly
            # did not happen.
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 — surfaced, not swallowed
            logger.exception("kernel ask failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        new_entries = []
        if ledger.exists():
            new_entries = [_entry_json(e) for e in list(read_entries(ledger))[before:]]

        return {
            "response": result.get("response", ""),
            "iterations": result.get("iterations", 0),
            "tool_calls": result.get("tool_calls", []),
            # Present only on the enforced path. Absent means no policy was in
            # force, and the UI has to say so rather than draw a reassuring chip.
            "placement": result.get("placement"),
            "enforced": "placement" in result,
            "decisions": new_entries,
        }

    return router
