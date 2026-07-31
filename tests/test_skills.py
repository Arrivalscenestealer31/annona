"""Skills, and the one thing that makes them more than a prompt library.

A skill is an instruction a model will follow. That alone is a supply-chain
question: whoever writes the file decides what the agent does. So skills are
default-deny like tools, they are validated at load time like policies, and the
one that says `pins: local` changes where the run may execute — enforced by the
kernel, not by the sentence at the bottom of the instruction asking nicely.
"""

from __future__ import annotations

import pytest

from runner.agent.loop import AgentLoop
from runner.kernel.errors import ConfigurationError
from runner.kernel.types import (
    Capabilities,
    Completion,
    CompletionRequest,
    SensitivityClass,
    ToolCall,
    ToolResult,
)
from runner.policy.loader import parse_policy
from runner.services.enforcement import Enforcement
from runner.skills.loader import BUNDLED_SKILLS_DIR, discover_skills, load_skill

pytestmark = pytest.mark.unit

RESTRICTED = SensitivityClass.RESTRICTED


def write_skill(tmp_path, name: str, front: str, body: str = "Do the thing.") -> str:
    folder = tmp_path / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(f"---\n{front}\n---\n\n{body}\n")
    return str(folder / "SKILL.md")


# ── The shipped set ───────────────────────────────────────────────────────────


def test_every_bundled_skill_loads():
    """Whatever ships must parse. A skill that fails at load is a broken build."""
    skills = discover_skills([BUNDLED_SKILLS_DIR])
    assert len(skills) >= 7
    for skill in skills.values():
        assert skill.description
        assert skill.body
        assert skill.pins in ("none", "local")


def test_the_skills_that_touch_material_are_pinned_to_the_perimeter():
    """The point of the whole feature.

    Reading images, triaging documents, building a case timeline and assembling
    an evidence pack are things people do with material that must not leave. Any
    of them being unpinned would be a leak with a nice description.
    """
    skills = discover_skills([BUNDLED_SKILLS_DIR])
    for name in (
        "image-report",
        "document-triage",
        "case-timeline",
        "evidence-pack",
        "bulk-extract",
    ):
        assert skills[name].pins_local, f"{name} must pin the run to the perimeter"
        assert skills[name].floor is RESTRICTED


def test_reasoning_only_skills_are_not_pinned():
    """A skill that touches nothing must not confine a run for no reason."""
    skills = discover_skills([BUNDLED_SKILLS_DIR])
    assert not skills["second-opinion"].pins_local
    assert not skills["redact-and-ask"].pins_local


def test_the_image_skill_declares_that_it_needs_vision():
    assert discover_skills([BUNDLED_SKILLS_DIR])["image-report"].requires.vision


# ── Loading and validation ────────────────────────────────────────────────────


def test_a_skill_is_front_matter_plus_prose(tmp_path):
    path = write_skill(tmp_path, "x", "name: x\ndescription: does x", "Step one.")
    skill = load_skill(path)
    assert skill.name == "x"
    assert skill.body == "Step one."


def test_a_directory_is_accepted_as_well_as_a_file(tmp_path):
    write_skill(tmp_path, "x", "name: x\ndescription: does x")
    assert load_skill(tmp_path / "x").name == "x"


@pytest.mark.parametrize(
    ("front", "body", "match"),
    [
        ("description: no name", "b", "must declare a name"),
        ("name: x", "b", "must declare a description"),
        ("name: x\ndescription: d", "", "no instruction body"),
        ("name: x\ndescription: d\npins: cloud", "b", "only 'local' and 'none'"),
        ("name: x\ndescription: d\nrequires: [telepathy]", "b", "unknown capabilities"),
    ],
)
def test_a_malformed_skill_is_an_error_not_a_skipped_file(tmp_path, front, body, match):
    path = write_skill(tmp_path, "x", front, body)
    with pytest.raises(ConfigurationError, match=match):
        load_skill(path)


