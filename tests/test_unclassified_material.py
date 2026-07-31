"""What happens to material nothing recognised.

Written after a live run got this wrong in the worst possible way. The prompt was

    "ciao, sono Matteo Ballabio, ho 27 anni e vorrei che mi scrivessi
     un'email per luca rossi"

— a name, an age, and a third party's name. It was classified **public** and
placed on a substrate outside the machine. Nothing leaked, because that substrate
happened to be the offline echo stub; had it been the Anthropic adapter one line
above it in the same file, it would have left.

Two defects produced that, and the suite had a test for neither:

1. ``Enforcement`` built ``WorkingSet()``, whose constructor defaults to PUBLIC.
   A policy declaring ``internal`` as its default class was ignored, so every run
   started at the class granting the widest permission — while
   ``Policy.default_class`` documented the opposite ("unclassifiable material is
   treated as the most sensitive, never the least").

2. The shipped policy made ``public`` the floor. A regex cannot recognise a
   sentence about a person; it matches no pattern and lives at no path. With a
   public floor, every such sentence is placeable anywhere the operator has ever
   allowed public — and adding a frontier substrate is the documented next step.

The rule these tests hold the code to: **the class of the unrecognised is the
cautious one.** A guarantee that only covers material you already knew how to
recognise is not a guarantee.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from runner.kernel.blocks import text_block
from runner.kernel.types import CompletionRequest, SensitivityClass, Turn
from runner.policy.loader import default_policy, load_policy
from runner.services.enforcement import Enforcement

# The sentence that started this. Nothing in it matches a path or a pattern.
ORDINARY_PROMPT = (
    "ciao, sono Matteo Ballabio, ho 27 anni e vorrei che mi scrivessi " "un'email per luca rossi"
)


POLICY_WITH_A_FRONTIER = """
version: 1
default: deny

classes:
  restricted:
    paths: ["~/clienti/**"]
    patterns: ['-----BEGIN [A-Z ]*PRIVATE KEY-----']
  internal:
    paths: ["~/**"]
    default: true
  public: {}

substrates:
  - id: local-gpu
    kind: echo
    jurisdiction: on-prem
    max_class: restricted
    quality: 60
  - id: frontier
    kind: echo
    jurisdiction: us
    max_class: public
    quality: 99

rules:
  - match: {class: restricted}
    allow: [local-gpu]
    on_unavailable: hold
  - match: {class: internal}
    allow: [local-gpu]
    on_unavailable: hold
  - match: {class: public}
    allow: [frontier, local-gpu]
    on_unavailable: hold
    prefer: quality
"""


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    h = tmp_path / "annona-home"
    h.mkdir()
    monkeypatch.setenv("ANNONA_HOME", str(h))
    return h


def _request(text: str) -> CompletionRequest:
    return CompletionRequest(
        system="",
        transcript=(Turn(role="user", blocks=(text_block(text),)),),
        tools=(),
    )


# ── The floor ─────────────────────────────────────────────────────────────────


def test_the_shipped_policy_treats_the_unrecognised_as_internal():
    assert default_policy().default_class is SensitivityClass.INTERNAL


def test_a_run_starts_at_the_class_the_policy_declares(home, tmp_path):
    """The bug in one line: the floor must come from the policy, not the
    constructor's default."""
    path = tmp_path / "policy.yaml"
    path.write_text(POLICY_WITH_A_FRONTIER)

    enforcement = Enforcement.for_run(
        policy_file=path, ledger_path=tmp_path / "ledger.jsonl", probe=False, fsync=False
    )
    assert enforcement.klass is SensitivityClass.INTERNAL


