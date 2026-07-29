"""
Brain Models

A local note and its sync state toward the cloud.
sync_status lifecycle:
  local_only → pending_sync → synced
                           ↘ sync_error
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

SYNC_LOCAL_ONLY = "local_only"  # never sent to the cloud
SYNC_PENDING = "pending_sync"  # marcata per sync al prossimo push
SYNC_SYNCED = "synced"  # presente su COT con cot_message_id
SYNC_ERROR = "sync_error"  # the last attempt failed


def new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class Note:
    id: str
    title: str
    content: str  # markdown
    tags: List[str]
    sync_status: str = SYNC_LOCAL_ONLY

    # Cloud references, populated after a sync
    cot_message_id: Optional[str] = None
    cot_cluster_id: Optional[str] = None
    cot_cluster_name: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    synced_at: Optional[datetime] = None
    sync_error: Optional[str] = None

    def is_synced(self) -> bool:
        return self.sync_status == SYNC_SYNCED

    def can_sync(self) -> bool:
        return self.sync_status in (SYNC_PENDING, SYNC_ERROR)


@dataclass
class SyncStats:
    pending: int = 0
    synced: int = 0
    local_only: int = 0
    errors: int = 0
    last_push: Optional[datetime] = None
    last_pull: Optional[datetime] = None
