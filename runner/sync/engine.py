"""
Sync Engine

Push/Pull tra il brain locale e il COT cloud.

Design:
- PUSH: note con sync_status=pending_sync → POST /api/v1/cloud/thoughts
- PULL: GET /api/v1/cloud/messages + /clusters → aggiorna cluster_info locale
- Non tutto deve essere sincronizzato: local_only rimane locale finché
  l'utente non chiama mark_pending() o push esplicito.

Local-first: ogni metodo verifica auth PRIMA di costruire un client httpx.
Senza credenziali la sync è un no-op silenzioso (niente Bearer None requests).
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from loguru import logger
import httpx

from runner.brain.manager import BrainManager
from runner.brain.models import Note, SYNC_PENDING, SYNC_ERROR
from runner.auth import AuthManager

# Errori di rete transitori: la nota resta pending_sync per riprovare dopo
_NETWORK_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.NetworkError,
    OSError,  # include DNS failures (socket.gaierror è sottoclasse di OSError)
)


class SyncError(Exception):
    """Errore lato sync (auth mancante, payload invalido, ecc.)."""


class SyncEngine:
    """Gestisce sync bidirezionale con COT cloud."""

    def __init__(
        self,
        brain: BrainManager,
        cot_url: str,
        auth: AuthManager,
        timeout: int = 30,
    ):
        self.brain   = brain
        self.cot_url = cot_url.rstrip("/")
        self.auth    = auth
        self.timeout = timeout

    def _client(self) -> httpx.Client:
        """Costruisce un httpx.Client autenticato. Solleva SyncError se manca il token."""
        token = self.auth.get_firebase_token()
        if not token:
            raise SyncError("not_authenticated")
        return httpx.Client(
            base_url=self.cot_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )

    # ── Push ──────────────────────────────────────────────────────────────────

    def push_pending(self) -> Dict[str, int]:
        """
        Invia al COT tutte le note con sync_status=pending_sync.
        Restituisce {"synced": N, "errors": M, "error"?: "not_authenticated"}.
        """
        pending = self.brain.list(sync_status=SYNC_PENDING)
        if not pending:
            logger.info("Sync push: nessuna nota pending")
            return {"synced": 0, "errors": 0}

        logger.info(f"Sync push: {len(pending)} note da inviare")
        synced = errors = 0

        try:
            with self._client() as client:
                for note in pending:
                    result = self._push_note(client, note)
                    if result:
                        synced += 1
                    else:
                        errors += 1
        except SyncError as e:
            logger.warning(f"Sync push skipped: {e}")
            return {"synced": 0, "errors": 0, "error": str(e)}

        logger.info(f"Sync push completata: {synced} ok, {errors} errori")
        return {"synced": synced, "errors": errors}

    def push_note(self, note_id: str) -> bool:
        """Push di una singola nota (indipendentemente dallo stato)."""
        note = self.brain.get(note_id)
        if not note:
            return False
        try:
            with self._client() as client:
                return self._push_note(client, note)
        except SyncError as e:
            logger.warning(f"Sync push skipped [{note_id}]: {e}")
            return False

    def _push_note(self, client: httpx.Client, note: Note) -> bool:
        try:
            payload = {
                "content": f"# {note.title}\n\n{note.content}",
                "metadata": {
                    "title": note.title,
                    "source": "local_runner",
                    "local_id": note.id,
                    "tags": note.tags,
                },
                "hint_tags": note.tags,
                "enable_embeddings": True,
            }

            resp = client.post("/api/v1/cloud/thoughts", json=payload)

            if resp.status_code in (200, 201):
                data = resp.json()
                # COT restituisce message_id e opzionalmente cluster
                cot_message_id  = data.get("message_id") or data.get("id")
                cot_cluster_id  = data.get("cluster_id")
                cot_cluster_name = data.get("cluster_name")

                self.brain.mark_synced(
                    note.id,
                    cot_message_id=str(cot_message_id),
                    cot_cluster_id=str(cot_cluster_id) if cot_cluster_id else None,
                    cot_cluster_name=cot_cluster_name,
                )
                logger.debug(f"Note synced: {note.id} → COT {cot_message_id}")
                return True
            else:
                error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                self.brain.mark_sync_error(note.id, error)
                logger.warning(f"Note sync failed [{note.id}]: {error}")
                return False

        except _NETWORK_ERRORS as e:
            # Errore di rete transitorio → lascia pending_sync, riproverà dopo
            logger.warning(f"Note sync offline [{note.id}]: {type(e).__name__} — rete non disponibile")
            return False
        except Exception as e:
            # Errore permanente (authn, payload, etc.) → marca sync_error
            self.brain.mark_sync_error(note.id, str(e))
            logger.error(f"Note sync error [{note.id}]: {e}")
            return False