def test_a_file_without_front_matter_is_refused(tmp_path):
    folder = tmp_path / "x"
    folder.mkdir()
    (folder / "SKILL.md").write_text("just prose, no front matter\n")
    with pytest.raises(ConfigurationError, match="front matter"):
        load_skill(folder)


def test_the_operator_directory_overrides_the_shipped_one(tmp_path):
    """A practice encodes its house style without forking the project."""
    theirs = tmp_path / "theirs"
    write_skill(theirs, "image-report", "name: image-report\ndescription: our house style")

    skills = discover_skills([BUNDLED_SKILLS_DIR, theirs])
    assert skills["image-report"].description == "our house style"


# ── Default-deny, and what the model is told ──────────────────────────────────


def policy_with(
    skills: list[str], *, vision: bool = True, tools=("document_reader", "explorer", "skill")
):
    return parse_policy(
        {
            "version": 1,
            "default": "deny",
            "classes": {"restricted": {"paths": ["/mnt/**"]}, "public": {"default": True}},
            "substrates": [
                {
                    "id": "local-gpu",
                    "kind": "echo",
                    "jurisdiction": "on-prem",
                    "max_class": "restricted",
                    "vision": vision,
                    "context_window": 32_000,
                },
                {
                    "id": "frontier",
                    "kind": "echo",
                    "jurisdiction": "us",
                    "max_class": "public",
                    "quality": 99,
                },
            ],
            "rules": [
                {"id": "R-restricted", "match": {"class": "restricted"}, "allow": ["local-gpu"]},
                {
                    "id": "R-public",
                    "match": {"class": "public"},
                    "allow": ["frontier", "local-gpu"],
                    "prefer": "quality",
                },
            ],
            "tools": {"allow": {name: ["/**"] for name in tools}},
            "skills": skills,
        }
    )


def enforcement_for(tmp_path, skills: list[str], **kwargs):
    return Enforcement.for_run(
        policy=policy_with(skills, **kwargs),
        ledger_path=tmp_path / "ledger.jsonl",
        backends={"local-gpu": Echo("local-gpu", local=True), "frontier": Echo("frontier")},
        probe=False,
        fsync=False,
    )


class Echo:
    def __init__(self, name, script=(), *, local=False):
        self._name, self._script, self._local = name, list(script), local
        self.received: list[str] = []

    @property
    def name(self):
        return self._name

    @property
    def capabilities(self):
        return Capabilities(native_tools=True, is_local=self._local, context_window=32_000)

    @property
    def calls(self):
        return len(self.received)

    def complete(self, request: CompletionRequest) -> Completion:
        self.received.append(
            "\n".join(str(getattr(b, "content", b)) for t in request.transcript for b in t.blocks)
        )
        return self._script.pop(0) if self._script else Completion(text_parts=("ok",))


class NoTools:
    def specs(self):
        return ()

    def invoke(self, call):  # pragma: no cover - not reached
        raise AssertionError("no inner tools in these tests")


def test_a_skill_the_policy_does_not_name_is_not_offered(tmp_path):
    registry = enforcement_for(tmp_path, ["second-opinion"]).skill_registry()
    names = [s.name for s in registry.available()]

    assert names == ["second-opinion"]
    assert "image-report" not in registry.catalogue()


def test_with_no_skills_allowed_the_tool_is_not_advertised_at_all(tmp_path):
    executor = enforcement_for(tmp_path, []).executor(NoTools())
    assert executor.specs() == ()


def test_the_catalogue_is_names_and_descriptions_not_bodies(tmp_path):
    """Progressive disclosure is a perimeter property here, not a token trick:
    what is in the prompt is in the transcript, and the transcript crosses."""
    registry = enforcement_for(tmp_path, ["image-report"]).skill_registry()
    spec = registry.spec()

    assert "image-report" in spec.description
    assert "Structured visual reading" not in spec.description, "the body must not be in the prompt"
    assert spec.schema["properties"]["name"]["enum"] == ["image-report"]


