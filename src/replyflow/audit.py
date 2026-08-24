from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from .models import AuditLog
from .repositories import AuditLogRepository


def record_state_transition(
    connection: sqlite3.Connection,
    *,
    task_id: str,
    before_state: str,
    after_state: str,
    note: str = "",
) -> None:
    AuditLogRepository(connection).create(
        AuditLog(
            audit_id=f"AUD-{uuid4().hex[:12].upper()}",
            task_id=task_id,
            action="DEMO_STATE_TRANSITION",
            before_summary=before_state,
            after_summary=f"{after_state}{': ' + note if note else ''}",
            created_at=datetime.now(timezone.utc),
        )
    )
