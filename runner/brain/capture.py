"""
Task → Note capture helper.

Salva il risultato dell'esecuzione di un task del runner come Note locale
(`sync_status=local_only`) nel Brain. L'utente decide quando pushare la nota
al cloud — la capture NON sincronizza automaticamente.

Vedi `RunnerDaemon._capture_task_to_brain` (`runner/main.py`).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from .manager import BrainManager
from .models import Note

# Soglia massima content (in bytes) — sopra: troncato + nota.
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
    Considera il risultato fallito se è esplicitamente `{success: False}`
    o un equivalente. Non assumere mai che `None` = success.
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
    Costruisce i tag e ritorna anche il `dedup_tag` (full uuid, no truncate)
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
    """Costruisce il markdown della nota."""
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
    Salva il task come Note locale con `sync_status=local_only`.

    - Idempotente: stesso task_id → 1 sola nota (check via tag `task:<uuid>`).
    - Mai propaga eccezioni: logga WARNING e ritorna None.
    - Non sincronizza automaticamente al cloud.

    Returns:
        La Note creata, oppure quella esistente se già presente, oppure
        None su errore.
    """
    try:
        failed = _is_failed(result)
        tags, dedup_tag = _build_tags(task, failed)

        # Idempotency: se esiste già una nota con tag `task:<full_uuid>` skip.
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
    except Exception as e:  # noqa: BLE001 — mai propagare
        logger.warning(f"Failed to capture task to brain: {e}")
        return None
