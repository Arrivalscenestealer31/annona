"""Classification, symlinks, and the invariant the whole product rests on.

The monotonicity invariant — a run's class never decreases — is what makes
"the transcript is the leak" a solved problem rather than an observation. It is
tested here exhaustively rather than by example, because the failure it prevents
is silent: a run that read a client file and then, three steps later, is placed
on a frontier API because the *current* step looks innocuous.
"""

from __future__ import annotations

import itertools
import os

import pytest

from runner.kernel.types import SensitivityClass, ToolCall, ToolResult
from runner.policy.classifier import PolicyClassifier, WorkingSet, path_like_values
from runner.policy.loader import parse_policy

pytestmark = pytest.mark.unit


def build_policy(tmp_path):
    return parse_policy(
        {
            "version": 1,
            "default": "deny",
            "classes": {
                "restricted": {
                    "paths": [f"{tmp_path}/clients/**"],
                    "patterns": [r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]"],
                },
                "internal": {"paths": [f"{tmp_path}/work/**"]},
                "public": {"default": True},
            },
            "substrates": [{"id": "local", "kind": "echo", "max_class": "restricted"}],
            "rules": [{"match": {"class": "public"}, "allow": ["local"]}],
        }
    )


@pytest.fixture
def classifier(tmp_path):
    (tmp_path / "clients").mkdir()
    (tmp_path / "work").mkdir()
    (tmp_path / "open").mkdir()
    return PolicyClassifier(build_policy(tmp_path))


# ── Paths ─────────────────────────────────────────────────────────────────────


def test_a_protected_directory_makes_a_path_restricted(classifier, tmp_path):
    assert classifier.classify_path(f"{tmp_path}/clients/BG-114.pdf") is SensitivityClass.RESTRICTED


def test_an_internal_directory_makes_a_path_internal(classifier, tmp_path):
    assert classifier.classify_path(f"{tmp_path}/work/notes.md") is SensitivityClass.INTERNAL


def test_an_unmatched_path_takes_the_policy_default(classifier, tmp_path):
    assert classifier.classify_path(f"{tmp_path}/open/readme.md") is SensitivityClass.PUBLIC


def test_the_directory_itself_matches_its_own_glob(classifier, tmp_path):
    """`clients/**` has to cover `clients`, or every policy needs two lines."""
    assert classifier.classify_path(f"{tmp_path}/clients") is SensitivityClass.RESTRICTED


def test_a_symlink_is_classified_by_its_target(classifier, tmp_path):
    """The cheapest way to walk a file out of a protected directory.

    A link in an unprotected folder pointing at a client file must not become
    public by virtue of where the link lives. This is the test that stops the
    perimeter from being a naming convention.
    """
    secret = tmp_path / "clients" / "BG-114.pdf"
    secret.write_text("client matter")
    link = tmp_path / "open" / "innocuous.pdf"
    os.symlink(secret, link)

    assert classifier.classify_path(str(link)) is SensitivityClass.RESTRICTED


