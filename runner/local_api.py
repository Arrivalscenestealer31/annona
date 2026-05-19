"""
Local API Server

FastAPI su 127.0.0.1:7070 — espone API + serve la web UI buildata da `ui/dist`.
Gira in un thread separato accanto al daemon di polling.

Endpoints:
  GET  /health
  GET  /api/auth/status
  POST /api/auth/save
  POST /api/auth/logout
  GET  /api/brain/notes
  POST /api/brain/notes
  GET  /api/brain/notes/{id}
  PATCH /api/brain/notes/{id}
  DELETE /api/brain/notes/{id}
  POST /api/brain/notes/{id}/mark-sync
  GET  /api/brain/search?q=...
  GET  /api/sync/status
  POST /api/sync/push
  POST /api/sync/push/{id}
  GET  /            → ui/dist/index.html (se la UI è stata buildata)
"""
import threading
from typing import List, Optional, Any, Dict
from pathlib import Path
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel

from .brain.manager import BrainManager
from .auth import AuthManager
from .brain.models import Note, SyncStats
from .sync.engine import SyncEngine


# UI dist path: <runner-root>/ui/dist
_UI_DIST = Path(__file__).resolve().parent.parent / "ui" / "dist"


# ── Pydantic I/O models ───────────────────────────────────────────────────────

class NoteCreate(BaseModel):
    title: str
    content: str = ""
    tags: List[str] = []

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None

class NoteOut(BaseModel):
    id: str
    title: str
    content: str
    tags: List[str]
    sync_status: str
    cot_message_id: Optional[str]
    cot_cluster_id: Optional[str]
    cot_cluster_name: Optional[str]
    created_at: datetime
    updated_at: datetime
    synced_at: Optional[datetime]
    sync_error: Optional[str]

    @classmethod
    def from_note(cls, n: Note) -> "NoteOut":
        return cls(**n.__dict__)

class SyncStatusOut(BaseModel):
    pending: int
    synced: int
    local_only: int
    errors: int
    last_push: Optional[datetime]


# ── App factory ───────────────────────────────────────────────────────────────