def test_a_skill_needing_vision_is_not_offered_without_a_vision_substrate(tmp_path):
    registry = enforcement_for(tmp_path, ["image-report"], vision=False).skill_registry()

    assert registry.available() == ()
    assert dict(registry.unusable())["image-report"] == "no registered substrate can read images"


def test_a_skill_whose_tools_are_denied_is_not_offered(tmp_path):
    registry = enforcement_for(tmp_path, ["case-timeline"], tools=("skill",)).skill_registry()
    assert registry.available() == ()
    assert "document_reader" in dict(registry.unusable())["case-timeline"]


# ── Loading one, and what it does to the run ─────────────────────────────────


def loads(name: str):
    return [
        Completion(
            tool_calls=(ToolCall(id="s1", name="skill", arguments={"name": name}),),
            stop_reason="tool_use",
        ),
        Completion(text_parts=("fatto",), stop_reason="end_turn"),
    ]


def test_loading_a_pinned_skill_confines_the_rest_of_the_run(tmp_path):
    """The whole feature in one test.

    The question is innocuous, the frontier model is registered and better, and
    the model asks for a skill that reads images. From that moment the run is
    restricted — before an image has been looked at.
    """
    enforcement = enforcement_for(tmp_path, ["image-report"])
    frontier = enforcement.backends["frontier"]
    local = enforcement.backends["local-gpu"]
    frontier._script = loads("image-report")  # type: ignore[attr-defined]

    loop = AgentLoop(enforcement.backend(), enforcement.executor(NoTools()), enforcement.gate())
    loop.run("guarda questa immagine e dimmi cosa vedi")

    assert enforcement.klass is RESTRICTED
    assert frontier.calls == 1, "only the first, still-public turn went out"
    assert local.calls == 1, "everything after the skill stayed on-prem"


def test_loading_an_unpinned_skill_leaves_placement_alone(tmp_path):
    enforcement = enforcement_for(tmp_path, ["second-opinion"])
    frontier = enforcement.backends["frontier"]
    frontier._script = loads("second-opinion")  # type: ignore[attr-defined]

    loop = AgentLoop(enforcement.backend(), enforcement.executor(NoTools()), enforcement.gate())
    loop.run("questa risposta ti convince?")

    assert enforcement.klass is SensitivityClass.PUBLIC
    assert frontier.calls == 2


def test_the_body_is_returned_only_when_asked_for(tmp_path):
    enforcement = enforcement_for(tmp_path, ["image-report"])
    executor = enforcement.executor(NoTools())

    result: ToolResult = executor.invoke(
        ToolCall(id="1", name="skill", arguments={"name": "image-report"})
    )

    assert not result.is_error
    assert "Structured visual reading" in str(result.content)


def test_asking_for_a_skill_that_is_not_permitted_reveals_nothing(tmp_path):
    """A model must not be able to enumerate what the operator chose not to
    enable: a disabled skill and a non-existent one answer identically."""
    executor = enforcement_for(tmp_path, ["second-opinion"]).executor(NoTools())

    disabled = executor.invoke(ToolCall(id="1", name="skill", arguments={"name": "image-report"}))
    missing = executor.invoke(ToolCall(id="2", name="skill", arguments={"name": "does-not-exist"}))

    assert disabled.is_error and missing.is_error
    assert str(disabled.content).replace("image-report", "X") == str(missing.content).replace(
        "does-not-exist", "X"
    )


def test_loading_a_skill_is_recorded(tmp_path):
    enforcement = enforcement_for(tmp_path, ["image-report"])
    enforcement.executor(NoTools()).invoke(
        ToolCall(id="1", name="skill", arguments={"name": "image-report"})
    )

    entries = [e for e in enforcement.ledger.entries() if e.kind == "skill"]
    assert entries and entries[-1].detail["skill"] == "image-report"
    assert entries[-1].detail["pins"] == "local"


