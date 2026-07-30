"""Placement conformance: the matrix a customer's auditor would run.

Fifteen cases over three classes and five liveness states. The test that matters
is the second row: **when the local GPU is down, restricted work is held, not
rerouted.** Every AI gateway on the market passes the others.

The policy under test is the shape a real deployment has — an on-prem runtime, a
private EU cluster, and a frontier API, each with a different ceiling — so the
matrix is the deployment's behaviour, not an abstraction of it.
"""

from __future__ import annotations

import pytest

from runner.kernel.types import Requirement, SensitivityClass
from runner.placement.engine import PlacementDecisionEngine
from runner.placement.registry import Health, SubstrateRegistry
from runner.policy.loader import parse_policy

pytestmark = pytest.mark.unit

PUBLIC = SensitivityClass.PUBLIC
INTERNAL = SensitivityClass.INTERNAL
RESTRICTED = SensitivityClass.RESTRICTED


POLICY_DOCUMENT = {
    "version": 1,
    "default": "deny",
    "classes": {
        "restricted": {"paths": ["/mnt/clients/**"]},
        "internal": {"paths": ["/mnt/work/**"]},
        "public": {"default": True},
    },
    "substrates": [
        {
            "id": "local-gpu",
            "kind": "echo",
            "jurisdiction": "on-prem",
            "max_class": "restricted",
            "quality": 60,
            "cost_per_mtok": 0.0,
        },
        {
            "id": "eu-cluster",
            "kind": "echo",
            "jurisdiction": "eu",
            "max_class": "internal",
            "quality": 70,
            "cost_per_mtok": 1.0,
        },
        {
            "id": "frontier",
            "kind": "echo",
            "jurisdiction": "us",
            "max_class": "public",
            "quality": 95,
            "cost_per_mtok": 15.0,
        },
    ],
    "rules": [
        {
            "id": "R-restricted",
            "match": {"class": "restricted"},
            "allow": ["local-gpu"],
            "on_unavailable": "hold",
        },
        {
            "id": "R-internal",
            "match": {"class": "internal"},
            "allow": ["local-gpu", "eu-cluster"],
            "on_unavailable": "queue",
            "prefer": "privacy",
        },
        {
            "id": "R-public",
            "match": {"class": "public"},
            "allow": ["local-gpu", "eu-cluster", "frontier"],
            "on_unavailable": "hold",
            "prefer": "quality",
        },
    ],
}


def engine_with(down: tuple[str, ...] = ()) -> PlacementDecisionEngine:
    """An engine whose named substrates are unreachable."""
    policy = parse_policy(POLICY_DOCUMENT)
    registry = SubstrateRegistry.from_substrates(policy.substrates)
    for substrate_id in down:
        registry.mark_down(substrate_id, "simulated outage")
    return PlacementDecisionEngine(policy, registry)


# ── The conformance matrix ────────────────────────────────────────────────────

MATRIX = [
    # (down substrates, class, expected outcome, expected substrate)
    ((), RESTRICTED, "placed", "local-gpu"),
    ((), INTERNAL, "placed", "local-gpu"),
    ((), PUBLIC, "placed", "frontier"),
    (("local-gpu",), RESTRICTED, "held", ""),
    (("local-gpu",), INTERNAL, "placed", "eu-cluster"),
    (("local-gpu",), PUBLIC, "placed", "frontier"),
    (("eu-cluster",), RESTRICTED, "placed", "local-gpu"),
    (("eu-cluster",), INTERNAL, "placed", "local-gpu"),
    (("eu-cluster",), PUBLIC, "placed", "frontier"),
    (("frontier",), PUBLIC, "placed", "eu-cluster"),
    (("frontier", "eu-cluster"), PUBLIC, "placed", "local-gpu"),
    (("local-gpu", "eu-cluster"), INTERNAL, "queued", ""),
    (("local-gpu", "eu-cluster", "frontier"), PUBLIC, "held", ""),
    (("local-gpu", "eu-cluster", "frontier"), INTERNAL, "queued", ""),
    (("local-gpu", "eu-cluster", "frontier"), RESTRICTED, "held", ""),
]


@pytest.mark.parametrize(
    ("down", "klass", "outcome", "substrate"),
    MATRIX,
    ids=[f"{k.label}-down:{'+'.join(d) or 'none'}" for d, k, _, _ in MATRIX],
)
def test_placement_conformance(down, klass, outcome, substrate):
    placement = engine_with(down).place(klass, Requirement(tools=True))
    assert placement.outcome == outcome
    assert placement.substrate == substrate


