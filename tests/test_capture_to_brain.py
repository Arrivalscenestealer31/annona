"""
Tests for the task → local Note capture hook in `RunnerDaemon._execute_task`.

Strategy:
  * Real `BrainManager` on a tmp_path vault (SQLite is cheap; covers the
    integration with create + find_note_by_tag).
  * Hand-rolled `_DaemonStub` that re-implements the contract of
    `RunnerDaemon._execute_task` + `_capture_task_to_brain` WITHOUT touching
    auth / cloud_client / local_api (which would need network + Firebase).
  * `executor.execute` is mocked per-test.

This keeps tests fast and hermetic while still exercising the production
`capture_task_as_note` helper.
"""
from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from runner.brain.capture import capture_task_as_note, MAX_CONTENT_BYTES
from runner.brain.manager import BrainManager
from runner.brain.models import SYNC_LOCAL_ONLY


# ── Daemon stub ───────────────────────────────────────────────────────────────


class _DaemonStub:
    """
    Mirrors the minimum surface of `RunnerDaemon._execute_task` /
    `_capture_task_to_brain` needed to test the capture behaviour.
    Avoids the heavy `RunnerDaemon.__init__` (auth + cloud + local_api).
    """

    def __init__(self, brain: BrainManager, capture: bool, executor: Any):
        self.brain = brain
        self.capture_to_brain = capture
        self.executor = executor
        self.cloud_client = MagicMock()

    def _capture_task_to_brain(self, task: Dict[str, Any], result: Any) -> None:
        if not self.capture_to_brain:
            return
        try:
            capture_task_as_note(self.brain, task, result)
        except Exception:  # noqa: BLE001
            pass

    def execute_task(self, task: Dict[str, Any]) -> Any:
        try:
            result = self.executor.execute(task)
            self._capture_task_to_brain(task, result)
            return result
        except Exception as e:
            self._capture_task_to_brain(task, {"success": False, "error": str(e)})
            raise


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def brain(tmp_path):
    b = BrainManager(tmp_path / "brain")
    yield b
    b.close()


@pytest.fixture
def fake_executor():
    """Mock executor with a configurable return value."""
    ex = MagicMock()
    ex.execute.return_value = {
        "type": "tool_result",
        "tool": "filesystem",
        "result": {"success": True, "output": "hello world"},
    }
    return ex


def _sample_tool_task() -> Dict[str, Any]:
    return {
        "id": "task-abc12345-1111-2222-3333-444455556666",
        "type": "tool",
        "payload": {"tool": "filesystem", "args": {"path": "/tmp/x"}},
    }


# ── Test 1 — capture_to_brain=True + success ──────────────────────────────────


def test_capture_creates_local_only_note_with_correct_tags(brain, fake_executor):
    daemon = _DaemonStub(brain, capture=True, executor=fake_executor)
    task = _sample_tool_task()

    daemon.execute_task(task)

    notes = brain.list()
    assert len(notes) == 1
    note = notes[0]

    assert note.sync_status == SYNC_LOCAL_ONLY
    # Tags richiesti dalla spec
    assert "runner" in note.tags
    assert f"task:{task['id']}" in note.tags  # full uuid, no truncate
    assert "type:tool" in note.tags
    assert "tool:filesystem" in note.tags
    assert "error" not in note.tags

    # Title: nessun task.title fornito → fallback "Task {type}: {id[:8]}"
    assert note.title.startswith("Task tool:")
    assert "task-abc" in note.title

    # Content sanity
    assert "**Task ID:**" in note.content
    assert task["id"] in note.content
    assert "## Input" in note.content
    assert "## Output" in note.content
    assert "hello world" in note.content


# ── Test 2 — capture_to_brain=False ───────────────────────────────────────────


def test_capture_disabled_creates_no_note(brain, fake_executor):
    daemon = _DaemonStub(brain, capture=False, executor=fake_executor)
    daemon.execute_task(_sample_tool_task())

    assert brain.list() == []


# ── Test 3 — Idempotency (same task_id × 2 → 1 note) ──────────────────────────


def test_same_task_id_does_not_create_duplicate_note(brain, fake_executor):
    daemon = _DaemonStub(brain, capture=True, executor=fake_executor)
    task = _sample_tool_task()

    daemon.execute_task(task)
    daemon.execute_task(task)  # retry simulato

    notes = brain.list()
    assert len(notes) == 1


def test_different_task_ids_create_different_notes(brain, fake_executor):
    daemon = _DaemonStub(brain, capture=True, executor=fake_executor)

    t1 = _sample_tool_task()
    t2 = dict(t1, id="task-xyz98765-0000-1111-2222-333344445555")

    daemon.execute_task(t1)
    daemon.execute_task(t2)

    assert len(brain.list()) == 2


# ── Test 4 — Truncation oltre 100 KB ──────────────────────────────────────────


def test_huge_output_is_truncated_with_marker(brain):
    # Output > 100 KB: stringa di 200 KB
    huge_string = "x" * (200 * 1024)
    ex = MagicMock()
    ex.execute.return_value = huge_string  # ritorno stringa diretta (markdown)

    daemon = _DaemonStub(brain, capture=True, executor=ex)
    daemon.execute_task(_sample_tool_task())

    note = brain.list()[0]
    encoded = note.content.encode("utf-8")
    # Trunc soglia + nota in coda → max ~ MAX_CONTENT_BYTES + len(marker)
    assert len(encoded) <= MAX_CONTENT_BYTES + 200
    assert "[Output truncated" in note.content


# ── Test 5 — Task fallito → tag `error` + prefix ──────────────────────────────


def test_failed_task_is_captured_with_error_tag_and_prefix(brain):
    ex = MagicMock()
    ex.execute.side_effect = RuntimeError("boom")

    daemon = _DaemonStub(brain, capture=True, executor=ex)
    task = _sample_tool_task()

    with pytest.raises(RuntimeError):
        daemon.execute_task(task)

    notes = brain.list()
    assert len(notes) == 1
    note = notes[0]

    assert "error" in note.tags
    assert "runner" in note.tags
    assert f"task:{task['id']}" in note.tags
    # Prefix
    assert note.content.lstrip().startswith("> **Task failed**")
    # Errore embeddato nell'output
    assert "boom" in note.content


def test_failed_result_dict_also_tagged_error(brain):
    """Anche un result {success: False} (non eccezione) deve essere taggato."""
    ex = MagicMock()
    ex.execute.return_value = {"success": False, "error": "validation failed"}

    daemon = _DaemonStub(brain, capture=True, executor=ex)
    daemon.execute_task(_sample_tool_task())

    note = brain.list()[0]
    assert "error" in note.tags
    assert note.content.lstrip().startswith("> **Task failed**")


# ── Extra — title da task.title se presente ───────────────────────────────────


def test_explicit_task_title_is_used(brain, fake_executor):
    daemon = _DaemonStub(brain, capture=True, executor=fake_executor)
    task = dict(_sample_tool_task(), title="My Cool Task")

    daemon.execute_task(task)

    note = brain.list()[0]
    assert note.title == "My Cool Task"


# ── Extra — find_note_by_tag direct unit test ─────────────────────────────────


def test_find_note_by_tag_returns_none_when_absent(brain):
    assert brain.find_note_by_tag("task:does-not-exist") is None


def test_find_note_by_tag_returns_matching_note(brain):
    n = brain.create(title="t", content="c", tags=["task:abc-123", "runner"])
    found = brain.find_note_by_tag("task:abc-123")
    assert found is not None
    assert found.id == n.id