def create_app(
    brain: BrainManager,
    sync: SyncEngine,
    auth: Optional[AuthManager] = None,
    cloud_enabled: bool = False,
) -> FastAPI:
    app = FastAPI(title="Akaion Local API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        # Same-origin (7070) needs no CORS. 5173 is the Vite dev server.
        # Tauri origins removed in Step 5 (desktop shell dropped).
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:7070",
            "http://127.0.0.1:7070",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _auth = auth or AuthManager()

    # ── Health ────────────────────────────────────────────────────────────────

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "akaion-local"}

    # ── Auth ──────────────────────────────────────────────────────────────────

    @app.get("/api/auth/status")
    def auth_status():
        """Controlla se il runner è autenticato. Sempre 200 — mai bloccante."""
        authenticated = _auth.is_authenticated()
        return {
            "authenticated": authenticated,
            "email": _auth.get_email() if authenticated else None,
            "runner_id": _auth.get_runner_id() if authenticated else None,
            "mode": "cloud" if authenticated else "local",
        }

    # ── Runner mode ───────────────────────────────────────────────────────────

    @app.get("/api/runner/mode")
    def runner_mode():
        """
        Modalità attuale del runner (la UI la usa per decidere cosa mostrare
        in sidebar: badge "Locale" vs "Sincronizzato").
        """
        authenticated = _auth.is_authenticated()
        return {
            "mode": "cloud" if (cloud_enabled and authenticated) else "local",
            "cloud_enabled": cloud_enabled,
            "authenticated": authenticated,
            "vault_path": str(brain.brain_dir) if hasattr(brain, "brain_dir") else "~/akaion-brain",
        }

    class AuthSaveRequest(BaseModel):
        firebase_token: str
        refresh_token: str
        expires_in: int = 3600
        email: Optional[str] = None

    @app.post("/api/auth/save")
    def auth_save(body: AuthSaveRequest):
        """
        Salva le credenziali Firebase ricevute dal login in-app.
        Chiamato dalla UI Tauri dopo il login con Firebase JS SDK.
        """
        try:
            _auth.save_credentials(
                firebase_token=body.firebase_token,
                refresh_token=body.refresh_token,
                expires_in=body.expires_in,
                email=body.email,
            )
            return {
                "authenticated": True,
                "email": body.email,
                "runner_id": _auth.get_runner_id(),
            }
        except Exception as e:
            raise HTTPException(500, f"Failed to save credentials: {e}")

    @app.post("/api/auth/logout")
    def auth_logout():
        """Rimuove le credenziali locali."""
        _auth.clear_credentials()
        return {"authenticated": False}

    # ── Brain: Notes ──────────────────────────────────────────────────────────

    @app.get("/api/brain/notes", response_model=List[NoteOut])
    def list_notes(
        sync_status: Optional[str] = Query(None),
        tag: Optional[str] = Query(None),
        limit: int = Query(100, le=500),
        offset: int = Query(0, ge=0),
    ):
        notes = brain.list(sync_status=sync_status, tag=tag, limit=limit, offset=offset)
        return [NoteOut.from_note(n) for n in notes]

    @app.post("/api/brain/notes", response_model=NoteOut, status_code=201)
    def create_note(body: NoteCreate):
        note = brain.create(title=body.title, content=body.content, tags=body.tags)
        return NoteOut.from_note(note)

    @app.get("/api/brain/notes/{note_id}", response_model=NoteOut)
    def get_note(note_id: str):
        note = brain.get(note_id)
        if not note:
            raise HTTPException(404, "Note not found")
        return NoteOut.from_note(note)

    @app.patch("/api/brain/notes/{note_id}", response_model=NoteOut)
    def update_note(note_id: str, body: NoteUpdate):
        note = brain.update(
            note_id,
            title=body.title,
            content=body.content,
            tags=body.tags,
        )
        if not note:
            raise HTTPException(404, "Note not found")
        return NoteOut.from_note(note)

    @app.delete("/api/brain/notes/{note_id}", status_code=204)
    def delete_note(note_id: str):
        if not brain.delete(note_id):
            raise HTTPException(404, "Note not found")

    @app.post("/api/brain/notes/{note_id}/mark-sync", response_model=NoteOut)
    def mark_note_for_sync(note_id: str):
        """Marca la nota come pending_sync — verrà inviata al prossimo push."""
        if not brain.mark_pending(note_id):
            raise HTTPException(404, "Note not found or already pending")
        note = brain.get(note_id)
        return NoteOut.from_note(note)

    @app.get("/api/brain/search", response_model=List[NoteOut])
    def search_notes(q: str = Query(..., min_length=1), limit: int = Query(20, le=100)):
        notes = brain.search(q, limit=limit)
        return [NoteOut.from_note(n) for n in notes]

    # ── Sync ──────────────────────────────────────────────────────────────────

    @app.get("/api/sync/status", response_model=SyncStatusOut)
    def sync_status():
        stats = brain.stats()
        return SyncStatusOut(
            pending=stats.pending,
            synced=stats.synced,
            local_only=stats.local_only,
            errors=stats.errors,
            last_push=stats.last_push,
        )

    @app.post("/api/sync/push")
    def sync_push():
        """Push tutte le note pending verso COT cloud."""
        return sync.push_pending()

    @app.post("/api/sync/push/{note_id}")
    def sync_push_one(note_id: str):
        """Push di una singola nota (forzato, indipendentemente dallo stato)."""
        ok = sync.push_note(note_id)
        if not ok:
            raise HTTPException(400, "Sync failed — controlla i log")
        note = brain.get(note_id)
        return NoteOut.from_note(note)

    # ── Static UI mount ────────────────────────────────────────────────────────
    # Must be LAST: it's mounted at "/" with html=True so it would otherwise
    # intercept /api/* routes registered above. FastAPI walks routes in order
    # and mounts are last-priority anyway, but we register it here to be explicit.
    _mount_ui(app)

    return app


def _mount_ui(app: FastAPI) -> None:
    """Mount the built React UI at `/`. Skip-with-warning if dist isn't built yet."""
    index_html = _UI_DIST / "index.html"
    if not index_html.exists():
        logger.warning(
            f"UI not built at {_UI_DIST}. Run `npm run build` in ui/ "
            f"or use start.sh (auto-builds on first run)."
        )
        return
    app.mount("/", StaticFiles(directory=str(_UI_DIST), html=True), name="ui")
    logger.info(f"UI mounted at / from {_UI_DIST}")


# ── Runner del server in thread separato ─────────────────────────────────────

class LocalAPIServer:
    """Avvia FastAPI in un daemon thread accanto al polling loop."""

    def __init__(
        self,
        brain: BrainManager,
        sync: SyncEngine,
        auth: Optional[AuthManager] = None,
        port: int = 7070,
        cloud_enabled: bool = False,
    ):
        self.brain         = brain
        self.sync          = sync
        self.auth          = auth
        self.port          = port
        self.cloud_enabled = cloud_enabled
        self._thread: Optional[threading.Thread] = None
        self._server: Optional[uvicorn.Server]   = None

    def start(self):
        app = create_app(self.brain, self.sync, self.auth, cloud_enabled=self.cloud_enabled)
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=self.port,
            log_level="warning",   # silenzia i log HTTP nel terminale del runner
            access_log=False,
        )
        self._server = uvicorn.Server(config)

        self._thread = threading.Thread(
            target=self._server.run,
            daemon=True,
            name="akaion-local-api",
        )
        self._thread.start()
        # Piccola attesa per lasciar partire uvicorn
        import time; time.sleep(0.5)
        logger.info(f"Local API ready on http://127.0.0.1:{self.port}")

    def stop(self):
        if self._server:
            self._server.should_exit = True
