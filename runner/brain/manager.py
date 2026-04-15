"""
Brain Manager

Gestisce la persistenza locale delle note:
- SQLite per metadata e indice full-text
- File markdown in <brain_dir>/notes/<id>.md

Struttura su disco:
  ~/akaion-brain/
  ├── notes/          ← <uuid>.md
  └── .akaion/
      └── index.db    ← SQLite
"""
import sqlite3
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from loguru import logger

from .models import Note, SyncStats, new_id, SYNC_LOCAL_ONLY, SYNC_PENDING, SYNC_SYNCED, SYNC_ERROR


SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id               TEXT PRIMARY KEY,
    title            TEXT NOT NULL,
    tags             TEXT NOT NULL DEFAULT '[]',   -- JSON array
    sync_status      TEXT NOT NULL DEFAULT 'local_only',
    cot_message_id   TEXT,
    cot_cluster_id   TEXT,
    cot_cluster_name TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    synced_at        TEXT,
    sync_error       TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    id UNINDEXED,
    title,
    content,
    content='',
    contentless_delete=1
);
"""


def _now() -> str:
    return datetime.utcnow().isoformat()


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(s) if s else None


class BrainManager:
    """CRUD locale per note + indice SQLite."""

    def __init__(self, brain_dir: Path):
        self.brain_dir = Path(brain_dir).expanduser()
        self.notes_dir = self.brain_dir / "notes"
        self.db_path   = self.brain_dir / ".akaion" / "index.db"

        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()
        logger.info(f"BrainManager ready: {self.brain_dir}")

    def _migrate(self):
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ── Markdown helpers ──────────────────────────────────────────────────────

    def _note_path(self, note_id: str) -> Path:
        return self.notes_dir / f"{note_id}.md"

    def _write_md(self, note_id: str, content: str):
        self._note_path(note_id).write_text(content, encoding="utf-8")

    def _read_md(self, note_id: str) -> str:
        p = self._note_path(note_id)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def _delete_md(self, note_id: str):
        p = self._note_path(note_id)
        if p.exists():
            p.unlink()

    # ── Row → Note ────────────────────────────────────────────────────────────

    def _row_to_note(self, row: sqlite3.Row) -> Note:
        content = self._read_md(row["id"])
        return Note(
            id=row["id"],
            title=row["title"],
            content=content,
            tags=json.loads(row["tags"]),
            sync_status=row["sync_status"],
            cot_message_id=row["cot_message_id"],
            cot_cluster_id=row["cot_cluster_id"],
            cot_cluster_name=row["cot_cluster_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            synced_at=_parse_dt(row["synced_at"]),
            sync_error=row["sync_error"],
        )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def create(self, title: str, content: str = "", tags: Optional[List[str]] = None) -> Note:
        note = Note(
            id=new_id(),
            title=title,
            content=content,
            tags=tags or [],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self._write_md(note.id, content)
        now = _now()
        self._conn.execute(
            """INSERT INTO notes (id, title, tags, sync_status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (note.id, note.title, json.dumps(note.tags), note.sync_status, now, now),
        )
        self._conn.execute(
            "INSERT INTO notes_fts (id, title, content) VALUES (?, ?, ?)",
            (note.id, note.title, content),
        )
        self._conn.commit()
        logger.debug(f"Note created: {note.id} [{note.title}]")
        return note

    def get(self, note_id: str) -> Optional[Note]:
        row = self._conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return self._row_to_note(row) if row else None

    def list(
        self,
        sync_status: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Note]:
        query = "SELECT * FROM notes"
        params: list = []
        conditions: list = []

        if sync_status:
            conditions.append("sync_status = ?")
            params.append(sync_status)
        if tag:
            conditions.append("tags LIKE ?")
            params.append(f'%"{tag}"%')
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params += [limit, offset]

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_note(r) for r in rows]

    def search(self, query: str, limit: int = 20) -> List[Note]:
        rows = self._conn.execute(
            """SELECT n.* FROM notes n
               JOIN notes_fts f ON n.id = f.id
               WHERE notes_fts MATCH ?
               ORDER BY rank LIMIT ?""",
            (query, limit),
        ).fetchall()
        return [self._row_to_note(r) for r in rows]

    def update(
        self,
        note_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[Note]:
        note = self.get(note_id)
        if not note:
            return None

        now = _now()
        updates: dict = {"updated_at": now}
        if title is not None:
            updates["title"] = title
            note.title = title
        if tags is not None:
            updates["tags"] = json.dumps(tags)
            note.tags = tags
        if content is not None:
            self._write_md(note_id, content)
            note.content = content
            # Aggiorna FTS
            self._conn.execute("DELETE FROM notes_fts WHERE id = ?", (note_id,))
            self._conn.execute(
                "INSERT INTO notes_fts (id, title, content) VALUES (?, ?, ?)",
                (note_id, updates.get("title", note.title), content),
            )

        # Se era synced e il contenuto cambia → torna pending
        if content is not None and note.sync_status == SYNC_SYNCED:
            updates["sync_status"] = SYNC_PENDING

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        self._conn.execute(
            f"UPDATE notes SET {set_clause} WHERE id = ?",
            list(updates.values()) + [note_id],
        )
        self._conn.commit()
        return self.get(note_id)

    def delete(self, note_id: str) -> bool:
        self._delete_md(note_id)
        self._conn.execute("DELETE FROM notes_fts WHERE id = ?", (note_id,))
        cur = self._conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ── Sync status helpers ───────────────────────────────────────────────────

    def mark_pending(self, note_id: str) -> bool:
        """Marca la nota per la sync al prossimo push."""
        cur = self._conn.execute(
            "UPDATE notes SET sync_status = ?, updated_at = ? WHERE id = ? AND sync_status != ?",
            (SYNC_PENDING, _now(), note_id, SYNC_PENDING),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def mark_synced(self, note_id: str, cot_message_id: str, cot_cluster_id: Optional[str] = None, cot_cluster_name: Optional[str] = None):
        """Aggiorna la nota dopo una sync riuscita."""
        self._conn.execute(
            """UPDATE notes SET
               sync_status = ?, cot_message_id = ?, cot_cluster_id = ?,
               cot_cluster_name = ?, synced_at = ?, sync_error = NULL, updated_at = ?
               WHERE id = ?""",
            (SYNC_SYNCED, cot_message_id, cot_cluster_id, cot_cluster_name, _now(), _now(), note_id),
        )
        self._conn.commit()

    def mark_sync_error(self, note_id: str, error: str):
        self._conn.execute(
            "UPDATE notes SET sync_status = ?, sync_error = ?, updated_at = ? WHERE id = ?",
            (SYNC_ERROR, error[:500], _now(), note_id),
        )
        self._conn.commit()

    def update_cluster_info(self, cot_message_id: str, cot_cluster_id: str, cot_cluster_name: str):
        """Aggiorna cluster info dopo un pull da COT."""
        self._conn.execute(
            "UPDATE notes SET cot_cluster_id = ?, cot_cluster_name = ? WHERE cot_message_id = ?",
            (cot_cluster_id, cot_cluster_name, cot_message_id),
        )
        self._conn.commit()

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> SyncStats:
        rows = self._conn.execute(
            "SELECT sync_status, COUNT(*) as cnt FROM notes GROUP BY sync_status"
        ).fetchall()
        counts = {r["sync_status"]: r["cnt"] for r in rows}

        last_push = self._conn.execute(
            "SELECT MAX(synced_at) as ts FROM notes WHERE sync_status = 'synced'"
        ).fetchone()["ts"]
        last_pull = self._conn.execute(
            "SELECT MAX(synced_at) as ts FROM notes WHERE cot_cluster_id IS NOT NULL"
        ).fetchone()["ts"]

        return SyncStats(
            pending=counts.get(SYNC_PENDING, 0),
            synced=counts.get(SYNC_SYNCED, 0),
            local_only=counts.get(SYNC_LOCAL_ONLY, 0),
            errors=counts.get(SYNC_ERROR, 0),
            last_push=_parse_dt(last_push),
            last_pull=_parse_dt(last_pull),
        )

    def close(self):
        self._conn.close()
