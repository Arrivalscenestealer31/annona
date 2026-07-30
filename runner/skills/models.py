"""Skills: folders of instructions that carry a jurisdiction (layer L2).

A skill is what Anthropic's Agent Skills are — a directory with a ``SKILL.md``
whose front matter names it and whose body teaches a model how to do one thing
well, loaded only when it is needed rather than pasted into every prompt.

Annona adds one field to that idea, and it is the only interesting part:

    pins: local

A skill can declare what it *touches*, and the kernel enforces the consequence.
``image-report`` is a generic instruction for reading an image and producing a
structured note — and the images people actually point it at are radiology
studies, damage claims and identity documents. Declaring ``pins: local`` means
that the moment the skill is loaded, the run is restricted for the rest of its
life: no later turn can be placed on a frontier API, whatever the prompt looks
like by then.

That is the difference between a prompt library and a capability system. The
instructions are portable and boring on purpose; the guarantee is not in the
text, it is in the runtime that refuses to place the work anywhere else.

Front matter, in full::

    ---
    name: image-report
    description: Read an image and produce a structured, factual report.
    version: 1
    requires: [vision]        # substrate capabilities the skill needs
    tools: [document_reader]  # tools it expects to be allowed
    pins: local               # local | none — where the run may go afterwards
    ---

Everything below the front matter is the instruction, and the model sees it only
after asking for it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from runner.kernel.types import SensitivityClass

__all__ = ["Skill", "SkillRequirements"]


@dataclass(frozen=True, slots=True)
class SkillRequirements:
    """What a skill needs from the deployment before it can be used."""

    vision: bool = False
    """The substrate must be able to read images."""

    tools: tuple[str, ...] = ()
    """Tools the skill expects. A skill whose tools are all denied is unusable,
    and saying so at load time is better than a model discovering it mid-run."""

    min_context: int = 0
    """Minimum context window, for skills that work over whole folders."""


@dataclass(frozen=True, slots=True)
class Skill:
    """One skill: a name, a description, an instruction, and its jurisdiction."""

    name: str
    description: str
    body: str
    version: int = 1
    requires: SkillRequirements = field(default_factory=SkillRequirements)
    pins: str = "none"
    source: Path | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def pins_local(self) -> bool:
        """Whether loading this skill confines the rest of the run to the perimeter."""
        return self.pins == "local"

    @property
    def floor(self) -> SensitivityClass:
        """The class the working set is raised to when this skill is loaded.

        ``restricted`` for a pinned skill, because that is the class every
        sensible policy keeps on-prem, and ``public`` otherwise — which changes
        nothing, since the working set only ever goes up.
        """
        return SensitivityClass.RESTRICTED if self.pins_local else SensitivityClass.PUBLIC

    def summary(self) -> str:
        """The one line a model sees before deciding whether to load the skill.

        Progressive disclosure is not a token-saving trick here: a prompt that
        contains every instruction also contains every instruction in the
        transcript, and the transcript is what crosses. Keeping bodies out of it
        until they are needed keeps the payload small *and* keeps the perimeter's
        classification honest.
        """
        marks = []
        if self.pins_local:
            marks.append("local only")
        if self.requires.vision:
            marks.append("vision")
        suffix = f"  [{', '.join(marks)}]" if marks else ""
        return f"{self.name} — {self.description}{suffix}"

    def satisfied_by(
        self,
        *,
        vision: bool,
        allowed_tools: Sequence[str],
        context_window: int = 0,
    ) -> tuple[bool, str]:
        """Whether this deployment can actually run the skill."""
        if self.requires.vision and not vision:
            return False, "no registered substrate can read images"

        missing = [t for t in self.requires.tools if t not in allowed_tools]
        if missing:
            return False, f"the policy does not allow: {', '.join(missing)}"

        if (
            self.requires.min_context
            and context_window
            and context_window < self.requires.min_context
        ):
            return False, (
                f"needs a context window of {self.requires.min_context}, "
                f"the best available is {context_window}"
            )

        return True, ""
