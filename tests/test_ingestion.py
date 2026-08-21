from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from replyflow.aggregation import get_aggregate_inbox, get_inbox_counts
from replyflow.db import connect_db, initialize_schema, seed_database
from replyflow.ingestion import IngestionError, ingest_simulated_email


@pytest.fixture
def connection(tmp_path: Path):
    db = connect_db(tmp_path / "replyflow.sqlite3")
    initialize_schema(db)
    seed_database(db)
    yield db
    db.close()


def test_one_line_buyer_email_reaches_raw_and_aggregate_inbox(connection) -> None:
    before = get_inbox_counts(connection)
    result = ingest_simulated_email(
        connection,
        body="Hi, where is order ORD-1001?",
        subject="Where is my order?",
        sender_name="Demo Buyer",
        sender_email="new-buyer@example.com",
        source_message_id="SRC-DEMO-001",
        received_at=datetime(2026, 8, 21, tzinfo=timezone.utc),
    )
    after = get_inbox_counts(connection)

    assert result.duplicate is False
    assert result.is_buyer_message is True
    assert result.email_status == "AGGREGATED_AS_STATION_MESSAGE"
    assert result.thread_status == "WAITING_ANALYSIS"
    assert after["raw_inbox"] == before["raw_inbox"] + 1
    assert after["aggregate_threads"] == before["aggregate_threads"] + 1
    assert after["pending_aggregate_threads"] == before["pending_aggregate_threads"] + 1
    row = connection.execute("SELECT * FROM emails WHERE email_id = ?", (result.email_id,)).fetchone()
    assert row["order_context_id"] is None
    assert get_aggregate_inbox(connection)[0]["thread_id"] == result.thread_id


def test_optional_order_context_is_stored_as_context_only(connection) -> None:
    result = ingest_simulated_email(
        connection,
        body="Could you check my package?",
        order_context_id="ORD-1001",
        source_message_id="SRC-DEMO-002",
    )
    row = connection.execute("SELECT order_context_id FROM emails WHERE email_id = ?", (result.email_id,)).fetchone()
    assert row["order_context_id"] == "ORD-1001"
    assert result.thread_id is not None


def test_blank_subject_and_sender_receive_fictional_defaults(connection) -> None:
    result = ingest_simulated_email(connection, body="Please help me find my package.")
    row = connection.execute(
        "SELECT subject, sender_name, sender_email FROM emails WHERE email_id = ?", (result.email_id,)
    ).fetchone()
    assert row["subject"] == "Message from buyer"
    assert row["sender_name"] == "Demo Buyer"
    assert row["sender_email"].endswith("@example.com")


def test_empty_body_is_rejected_without_database_changes(connection) -> None:
    before = get_inbox_counts(connection)
    with pytest.raises(IngestionError) as error:
        ingest_simulated_email(connection, body="   ")
    assert error.value.code == "EMAIL_EMPTY"
    assert get_inbox_counts(connection) == before


def test_non_buyer_message_stays_in_raw_inbox(connection) -> None:
    before = get_inbox_counts(connection)
    result = ingest_simulated_email(
        connection,
        body="Platform notification: your account settings were updated.",
        subject="Platform notification",
        sender_name="Demo Platform",
        sender_email="notifications@example.com",
        source="platform_notification",
        source_message_id="SRC-DEMO-003",
    )
    after = get_inbox_counts(connection)

    assert result.is_buyer_message is False
    assert result.email_status == "NOT_BUYER_MESSAGE"
    assert result.thread_id is None
    assert after["raw_inbox"] == before["raw_inbox"] + 1
    assert after["aggregate_threads"] == before["aggregate_threads"]


def test_duplicate_source_message_is_idempotent(connection) -> None:
    first_kwargs = {
        "body": "Where is order ORD-1002?",
        "source_message_id": "SRC-DEMO-DUPLICATE",
        "sender_email": "duplicate@example.com",
    }
    first = ingest_simulated_email(connection, **first_kwargs)
    counts_after_first = get_inbox_counts(connection)
    second = ingest_simulated_email(
        connection,
        body="Changed body should be ignored.",
        source_message_id="SRC-DEMO-DUPLICATE",
        sender_email="duplicate@example.com",
    )
    counts_after_second = get_inbox_counts(connection)

    assert first.duplicate is False
    assert second.duplicate is True
    assert second.email_id == first.email_id
    assert second.thread_id == first.thread_id
    assert counts_after_second == counts_after_first
