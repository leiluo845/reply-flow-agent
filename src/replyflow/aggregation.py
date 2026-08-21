from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .models import AggregateThread


BUYER_SOURCES = {"demo_console", "marketplace_station_message"}
NON_BUYER_SOURCES = {"platform_notification", "system_notification", "internal_message"}


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def is_buyer_message(*, source: str, sender_email: str, subject: str, body: str) -> bool:
    """Classify only the demo/source boundary; this is not a policy classifier."""
    normalized_source = source.strip().lower()
    if normalized_source in NON_BUYER_SOURCES:
        return False
    if normalized_source in BUYER_SOURCES:
        return True
    sender = sender_email.strip().lower()
    if sender.startswith(("no-reply@", "notifications@", "system@")):
        return False
    text = f"{subject} {body}".lower()
    if "platform notification" in text or "system notification" in text:
        return False
    return True


def insert_aggregate_thread(
    connection: sqlite3.Connection,
    *,
    email_id: str,
    thread_id: str | None = None,
    scenario: str | None = None,
) -> AggregateThread:
    now = datetime.now(timezone.utc)
    item = AggregateThread(
        thread_id=thread_id or f"THR-{uuid4().hex[:12].upper()}",
        email_id=email_id,
        scenario=scenario,
        status="WAITING_ANALYSIS",
        created_at=now,
        updated_at=now,
    )
    connection.execute(
        """INSERT INTO aggregate_threads
        (thread_id, email_id, scenario, ai_level, risk_level, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            item.thread_id,
            item.email_id,
            item.scenario,
            item.ai_level,
            item.risk_level,
            item.status,
            _iso(item.created_at),
            _iso(item.updated_at),
        ),
    )
    return item


def create_aggregate_thread(
    connection: sqlite3.Connection,
    *,
    email_id: str,
    thread_id: str | None = None,
    scenario: str | None = None,
) -> AggregateThread:
    item = insert_aggregate_thread(connection, email_id=email_id, thread_id=thread_id, scenario=scenario)
    connection.commit()
    return item


def get_aggregate_inbox(connection: sqlite3.Connection, *, pending_only: bool = False) -> list[dict[str, Any]]:
    query = """SELECT t.*, e.subject, e.body, e.sender_name, e.sender_email, e.received_at
               FROM aggregate_threads t JOIN emails e ON e.email_id = t.email_id"""
    params: tuple[Any, ...] = ()
    if pending_only:
        query += " WHERE t.status IN ('WAITING_ANALYSIS','AI_ANALYZING','WAITING_USER_CONFIRMATION','WAITING_HIGH_RISK_CHECK','FAILED')"
    query += " ORDER BY t.updated_at DESC"
    return [dict(row) for row in connection.execute(query, params).fetchall()]


def get_inbox_counts(connection: sqlite3.Connection) -> dict[str, int]:
    raw_count = int(connection.execute("SELECT COUNT(*) FROM emails").fetchone()[0])
    aggregate_count = int(connection.execute("SELECT COUNT(*) FROM aggregate_threads").fetchone()[0])
    pending_count = int(
        connection.execute(
            """SELECT COUNT(*) FROM aggregate_threads
            WHERE status IN ('WAITING_ANALYSIS','AI_ANALYZING','WAITING_USER_CONFIRMATION','WAITING_HIGH_RISK_CHECK','FAILED')"""
        ).fetchone()[0]
    )
    outbox_count = int(connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])
    return {
        "raw_inbox": raw_count,
        "aggregate_threads": aggregate_count,
        "pending_aggregate_threads": pending_count,
        "outbox": outbox_count,
    }