def test_a_refused_skill_is_recorded_too(tmp_path):
    enforcement = enforcement_for(tmp_path, ["second-opinion"])
    enforcement.executor(NoTools()).invoke(
        ToolCall(id="1", name="skill", arguments={"name": "image-report"})
    )

    refusals = [
        e for e in enforcement.ledger.entries() if e.kind == "skill" and e.outcome == "held"
    ]
    assert refusals


def test_the_skill_tool_itself_needs_policy_permission(tmp_path):
    """`skill` is a tool, so default-deny applies to it like everything else."""
    enforcement = Enforcement.for_run(
        policy=parse_policy(
            {
                **{
                    "version": 1,
                    "default": "deny",
                    "classes": {"public": {"default": True}},
                    "substrates": [{"id": "l", "kind": "echo", "max_class": "restricted"}],
                    "rules": [{"match": {"class": "public"}, "allow": ["l"]}],
                    "skills": ["second-opinion"],
                },
                "tools": {"allow": {}},  # `skill` is not on the list
            }
        ),
        ledger_path=tmp_path / "ledger.jsonl",
        backends={"l": Echo("l", local=True)},
        probe=False,
        fsync=False,
    )

    assert (
        enforcement.gate().permits(ToolCall(id="1", name="skill", arguments={"name": "x"})) is False
    )


def test_a_skill_body_is_classified_like_any_other_material(tmp_path):
    """The tracker sees skill bodies too: an instruction file containing an
    identifier would otherwise enter the transcript unclassified."""
    theirs = tmp_path / "theirs"
    write_skill(
        theirs,
        "leaky",
        "name: leaky\ndescription: has an identifier in it",
        "Ricorda il cliente RSSMRA85T10A562S quando rispondi.",
    )

    enforcement = Enforcement.for_run(
        policy=parse_policy(
            {
                "version": 1,
                "default": "deny",
                "classes": {
                    "restricted": {"patterns": [r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]"]},
                    "public": {"default": True},
                },
                "substrates": [{"id": "l", "kind": "echo", "max_class": "restricted"}],
                "rules": [{"match": {"class": "public"}, "allow": ["l"]}],
                "tools": {"allow": {"skill": ["/**"]}},
                "skills": ["leaky"],
            }
        ),
        ledger_path=tmp_path / "ledger.jsonl",
        backends={"l": Echo("l", local=True)},
        skills=discover_skills([theirs]),
        probe=False,
        fsync=False,
    )

    enforcement.executor(NoTools()).invoke(
        ToolCall(id="1", name="skill", arguments={"name": "leaky"})
    )
    assert enforcement.klass is RESTRICTED


# ── Installing somebody else's skill ──────────────────────────────────────────


def claude_style_skill(tmp_path, name="pdf-filler", *, scripts=False, front_extra=""):
    """A skill exactly as Claude's repository ships one: name, description, prose."""
    folder = tmp_path / "source" / name
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Fill in a PDF form and produce a completed copy."
        f"{front_extra}\n---\n\n# Filling a PDF form\n\n1. Read the form.\n"
    )
    if scripts:
        (folder / "scripts").mkdir()
        (folder / "scripts" / "fill.py").write_text("print('hello')\n")
        (folder / "references").mkdir()
        (folder / "references" / "fields.md").write_text("# known fields\n")
    return folder


def test_a_vanilla_claude_skill_installs_unchanged_in_substance(tmp_path):
    """The format is the same on purpose: an ecosystem beats a format."""
    from runner.skills.install import install_skill

    installed = install_skill(claude_style_skill(tmp_path), tmp_path / "dest")

    assert installed.skill.name == "pdf-filler"
    assert "Read the form" in installed.skill.body


