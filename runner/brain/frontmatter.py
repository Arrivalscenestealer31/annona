"""YAML frontmatter for vault notes.

Before this module the markdown files held the note body and nothing else: the
title, the tags and the sync state lived only in the SQLite index, and files were
named by uuid. So "walk away from the runner and keep your data" was true of the
prose and false of everything around it — delete the index and you kept a folder
of anonymous text files.

Frontmatter fixes that. Every note is now self-describing, and the format is the
one Obsidian, Jekyll, Hugo and every static site generator already read.

**The writer is strict, the reader is tolerant.** The writer emits a fixed field
order with an explicit style, so the same note always produces the same bytes and
a vault stays diffable in Git. The reader accepts whatever a human typed, because
these files exist to be edited by hand — that is the whole point of the format.

The SQLite index stays: it answers queries, and rebuilding it from the vault is
cheap. But the markdown is now the record of truth, and the index is derived.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import yaml

__all__ = ["FIELD_ORDER", "dump", "has_frontmatter", "parse", "split"]

_DELIMITER = "---"

# The `\r?\n?` after the closing delimiter swallows the single blank line the
# writer puts between frontmatter and body, so a body round-trips byte-for-byte.
# A body that genuinely begins with a blank line loses it — the same trade every
# frontmatter parser makes, and the alternative is every note gaining a stray
# newline on each read.
_FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(?P<meta>.*?)\r?\n---[ \t]*(?:\r?\n\r?\n?(?P<body>.*))?\Z",
    re.DOTALL,
)

FIELD_ORDER = (
    "id",
    "title",
    "tags",
    "created",
    "updated",
    "sync",
    "synced_at",
    "cloud_message_id",
    "cloud_cluster_id",
    "cloud_cluster_name",
)
"""Emission order.

Fixed rather than alphabetical so a human reads identity, then meaning, then
machinery — and so the diff of an edited note shows the edit rather than a
reshuffle.
"""


def has_frontmatter(text: str) -> bool:
    """Whether ``text`` opens with a frontmatter block."""
    return _FRONTMATTER_RE.match(text) is not None


def split(text: str) -> tuple[str | None, str]:
    """Separate the raw frontmatter block from the body.

    Returns ``(None, text)`` when there is no frontmatter, so a pre-migration
    note reads as pure body — which is exactly what it is.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    return match.group("meta"), match.group("body") or ""


def parse(text: str) -> tuple[dict[str, Any], str]:
    """Read a note into ``(metadata, body)``.

    Malformed YAML is not an error: the file is returned as a body with empty
    metadata. A note the parser cannot understand is still a note, and losing
    someone's prose to a stray colon would be unforgivable.
    """
    raw, body = split(text)
    if raw is None:
        return {}, body

    try:
        loaded = yaml.safe_load(raw)
    except yaml.YAMLError:
        return {}, body

    if not isinstance(loaded, Mapping):
        return {}, body

    return {str(k): v for k, v in loaded.items()}, body


def dump(metadata: Mapping[str, Any], body: str) -> str:
    """Render a note with frontmatter.

    Empty and ``None`` values are omitted rather than written as blanks: a note
    that has never synced should not carry four empty cloud fields explaining
    that nothing happened.
    """
    fields = _ordered(metadata)
    if not fields:
        return body

    lines = [_DELIMITER]
    for key, value in fields:
        lines.append(_emit(key, value))
    lines.append(_DELIMITER)

    rendered = "\n".join(line for line in lines if line is not None)
    return f"{rendered}\n\n{body}" if body else f"{rendered}\n"


# ── Internals ─────────────────────────────────────────────────────────────────


def _ordered(metadata: Mapping[str, Any]) -> list[tuple[str, Any]]:
    """Known fields in declared order, then anything else alphabetically.

    Unknown keys are preserved rather than dropped: if someone adds `project:` to
    a note by hand, the runner must not eat it on the next write.
    """
    known = [(k, metadata[k]) for k in FIELD_ORDER if _is_set(metadata.get(k))]
    extra = sorted((k, v) for k, v in metadata.items() if k not in FIELD_ORDER and _is_set(v))
    return known + extra


def _is_set(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str | list | tuple | dict):
        return bool(value)
    return True


def _emit(key: str, value: Any) -> str:
    if isinstance(value, list | tuple):
        items = ", ".join(_scalar(v) for v in value)
        return f"{key}: [{items}]"
    return f"{key}: {_scalar(value)}"


def _scalar(value: Any) -> str:
    """Render one value, quoting only when the YAML would otherwise be ambiguous."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)

    text = str(value)
    if _needs_quoting(text):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


_UNQUOTED_SAFE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9 _./+@-]*\Z")

_YAML_RESERVED = {
    # The "Norway problem" and friends: bare words YAML reads as something else.
    "y",
    "yes",
    "n",
    "no",
    "on",
    "off",
    "true",
    "false",
    "null",
    "~",
}


def _needs_quoting(text: str) -> bool:
    if not text:
        return True
    if text.lower() in _YAML_RESERVED:
        return True
    if not _UNQUOTED_SAFE.match(text):
        return True
    return text != text.strip()
