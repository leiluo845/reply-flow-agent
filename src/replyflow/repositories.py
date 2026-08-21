from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .db import payload_hash, utc_now
from .models import AggregateThread, EmailRecord, OrderRecord, ShippingEvent


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


class EmailRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def add(self, email: EmailRecord) -> bool:
        cursor = self.connection.execute(
            """INSERT OR IGNORE INTO emails
            (email_id, source_message_id, sender_name, sender_email, subject, body,
             received_at, source, order_context_id, attachments_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                email.email_id,
                email.source_message_id,
                email.sender_name,
                email.sender_email,
                email.subject,
                email.body,
                _iso(email.received_at),
                email.source,
                email.order_context_id,
                json.dumps(email.attachments, ensure_ascii=False),
                email.status,
                utc_now(),
            ),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def get(self, email_id: str) -> dict[str, Any] | None:
        return _row_dict(self.connection.execute("SELECT * FROM emails WHERE email_id = ?", (email_id,)).fetchone())

    def get_by_source_message_id(self, source_message_id: str) -> dict[str, Any] | None:
        return _row_dict(
            self.connection.execute("SELECT * FROM emails WHERE source_message_id = ?", (source_message_id,)).fetchone()
        )

    def count(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM emails").fetchone()[0])


class OrderRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def get(self, order_id: str) -> dict[str, Any] | None:
        return _row_dict(self.connection.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone())

    def list_shipping_events(self, order_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM shipping_events WHERE order_id = ? ORDER BY event_time ASC", (order_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def find_by_customer_email(self, customer_email: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM orders WHERE customer_email = ? ORDER BY ordered_at DESC", (customer_email,)
        ).fetchall()
        return [dict(row) for row in rows]


class ThreadRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def create(
        self,
        *,
        email_id: str,
        thread_id: str | None = None,
        scenario: str | None = None,
        ai_level: str | None = None,
        risk_level: str | None = None,
        status: str = "WAITING_ANALYSIS",
    ) -> AggregateThread:
        now = datetime.now(timezone.utc)
        item = AggregateThread(
            thread_id=thread_id or f"THR-{uuid4().hex[:12].upper()}",
            email_id=email_id,
            scenario=scenario,
            ai_level=ai_level,
            risk_level=risk_level,
            status=status,
            created_at=now,
            updated_at=now,
        )
        self.connection.execute(
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
        self.connection.commit()
        return item

    def get(self, thread_id: str) -> dict[str, Any] | None:
        return _row_dict(
            self.connection.execute(
                """SELECT t.*, e.subject, e.body, e.sender_name, e.sender_email
                FROM aggregate_threads t JOIN emails e ON e.email_id = t.email_id
                WHERE t.thread_id = ?""",
                (thread_id,),
            ).fetchone()
        )

    def list_recent(self, *, status: str | None = None) -> list[dict[str, Any]]:
        query = """SELECT t.*, e.subject, e.body, e.sender_name, e.sender_email
                   FROM aggregate_threads t JOIN emails e ON e.email_id = t.email_id"""
        params: tuple[Any, ...] = ()
        if status:
            query += " WHERE t.status = ?"
            params = (status,)
        query += " ORDER BY t.updated_at DESC"
        return [dict(row) for row in self.connection.execute(query, params).fetchall()]

    def update_status(self, thread_id: str, status: str, *, ai_level: str | None = None, risk_level: str | None = None) -> None:
        self.connection.execute(
            """UPDATE aggregate_threads
            SET status = ?, ai_level = COALESCE(?, ai_level), risk_level = COALESCE(?, risk_level), updated_at = ?
            WHERE thread_id = ?""",
            (status, ai_level, risk_level, utc_now(), thread_id),
        )
        self.connection.commit()

    def count(self, *, pending_only: bool = False) -> int:
        query = "SELECT COUNT(*) FROM aggregate_threads"
        params: tuple[Any, ...] = ()
        if pending_only:
            query += " WHERE status IN ('WAITING_ANALYSIS','AI_ANALYZING','WAITING_USER_CONFIRMATION','WAITING_HIGH_RISK_CHECK','FAILED')"
        return int(self.connection.execute(query, params).fetchone()[0])


class IdempotencyRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def reserve(self, operation_id: str, action: str, payload: object, *, result_ref: str | None = None) -> str:
        digest = payload_hash(payload)
        row = self.connection.execute(
            "SELECT payload_hash FROM idempotency_keys WHERE operation_id = ?", (operation_id,)
        ).fetchone()
        if row:
            return "REPLAY" if row[0] == digest else "IDEMPOTENCY_CONFLICT"
        self.connection.execute(
            """INSERT INTO idempotency_keys(operation_id, action, payload_hash, result_ref, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            (operation_id, action, digest, result_ref, utc_now()),
        )
        self.connection.commit()
        return "NEW"

    def get(self, operation_id: str) -> dict[str, Any] | None:
        return _row_dict(self.connection.execute("SELECT * FROM idempotency_keys WHERE operation_id = ?", (operation_id,)).fetchone())


class OutboxRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def count(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])

    def list_recent(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM outbox ORDER BY simulated_sent_at DESC").fetchall()]
