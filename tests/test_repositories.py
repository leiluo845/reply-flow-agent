from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from replyflow.db import connect_db, initialize_schema, seed_database
from replyflow.models import EmailRecord
from replyflow.repositories import EmailRepository, IdempotencyRepository, OrderRepository, OutboxRepository, ThreadRepository


def _connection(tmp_path: Path):
    connection = connect_db(tmp_path / "replyflow.sqlite3")
    initialize_schema(connection)
    seed_database(connection)
    return connection


def test_order_and_shipping_queries_return_verified_seed_rows(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        orders = OrderRepository(connection)
        order = orders.get("ORD-1001")
        assert order is not None
        assert order["fulfillment_status"] == "in_transit"
        events = orders.list_shipping_events("ORD-1001")
        assert len(events) == 3
        assert events[-1]["status"] == "In transit"
    finally:
        connection.close()


def test_email_insert_is_idempotent_by_source_message_id(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        repo = EmailRepository(connection)
        email = EmailRecord(
            email_id="EML-NEW",
            source_message_id="SRC-20260820-0001",
            sender_name="Replay Buyer",
            sender_email="replay@example.com",
            subject="Duplicate",
            body="This should not create a second row.",
            received_at=datetime.now(timezone.utc),
            source="demo_console",
        )
        assert repo.add(email) is False
        assert repo.count() == 30
        assert repo.get_by_source_message_id(email.source_message_id)["email_id"] == "EML-0001"
    finally:
        connection.close()


def test_thread_aggregation_query_and_status_update(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        threads = ThreadRepository(connection)
        created = threads.create(email_id="EML-0001", scenario="shipment_inquiry", ai_level="L1", risk_level="R0")
        assert threads.count() == 1
        assert threads.count(pending_only=True) == 1
        row = threads.get(created.thread_id)
        assert row is not None
        assert row["subject"] == "Where is my order?"
        threads.update_status(created.thread_id, "AI_REPLIED")
        assert threads.count(pending_only=True) == 0
        assert threads.list_recent()[0]["status"] == "AI_REPLIED"
    finally:
        connection.close()


def test_operation_id_replay_and_conflict(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        repo = IdempotencyRepository(connection)
        assert repo.reserve("op-1", "send_simulated_reply", {"body": "hello"}) == "NEW"
        assert repo.reserve("op-1", "send_simulated_reply", {"body": "hello"}) == "REPLAY"
        assert repo.reserve("op-1", "send_simulated_reply", {"body": "changed"}) == "IDEMPOTENCY_CONFLICT"
        assert repo.get("op-1")["action"] == "send_simulated_reply"
    finally:
        connection.close()


def test_outbox_starts_empty_and_is_queryable(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    try:
        repo = OutboxRepository(connection)
        assert repo.count() == 0
        assert repo.list_recent() == []
    finally:
        connection.close()