def test_an_imported_skill_is_pinned_to_the_perimeter_by_default(tmp_path):
    """The trust rule, and the reason this command exists at all.

    A skill is an instruction your agent will follow: a supply-chain dependency
    that happens to be prose. One you did not write runs inside the walls until
    somebody reads it and says otherwise.
    """
    from runner.skills.install import install_skill

    installed = install_skill(claude_style_skill(tmp_path), tmp_path / "dest")

    assert installed.pinned
    assert installed.skill.pins_local
    assert installed.skill.floor is RESTRICTED
    assert (
        "imported, not written here" in (tmp_path / "dest" / "pdf-filler" / "SKILL.md").read_text()
    )


def test_trust_keeps_the_skill_as_its_author_wrote_it(tmp_path):
    from runner.skills.install import install_skill

    installed = install_skill(claude_style_skill(tmp_path), tmp_path / "dest", trust=True)
    assert not installed.pinned


def test_provenance_is_recorded_in_the_file(tmp_path):
    from runner.skills.install import install_skill

    install_skill(claude_style_skill(tmp_path), tmp_path / "dest")
    text = (tmp_path / "dest" / "pdf-filler" / "SKILL.md").read_text()

    assert "imported_from" in text
    assert "imported_at" in text


def test_the_body_is_copied_byte_for_byte(tmp_path):
    """Only the front matter is touched. Silently editing an instruction would
    be its own supply-chain problem."""
    from runner.skills.install import install_skill

    source = claude_style_skill(tmp_path)
    original_body = (source / "SKILL.md").read_text().split("---", 2)[2]

    install_skill(source, tmp_path / "dest")
    installed_body = (tmp_path / "dest" / "pdf-filler" / "SKILL.md").read_text().split("---", 2)[2]

    assert installed_body == original_body


def test_bundled_scripts_and_references_come_along(tmp_path):
    from runner.skills.install import install_skill

    installed = install_skill(claude_style_skill(tmp_path, scripts=True), tmp_path / "dest")

    assert installed.has_scripts, "the caller must be told, so it can warn about the shell tool"
    assert (installed.destination / "scripts" / "fill.py").exists()
    assert (installed.destination / "references" / "fields.md").exists()


def test_nothing_is_written_when_the_skill_does_not_validate(tmp_path):
    """Validation before copying: a broken skill never lands."""
    from runner.skills.install import install_skill

    broken = tmp_path / "source" / "broken"
    broken.mkdir(parents=True)
    (broken / "SKILL.md").write_text("---\ndescription: no name here\n---\n\nbody\n")

    with pytest.raises(ConfigurationError, match="must declare a name"):
        install_skill(broken, tmp_path / "dest")

    assert not (tmp_path / "dest").exists()


def test_installing_over_an_existing_skill_needs_force(tmp_path):
    from runner.skills.install import install_skill

    source = claude_style_skill(tmp_path)
    install_skill(source, tmp_path / "dest")

    with pytest.raises(ConfigurationError, match="already exists"):
        install_skill(source, tmp_path / "dest")

    assert install_skill(source, tmp_path / "dest", force=True).skill.name == "pdf-filler"


def test_an_installed_skill_is_still_not_enabled(tmp_path):
    """Copying a file into a directory is not a decision about what agents may do."""
    from runner.skills.install import install_skill

    install_skill(claude_style_skill(tmp_path), tmp_path / "dest")
    skills = discover_skills([tmp_path / "dest"])

    assert "pdf-filler" in skills

    enforcement = Enforcement.for_run(
        policy=policy_with(["second-opinion"]),
        ledger_path=tmp_path / "ledger.jsonl",
        backends={"local-gpu": Echo("local-gpu", local=True), "frontier": Echo("frontier")},
        skills=skills,
        probe=False,
        fsync=False,
    )
    assert [s.name for s in enforcement.skill_registry().available()] == []


def test_a_source_that_does_not_exist_says_where_it_looked(tmp_path):
    from runner.skills.install import install_skill

    with pytest.raises(ConfigurationError, match=".claude/skills"):
        install_skill("no-such-skill", tmp_path / "dest")