def test_restricted_work_is_held_when_local_is_down_and_names_why():
    """The single most important assertion in this repository.

    A frontier API is up, has capacity, and would answer well. It is not used,
    and the record says so in words a non-engineer can check.
    """
    placement = engine_with(("local-gpu",)).place(RESTRICTED, Requirement(tools=True))

    assert placement.outcome == "held"
    assert placement.substrate == ""
    assert "holds rather than downgrades" in placement.reason

    rejected = dict(placement.rejected)
    assert "unhealthy" in rejected["local-gpu"]
    assert rejected["frontier"] == "max_class public < restricted"
    assert rejected["eu-cluster"] == "max_class internal < restricted"


def test_a_class_with_no_rule_is_held():
    """Default-deny is not a slogan about tools; it covers placement too."""
    policy = parse_policy(
        {
            **POLICY_DOCUMENT,
            "rules": [{"id": "R-public", "match": {"class": "public"}, "allow": ["frontier"]}],
        }
    )
    engine = PlacementDecisionEngine(policy, SubstrateRegistry.from_substrates(policy.substrates))

    placement = engine.place(RESTRICTED)
    assert placement.outcome == "held"
    assert "no rule covers class restricted" in placement.reason


# ── Requirements ──────────────────────────────────────────────────────────────


def test_a_substrate_without_tool_support_is_not_chosen_for_a_tool_step():
    document = {
        **POLICY_DOCUMENT,
        "substrates": [
            {**POLICY_DOCUMENT["substrates"][0], "tools": False},
            POLICY_DOCUMENT["substrates"][1],
            POLICY_DOCUMENT["substrates"][2],
        ],
    }
    policy = parse_policy(document)
    engine = PlacementDecisionEngine(policy, SubstrateRegistry.from_substrates(policy.substrates))

    with_tools = engine.place(INTERNAL, Requirement(tools=True))
    without_tools = engine.place(INTERNAL, Requirement(tools=False))

    assert with_tools.substrate == "eu-cluster"
    assert without_tools.substrate == "local-gpu"
    assert dict(with_tools.rejected)["local-gpu"] == "does not support tool use"


def test_a_substrate_with_too_small_a_context_is_not_chosen():
    document = {
        **POLICY_DOCUMENT,
        "substrates": [
            {**POLICY_DOCUMENT["substrates"][0], "context_window": 8_000},
            {**POLICY_DOCUMENT["substrates"][1], "context_window": 128_000},
            POLICY_DOCUMENT["substrates"][2],
        ],
    }
    policy = parse_policy(document)
    engine = PlacementDecisionEngine(policy, SubstrateRegistry.from_substrates(policy.substrates))

    placement = engine.place(INTERNAL, Requirement(min_context=32_000))
    assert placement.substrate == "eu-cluster"
    assert "context window 8000" in dict(placement.rejected)["local-gpu"]


def test_a_restricted_step_is_held_rather_than_placed_on_a_bigger_context_elsewhere():
    """Capacity is never a reason to cross a jurisdiction."""
    document = {
        **POLICY_DOCUMENT,
        "substrates": [
            {**POLICY_DOCUMENT["substrates"][0], "context_window": 8_000},
            {**POLICY_DOCUMENT["substrates"][1], "context_window": 128_000},
            {**POLICY_DOCUMENT["substrates"][2], "context_window": 200_000},
        ],
    }
    policy = parse_policy(document)
    engine = PlacementDecisionEngine(policy, SubstrateRegistry.from_substrates(policy.substrates))

    assert engine.place(RESTRICTED, Requirement(min_context=100_000)).outcome == "held"


# ── Preference and determinism ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("prefer", "expected"),
    [("privacy", "local-gpu"), ("cost", "local-gpu"), ("quality", "frontier"), ("latency", "local-gpu")],
)
def test_preference_decides_among_permitted_substrates(prefer, expected):
    document = {
        **POLICY_DOCUMENT,
        "rules": [
            {
                "id": "R-public",
                "match": {"class": "public"},
                "allow": ["local-gpu", "eu-cluster", "frontier"],
                "prefer": prefer,
            }
        ],
    }
    policy = parse_policy(document)
    engine = PlacementDecisionEngine(policy, SubstrateRegistry.from_substrates(policy.substrates))
    assert engine.place(PUBLIC).substrate == expected