def test_a_policy_with_a_public_floor_is_still_honoured(home, tmp_path):
    """The fix is "obey the policy", not "always start at internal". An operator
    who deliberately declares a public floor gets one."""
    path = tmp_path / "policy.yaml"
    path.write_text(
        POLICY_WITH_A_FRONTIER.replace(
            '  internal:\n    paths: ["~/**"]\n    default: true',
            '  internal:\n    paths: ["~/**"]',
        ).replace("  public: {}", "  public:\n    default: true")
    )

    enforcement = Enforcement.for_run(
        policy_file=path, ledger_path=tmp_path / "ledger.jsonl", probe=False, fsync=False
    )
    assert enforcement.klass is SensitivityClass.PUBLIC


# ── The placement that follows ────────────────────────────────────────────────


def test_an_ordinary_sentence_about_a_person_does_not_leave_the_machine(home, tmp_path):
    """The live failure, as a test.

    A frontier substrate is registered and allowed for public, exactly as an
    operator following the docs would set it up. The prompt must still be served
    on-premise, because nothing recognised it and unrecognised is internal.
    """
    path = tmp_path / "policy.yaml"
    path.write_text(POLICY_WITH_A_FRONTIER)

    enforcement = Enforcement.for_run(
        policy_file=path, ledger_path=tmp_path / "ledger.jsonl", probe=False, fsync=False
    )
    backend = enforcement.backend()
    backend.complete(_request(ORDINARY_PROMPT))

    placement = backend.last_placement
    assert placement is not None
    assert placement.substrate == "local-gpu"
    assert enforcement.klass is SensitivityClass.INTERNAL

    entry = enforcement.ledger.entries()[-1]
    assert entry.klass == "internal"
    assert entry.substrate == "local-gpu"


def test_the_frontier_is_reachable_only_for_material_declared_public(home, tmp_path):
    """The other half: this must not become "nothing ever leaves", which would
    make the class ladder theatre. With a public floor the same prompt goes to
    the substrate the policy prefers."""
    path = tmp_path / "policy.yaml"
    path.write_text(
        POLICY_WITH_A_FRONTIER.replace(
            '  internal:\n    paths: ["~/**"]\n    default: true',
            '  internal:\n    paths: ["~/**"]',
        ).replace("  public: {}", "  public:\n    default: true")
    )

    enforcement = Enforcement.for_run(
        policy_file=path, ledger_path=tmp_path / "ledger.jsonl", probe=False, fsync=False
    )
    backend = enforcement.backend()
    backend.complete(_request(ORDINARY_PROMPT))

    assert backend.last_placement.substrate == "frontier"


def test_a_recognised_identifier_still_raises_the_class_above_the_floor(home, tmp_path):
    """Raising above the floor has to keep working — the floor is a minimum, not
    a replacement for classification."""
    path = tmp_path / "policy.yaml"
    path.write_text(POLICY_WITH_A_FRONTIER)

    enforcement = Enforcement.for_run(
        policy_file=path, ledger_path=tmp_path / "ledger.jsonl", probe=False, fsync=False
    )
    backend = enforcement.backend()
    backend.complete(_request("ecco la chiave:\n-----BEGIN RSA PRIVATE KEY-----"))

    assert enforcement.klass is SensitivityClass.RESTRICTED
    assert backend.last_placement.substrate == "local-gpu"


def test_the_shipped_policy_registers_nothing_that_could_send_material_away():
    """Defence in depth: even with the floor wrong, `annona policy init` must not
    hand anyone a substrate outside their machine."""
    policy = default_policy()
    assert [s.jurisdiction for s in policy.substrates] == ["on-prem"]
    for rule in policy.rules:
        assert set(rule.allow) <= {"local-gpu"}


def test_the_written_policy_matches_the_built_in_one(tmp_path):
    """`annona policy init` writes what `default_policy()` returns — otherwise
    the file a user reads and the object the tests check are two products."""
    from runner.policy.loader import write_default_policy

    target = write_default_policy(tmp_path / "policy.yaml")
    written = load_policy(target)

    assert written.default_class is default_policy().default_class
    assert [s.id for s in written.substrates] == [s.id for s in default_policy().substrates]
