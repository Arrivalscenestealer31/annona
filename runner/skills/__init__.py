"""L2 — skills: instructions that carry a jurisdiction.

Anthropic's Agent Skills format (a directory with ``SKILL.md``, front matter and
prose, loaded on demand) plus one field this project needs: ``pins: local``,
which makes loading a skill a placement decision the kernel enforces.
"""

from runner.skills.install import CLAUDE_SKILLS_DIR, install_skill, resolve_source
from runner.skills.loader import BUNDLED_SKILLS_DIR, discover_skills, load_skill, skills_dirs
from runner.skills.models import Skill, SkillRequirements
from runner.skills.registry import SKILL_TOOL, SkillfulExecutor, SkillRegistry

__all__ = [
    "BUNDLED_SKILLS_DIR",
    "CLAUDE_SKILLS_DIR",
    "SKILL_TOOL",
    "Skill",
    "SkillRegistry",
    "SkillRequirements",
    "SkillfulExecutor",
    "discover_skills",
    "install_skill",
    "load_skill",
    "resolve_source",
    "skills_dirs",
]
