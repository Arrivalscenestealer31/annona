"""
CLI tests for `akaion note ...` e `akaion sync ...`.

They use typer.testing.CliRunner and isolate the vault via tmp_path and
la env var AKAION_BRAIN_DIR (consultata da _resolve_brain_dir() in cli.py).
"""

import re

# Import il root typer app
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli import app  # noqa: E402

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def isolated_brain(tmp_path, monkeypatch):
    """
    Isola il brain in tmp_path/akaion-brain e forza ConfigManager
    not to read the user's config: no config_exists().
    """
    brain_dir = tmp_path / "akaion-brain"
    monkeypatch.setenv("AKAION_BRAIN_DIR", str(brain_dir))

    # Evita che il resolver legga una config preesistente con un altro brain dir
    from runner.config import ConfigManager

    monkeypatch.setattr(ConfigManager, "config_exists", lambda self: False)
    yield brain_dir


@pytest.fixture
def runner():
    return CliRunner()


def _extract_short_id(stdout: str) -> str:
    """Extract the first UUID from stdout, as printed by `note add`."""
    m = re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        stdout,
    )
    assert m, f"No UUID found in stdout:\n{stdout}"
    return m.group(0)


# ── note add --stdin ──────────────────────────────────────────────────────────


def test_note_add_stdin_creates_local_only(isolated_brain, runner):
    result = runner.invoke(
        app,
        ["note", "add", "--title", "test", "--tag", "foo", "--stdin"],
        input="note 1\n",
    )
    assert result.exit_code == 0, result.stdout
    assert "Note created" in result.stdout
    assert "local_only" in result.stdout

    # Check the database directly
    from runner.brain.manager import BrainManager
    from runner.brain.models import SYNC_LOCAL_ONLY

    brain = BrainManager(isolated_brain)
    notes = brain.list()
    assert len(notes) == 1
    n = notes[0]
    assert n.title == "test"
    assert n.tags == ["foo"]
    assert n.sync_status == SYNC_LOCAL_ONLY
    assert "note 1" in n.content
    brain.close()


# ── note list ─────────────────────────────────────────────────────────────────


def test_note_list_shows_created_note(isolated_brain, runner):
    add = runner.invoke(
        app,
        ["note", "add", "--title", "list-me", "--tag", "bar", "--stdin"],
        input="contenuto",
    )
    assert add.exit_code == 0

    lst = runner.invoke(app, ["note", "list"])
    assert lst.exit_code == 0, lst.stdout
    assert "list-me" in lst.stdout
    assert "bar" in lst.stdout
    assert "local_only" in lst.stdout


# ── note delete --yes ─────────────────────────────────────────────────────────


def test_note_delete_removes_note(isolated_brain, runner):
    add = runner.invoke(
        app,
        ["note", "add", "--title", "to-delete", "--stdin"],
        input="byebye",
    )
    assert add.exit_code == 0
    note_id = _extract_short_id(add.stdout)
    short = note_id[:8]

    delete = runner.invoke(app, ["note", "delete", short, "--yes"])
    assert delete.exit_code == 0, delete.stdout
    assert "Note deleted" in delete.stdout

    # Check the database
    from runner.brain.manager import BrainManager

    brain = BrainManager(isolated_brain)
    assert brain.list() == []
    # The markdown file is gone too
    assert not (isolated_brain / "notes" / f"{note_id}.md").exists()
    brain.close()


# ── sync status su DB vuoto ───────────────────────────────────────────────────


def test_sync_status_empty(isolated_brain, runner):
    result = runner.invoke(app, ["sync", "status"])
    assert result.exit_code == 0, result.stdout
    assert "0 notes total" in result.stdout
    assert "never" in result.stdout  # last push: never


# ── note show <prefix> ────────────────────────────────────────────────────────


def test_note_show_by_prefix(isolated_brain, runner):
    add = runner.invoke(
        app,
        ["note", "add", "--title", "showme", "--tag", "alpha", "--stdin"],
        input="contenuto da mostrare",
    )
    assert add.exit_code == 0, add.stdout
    note_id = _extract_short_id(add.stdout)
    short = note_id[:8]

    show = runner.invoke(app, ["note", "show", short])
    assert show.exit_code == 0, show.stdout
    assert "showme" in show.stdout
    assert "alpha" in show.stdout
    assert "contenuto da mostrare" in show.stdout
    assert "local_only" in show.stdout


# ── note search <query> ───────────────────────────────────────────────────────


def test_note_search_fts(isolated_brain, runner):
    add = runner.invoke(
        app,
        ["note", "add", "--title", "ricerca-target", "--stdin"],
        input="parolachiave unica",
    )
    assert add.exit_code == 0, add.stdout

    search = runner.invoke(app, ["note", "search", "parolachiave"])
    assert search.exit_code == 0, search.stdout
    assert "ricerca-target" in search.stdout


# ── sync push --dry-run con 0 pending ─────────────────────────────────────────


def test_sync_push_dry_run_nothing_to_push(isolated_brain, runner):
    result = runner.invoke(app, ["sync", "push", "--all-pending", "--dry-run"])
    assert result.exit_code == 0, result.stdout
    assert "Nothing to push" in result.stdout


# ── id ambiguity ──────────────────────────────────────────────────────────────


def test_note_id_ambiguous_prefix_lists_candidates(isolated_brain, runner, monkeypatch):
    """Crea 2 note con id pilotati per garantire un prefix collisione."""
    from runner.brain import manager as manager_module
    from runner.brain.manager import BrainManager

    # Forziamo id deterministici condividenti un prefix di 4 caratteri
    ids = iter(
        [
            "abcd1111-1111-1111-1111-111111111111",
            "abcd2222-2222-2222-2222-222222222222",
        ]
    )
    monkeypatch.setattr(manager_module, "new_id", lambda: next(ids))

    brain = BrainManager(isolated_brain)
    brain.create(title="first", content="x")
    brain.create(title="second", content="y")
    brain.close()

    # A prefix matching both must error and list the candidates
    show = runner.invoke(app, ["note", "show", "abcd"])
    assert show.exit_code != 0, show.stdout
    assert "ambiguo" in show.stdout.lower() or "ambig" in show.stdout.lower()
    assert "first" in show.stdout
    assert "second" in show.stdout

    # A prefix matching nothing must report that clearly
    miss = runner.invoke(app, ["note", "show", "deadbeef"])
    assert miss.exit_code != 0, miss.stdout
    assert "no note" in miss.stdout.lower()
