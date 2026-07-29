"""
Task → Note capture helper.

Records the result of a runner task as a local note
(`sync_status=local_only`) in the vault. You decide when to push it
to the cloud: capturing never syncs on its own.

Vedi `RunnerDaemon._capture_task_to_brain` (`runner/main.py`).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from .manager import BrainManager
from .models import Note

# Maximum content size in bytes; above it the note is truncated and marked.
MAX_CONTENT_BYTES = 100 * 1024  # 100 KB
_TRUNC_NOTE = "\n\n_[Output truncated, full result sent to cloud only]_\n"


def _derive_title(task: Dict[str, Any]) -> str:
    """Title fallback: task.title → task.name → "Task {type}: {id_short}"."""
    title = task.get("title") or task.get("name")
    if title:
        return str(title)
    task_type = task.get("type", "command")
    task_id = str(task.get("id", "unknown"))
    return f"Task {task_type}: {task_id[:8]}"


def _is_failed(result: Any) -> bool:
    """
    Treats a result as failed only when it explicitly says `{success: False}`
    or equivalent. `None` is never assumed to mean success.
    """
    if result is None:
        return True
    if isinstance(result, dict):
        if result.get("success") is False:
            return True
        if "error" in result and result.get("error"):
            return True
    return False


def _format_payload(payload: Any) -> str:
    """Serialize input payload per la sezione `## Input` del markdown."""
    try:
        return json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return repr(payload)


def _format_output(result: Any) -> str:
    """
    Output preservato:
      - str → as-is (assunto markdown)
      - altro → JSON in code block
    """
    if isinstance(result, str):
        return result
    try:
        body = json.dumps(result, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        body = repr(result)
    return f"```json\n{body}\n```"


def _build_tags(
    task: Dict[str, Any],
    failed: bool,
) -> Tuple[List[str], str]:
    """
    Builds the tags and also returns `dedup_tag` (the full uuid, untruncated)
    da usare per il check di idempotency.
    """
    task_id = str(task.get("id", "unknown"))
    task_type = task.get("type", "command")
    dedup_tag = f"task:{task_id}"

    tags: List[str] = [
        "runner",
        dedup_tag,
        f"type:{task_type}",
    ]

    # Tool name solo se task_type == "tool"
    if task_type == "tool":
        tool_name = (task.get("payload") or {}).get("tool")
        if tool_name:
            tags.append(f"tool:{tool_name}")

    if failed:
        tags.append("error")

    return tags, dedup_tag


def _build_content(
    title: str,
    task: Dict[str, Any],
    result: Any,
    failed: bool,
) -> str:
    """Render the note as markdown."""
    task_id = str(task.get("id", "unknown"))
    task_type = task.get("type", "command")
    tool_line = ""
    if task_type == "tool":
        tool_name = (task.get("payload") or {}).get("tool")
        if tool_name:
            tool_line = f"**Tool:** `{tool_name}`\n"

    timestamp = datetime.utcnow().isoformat() + "Z"
    payload = task.get("payload", {})

    failure_prefix = "> **Task failed**\n\n" if failed else ""

    content = (
        f"{failure_prefix}"
        f"# {title}\n\n"
        f"**Task ID:** `{task_id}`\n"
        f"**Type:** `{task_type}`\n"
        f"**Executed:** {timestamp}\n"
        f"{tool_line}"
        f"\n## Input\n\n"
        f"```json\n{_format_payload(payload)}\n```\n"
        f"\n## Output\n\n"
        f"{_format_output(result)}\n"
    )

    # Truncate se superiamo soglia (evita vault gonfiato da explorer/document_reader).
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_CONTENT_BYTES:
        truncated = encoded[:MAX_CONTENT_BYTES].decode("utf-8", errors="ignore")
        content = truncated + _TRUNC_NOTE

    return content


def capture_task_as_note(
    brain: BrainManager,
    task: Dict[str, Any],
    result: Any,
) -> Optional[Note]:
    """
    Stores the task as a local note with `sync_status=local_only`.

    - Idempotent: one note per task_id, matched on the `task:<uuid>` tag.
    - Never raises: logs a warning and returns None.
    - Never syncs to the cloud on its own.

    Returns:
        The note created, the existing one if there already was one, or
        None on error.
    """
    try:
        failed = _is_failed(result)
        tags, dedup_tag = _build_tags(task, failed)

        # Idempotency: skip if a note already carries the `task:<full_uuid>` tag.
        existing = brain.find_note_by_tag(dedup_tag)
        if existing is not None:
            logger.debug(
                f"Task {str(task.get('id', ''))[:8]} already captured "
                f"as note {existing.id[:8]}, skipping"
            )
            return existing

        title = _derive_title(task)
        content = _build_content(title, task, result, failed)

        note = brain.create(title=title, content=content, tags=tags)

        task_short = str(task.get("id", "unknown"))[:8]
        logger.info(f"📝 Captured task {task_short} as note {note.id[:8]}")
        return note
    except Exception as e:  # noqa: BLE001 - capturing must never fail a task
        logger.warning(f"Failed to capture task to brain: {e}")
        return None