def test_ties_break_on_the_order_the_rule_lists_them():
    """Two identical substrates must not be chosen by dictionary order."""
    document = {
        **POLICY_DOCUMENT,
        "substrates": [
            {"id": "b", "kind": "echo", "jurisdiction": "eu", "max_class": "public", "quality": 50},
            {"id": "a", "kind": "echo", "jurisdiction": "eu", "max_class": "public", "quality": 50},
        ],
        "rules": [{"id": "R", "match": {"class": "public"}, "allow": ["a", "b"], "prefer": "cost"}],
    }
    policy = parse_policy(document)
    engine = PlacementDecisionEngine(policy, SubstrateRegistry.from_substrates(policy.substrates))
    assert engine.place(PUBLIC).substrate == "a"


def test_the_same_facts_always_produce_the_same_placement():
    """Reproducibility is a property an auditor tests, so it is one we assert."""
    engine = engine_with()
    decisions = {engine.place(INTERNAL, Requirement(tools=True)).substrate for _ in range(50)}
    assert decisions == {"local-gpu"}


# ── Egress double-check ───────────────────────────────────────────────────────


def test_egress_refuses_a_payload_above_the_destination_ceiling():
    engine = engine_with()
    ok, why = engine.clears_egress(RESTRICTED, "frontier")
    assert not ok
    assert "capped at public" in why


def test_egress_allows_what_placement_allowed():
    assert engine_with().clears_egress(PUBLIC, "frontier") == (True, "")


def test_egress_refuses_an_unregistered_destination():
    ok, why = engine_with().clears_egress(PUBLIC, "somewhere-else")
    assert not ok and "not registered" in why


# ── Explanation ───────────────────────────────────────────────────────────────


def test_explain_names_the_rule_the_candidates_and_the_losers():
    text = engine_with(("local-gpu",)).explain(RESTRICTED, Requirement(tools=True))
    assert "R-restricted" in text
    assert "candidates   none" in text
    assert "frontier — max_class public < restricted" in text


# ── Registry ──────────────────────────────────────────────────────────────────


def test_an_unregistered_substrate_is_down_not_missing():
    registry = SubstrateRegistry.from_substrates(parse_policy(POLICY_DOCUMENT).substrates)
    health = registry.health("nope")
    assert not health.up and "not registered" in health.reason


def test_a_failed_call_trips_the_breaker_for_the_cooloff():
    # one tick per health() call: mark_down, then three checks
    clock = iter([0.0, 1.0, 2.0, 500.0])
    registry = SubstrateRegistry.from_substrates(
        parse_policy(POLICY_DOCUMENT).substrates,
        clock=lambda: next(clock),
        cooloff=60.0,
    )

    registry.mark_down("frontier", "connection refused")
    assert not registry.is_up("frontier")
    assert not registry.is_up("frontier"), "the breaker must stay tripped inside the cooloff"
    assert registry.is_up("frontier"), "and must clear once the cooloff has passed"


def test_a_successful_call_clears_the_breaker():
    registry = SubstrateRegistry.from_substrates(parse_policy(POLICY_DOCUMENT).substrates)
    registry.mark_down("eu-cluster", "timeout")
    registry.mark_up("eu-cluster", latency_ms=12.0)
    assert registry.is_up("eu-cluster")


def test_probes_run_only_for_substrates_that_asked_for_one():
    calls: list[str] = []

    def prober(substrate):
        calls.append(substrate.id)
        return Health.ok()

    document = {
        **POLICY_DOCUMENT,
        "substrates": [
            {**POLICY_DOCUMENT["substrates"][0], "probe": True, "endpoint": "http://x/v1"},
            POLICY_DOCUMENT["substrates"][1],
            POLICY_DOCUMENT["substrates"][2],
        ],
    }
    registry = SubstrateRegistry.from_substrates(parse_policy(document).substrates, prober=prober)
    registry.snapshot()

    assert calls == ["local-gpu"]


def test_probe_results_are_cached_for_the_ttl():
    calls: list[str] = []
    # one tick per is_up(): inside the TTL, inside the TTL, past it
    clock = iter([0.0, 1.0, 100.0])

    def prober(substrate):
        calls.append(substrate.id)
        return Health.ok()

    document = {
        **POLICY_DOCUMENT,
        "substrates": [
            {**POLICY_DOCUMENT["substrates"][0], "probe": True, "endpoint": "http://x/v1"}
        ],
        "rules": [{"id": "R", "match": {"class": "public"}, "allow": ["local-gpu"]}],
    }
    registry = SubstrateRegistry.from_substrates(
        parse_policy(document).substrates,
        prober=prober,
        clock=lambda: next(clock),
        ttl=10.0,
    )

    registry.is_up("local-gpu")
    registry.is_up("local-gpu")
    registry.is_up("local-gpu")

    assert calls == ["local-gpu", "local-gpu"], "one probe inside the TTL, one after it"
