"""System prompt construction for agentic runs (layer L3).

Kept separate from the loop for one practical reason: the prompt is the most
frequently edited part of an agent and the least testable in place. With it here,
``docs/research`` Lab Note 04 — ablating prompt sections to find the dead weight —
is a change to one function and a test, not surgery on control flow.

The text is byte-for-byte the prompt the runner has always used. Phase 0 changes
no behaviour, and a prompt is behaviour.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

__all__ = ["AGENT_ROLE", "LANGUAGE_RULE", "build_system_prompt"]

AGENT_ROLE = (
    "You are an advanced local agent running on the user's machine. "
    "You have access to tools to explore the filesystem, read documents of any format "
    "(PDF, DOCX, XLSX, CSV, code files), execute shell commands, and analyze content. "
    "When given a task, think step by step and use the appropriate tools. "
    "Be thorough: explore before reading, read before summarizing. "
)

LANGUAGE_RULE = (
    "Answer in the language the user wrote in. If the request is in Italian, the "
    "entire reply is in Italian — including when a tool fails, when permission is "
    "denied, and whatever language the documents you read are written in. Never "
    "switch language."
)
"""Kept out of :data:`AGENT_ROLE` so it can be placed last.

Small open-weight models drift language once tool results in another language
enter the transcript. Observed twice on qwen2.5:14b: an Italian question about
an Italian folder, answered in Thai — the content correct, the answer useless.
The rule was already in the prompt when that happened; what changed is where it
sits. Instructions at the end of a system prompt survive a long transcript;
instructions in the middle are what the model has already stopped attending to
by turn three. A deployment that is sovereign is a deployment whose model is
small enough for this to matter.
"""


def build_system_prompt(context: Mapping[str, Any] | None) -> str:
    """Compose the system prompt for a run.

    Args:
        context: Free-form run context injected verbatim. Serialised with
            ``default=str`` so a Path or a datetime in the context cannot fail a
            run before it starts.

    Returns:
        The full system prompt: role, context, then the language rule last.
    """
    if context:
        try:
            rendered = json.dumps(context)
        except (TypeError, ValueError):
            rendered = json.dumps(context, default=str)
    else:
        rendered = "none"

    return f"{AGENT_ROLE}Context: {rendered}\n\n{LANGUAGE_RULE}"