def test_relative_and_absolute_forms_agree(classifier, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert classifier.classify_path("clients/x.pdf") is SensitivityClass.RESTRICTED


def test_traversal_does_not_escape_classification(classifier, tmp_path):
    """`work/../clients/x` is a client file however it is spelled."""
    tricky = f"{tmp_path}/work/../clients/x.pdf"
    assert classifier.classify_path(tricky) is SensitivityClass.RESTRICTED


# ── Content ───────────────────────────────────────────────────────────────────


def test_an_identifier_in_content_raises_the_class(classifier):
    assert classifier.classify_content("il codice è RSSMRA85T10A562S") is SensitivityClass.RESTRICTED


def test_ordinary_content_is_public(classifier):
    assert classifier.classify_content("the quarterly report is late") is SensitivityClass.PUBLIC


def test_empty_content_is_public(classifier):
    assert classifier.classify_content("") is SensitivityClass.PUBLIC


def test_a_tool_result_is_classified_by_what_it_returned(classifier):
    result = ToolResult(
        call_id="1",
        name="document_reader",
        content={"text": "cliente RSSMRA85T10A562S, pratica aperta"},
    )
    assert classifier.classify_result(result) is SensitivityClass.RESTRICTED


def test_a_nested_tool_result_is_still_classified(classifier):
    result = ToolResult(
        call_id="1",
        name="explorer",
        content={"files": [{"preview": "RSSMRA85T10A562S"}]},
    )
    assert classifier.classify_result(result) is SensitivityClass.RESTRICTED


# ── Calls ─────────────────────────────────────────────────────────────────────


def test_a_call_is_classified_by_the_path_it_names(classifier, tmp_path):
    call = ToolCall(id="1", name="document_reader", arguments={"path": f"{tmp_path}/clients/x.pdf"})
    assert classifier.classify_call(call) is SensitivityClass.RESTRICTED


def test_path_arguments_are_found_by_name_not_by_shape():
    """A URL is not a path, and a classifier that says otherwise is noise."""
    assert path_like_values({"url": "https://example.com/a/b"}) == ()
    assert path_like_values({"path": "/tmp/x"}) == ("/tmp/x",)
    assert path_like_values({"target": {"path": "/tmp/y"}}) == ("/tmp/y",)


def test_a_call_with_no_path_is_classified_by_its_arguments(classifier):
    call = ToolCall(id="1", name="shell", arguments={"command": "echo RSSMRA85T10A562S"})
    assert classifier.classify_call(call) is SensitivityClass.RESTRICTED


# ── The invariant ─────────────────────────────────────────────────────────────


def test_working_set_starts_public():
    assert WorkingSet().klass is SensitivityClass.PUBLIC


@pytest.mark.parametrize(
    "sequence",
    list(itertools.permutations(list(SensitivityClass), 3)),
    ids=lambda seq: "→".join(k.label for k in seq) if isinstance(seq, tuple) else str(seq),
)
def test_the_working_set_never_goes_down(sequence):
    """Exhaustive over every ordering of every class.

    Not a sampled property: there are six orderings of three classes, so the
    invariant is checked over the whole space. Whatever order material arrives
    in, the class at the end is the maximum, and it never dips in between.
    """
    working_set = WorkingSet()
    seen: list[SensitivityClass] = []

    for klass in sequence:
        current = working_set.observe(f"source-{klass.label}", klass)
        seen.append(current)
        assert current == max(sequence[: len(seen)])

    assert working_set.klass == max(sequence)
    assert seen == sorted(seen), "the class dipped mid-run, which must be impossible"


def test_the_working_set_names_what_raised_it():
    """`annona why` prints this sentence; it has to be the true one."""
    working_set = WorkingSet()
    working_set.observe("/work/notes.md", SensitivityClass.INTERNAL)
    working_set.observe("/clients/BG-114.pdf", SensitivityClass.RESTRICTED)
    working_set.observe("/tmp/readme", SensitivityClass.PUBLIC)

    assert working_set.klass is SensitivityClass.RESTRICTED
    assert "/clients/BG-114.pdf" in working_set.reason
    assert "restricted" in working_set.reason


def test_provenance_keeps_everything_observed():
    working_set = WorkingSet()
    working_set.observe("a", SensitivityClass.PUBLIC)
    working_set.observe("b", SensitivityClass.RESTRICTED)
    assert [p[0] for p in working_set.provenance] == ["a", "b"]


def test_classes_are_ordered_and_comparable():
    assert SensitivityClass.PUBLIC < SensitivityClass.INTERNAL < SensitivityClass.RESTRICTED
    assert max(SensitivityClass.PUBLIC, SensitivityClass.RESTRICTED) is SensitivityClass.RESTRICTED


@pytest.mark.parametrize("bad", ["confidential", "", "secret", 7, None, True])
def test_unknown_class_values_raise_rather_than_defaulting(bad):
    with pytest.raises(ValueError):
        SensitivityClass.parse(bad)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("public", SensitivityClass.PUBLIC),
        ("INTERNAL", SensitivityClass.INTERNAL),
        (" restricted ", SensitivityClass.RESTRICTED),
        (2, SensitivityClass.RESTRICTED),
        (SensitivityClass.INTERNAL, SensitivityClass.INTERNAL),
    ],
)
def test_class_parsing_accepts_what_a_policy_file_contains(given, expected):
    assert SensitivityClass.parse(given) is expected
