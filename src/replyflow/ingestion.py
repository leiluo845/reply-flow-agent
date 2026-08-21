from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from .aggregation import insert_aggregate_thread, is_buyer_message
from .db import transaction, utc_now


class IngestionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class IngestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email_id: str
    source_message_id: str
    email_status: str
    is_buyer_message: bool
    thread_id: str | None = None
    thread_status: str | None = None
    duplicate: bool = False


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _generated_sender() -> tuple[str, str]:
    token = uuid4().hex[:8]
    return "Demo Buyer", f"buyer-{token}@example.com"


def ingest_simulated_email(
    connection: sqlite3.Connection,
    *,
    body: str,
    subject: str | None = None,
    sender_name: str | None = None,
    sender_email: str | None = None,
    source: str = "demo_console",
    source_message_id: str | None = None,
    order_context_id: str | None = None,
    received_at: datetime | None = None,
) -> IngestionResult:
    """Write one fictional email and, when applicable, create its top inbox thread."""
    normalized_body = body.strip()
    if not normalized_body:
        raise IngestionError("EMAIL_EMPTY", "Email body cannot be empty.")

    generated_name, generated_email = _generated_sender()
    final_sender_name = sender_name.strip() if sender_name and sender_name.strip() else generated_name
    final_sender_email = sender_email.strip() if sender_email and sender_email.strip() else generated_email

    final_subject = subject.strip() if subject and subject.strip() else "Message from buyer"
    final_source_message_id = source_message_id or f"SRC-DEMO-{uuid4().hex[:12].upper()}"
    final_email_id = f"EML-DEMO-{uuid4().hex[:12].upper()}"
    final_received_at = received_at or datetime.now(timezone.utc)
    buyer_message = is_buyer_message(
        source=source,
        sender_email=final_sender_email,
        subject=final_subject,
        body=normalized_body,
    )

    with transaction(connection):
        existing = connection.execute(
            "SELECT email_id, source_message_id, status FROM emails WHERE source_message_id = ?",
            (final_source_message_id,),
        ).fetchone()
        if existing:
            existing_thread = connection.execute(
                "SELECT thread_id, status FROM aggregate_threads WHERE email_id = ? ORDER BY created_at LIMIT 1",
                (existing["email_id"],),
            ).fetchone()
            return IngestionResult(
                email_id=existing["email_id"],
                source_message_id=existing["source_message_id"],
                email_status=existing["status"],
                is_buyer_message=existing_thread is not None,
                thread_id=existing_thread["thread_id"] if existing_thread else None,
                thread_status=existing_thread["status"] if existing_thread else None,
                duplicate=True,
            )

        connection.execute(
            """INSERT INTO emails
            (email_id, source_message_id, sender_name, sender_email, subject, body,
             received_at, source, order_context_id, attachments_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?)""",
            (
                final_email_id,
                final_source_message_id,
                final_sender_name,
                final_sender_email,
                final_subject,
                normalized_body,
                _iso(final_received_at),
                source,
                order_context_id,
                "RECEIVING",
                utc_now(),
            ),
        )
        connection.execute("UPDATE emails SET status = 'RECEIVED' WHERE email_id = ?", (final_email_id,))
        connection.execute("UPDATE emails SET status = 'WRITTEN_TO_INBOX' WHERE email_id = ?", (final_email_id,))
        if not buyer_message:
            connection.execute("UPDATE emails SET status = 'NOT_BUYER_MESSAGE' WHERE email_id = ?", (final_email_id,))
            return IngestionResult(
                email_id=final_email_id,
                source_message_id=final_source_message_id,
                email_status="NOT_BUYER_MESSAGE",
                is_buyer_message=False,
            )

        connection.execute("UPDATE emails SET status = 'CLASSIFYING_SOURCE' WHERE email_id = ?", (final_email_id,))
        thread = insert_aggregate_thread(connection, email_id=final_email_id)
        connection.execute(
            "UPDATE emails SET status = 'AGGREGATED_AS_STATION_MESSAGE' WHERE email_id = ?",
            (final_email_id,),
        )
        return IngestionResult(
            email_id=final_email_id,
            source_message_id=final_source_message_id,
            email_status="AGGREGATED_AS_STATION_MESSAGE",
            is_buyer_message=True,
            thread_id=thread.thread_id,
            thread_status=thread.status,
        )
