from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from replyflow.db import connect_db, initialize_schema, seed_database, transaction


EXPECTED_TABLES = {
    "emails",
    "aggregate_threads",
    "orders",
    "shipping_events",
    "reply_basis",
    "reply_drafts",
    "outbox",
    "task_runs",
    "tool_traces",
    "risk_decisions",
    "confirmations",
    "audit_logs",
    "idempotency_keys",
    "evaluation_results",
}


def test_schema_is_idempotent_and_contains_only_allowed_tables(tmp_path: Path) -> None:
    connection = connect_db(tmp_path / "replyflow.sqlite3")
    try:
        initialize_schema(connection)
        initialize_schema(connection)
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        assert tables == EXPECTED_TABLES
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        connection.close()


def test_seed_database_is_idempotent(tmp_path: Path) -> None:
    connection = connect_db(tmp_path / "replyflow.sqlite3")
    try:
        initialize_schema(connection)
        first = seed_database(connection)
        second = seed_database(connection)
        assert first == {"emails": 30, "orders": 20, "shipping_events": 52, "reply_basis": 16}
        assert second == first
        for table, expected in (("emails", 30), ("orders", 20), ("shipping_events", 52), ("reply_basis", 16)):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == expected
        assert connection.execute("SELECT COUNT(*) FROM aggregate_threads").fetchone()[0] == 0
    finally:
        connection.close()


def test_transaction_rolls_back_all_writes(tmp_path: Path) -> None:
    connection = connect_db(tmp_path / "replyflow.sqlite3")
    try:
        initialize_schema(connection)
        with pytest.raises(RuntimeError):
            with transaction(connection):
                connection.execute(
                    "INSERT INTO emails(email_id, source_message_id, sender_name, sender_email, subject, body, received_at, source, created_at) VALUES ('E-TX', 'S-TX', 'Demo', 'demo@example.com', 'x', 'x', '2026-08-21T00:00:00Z', 'demo', '2026-08-21T00:00:00Z')"
                )
                raise RuntimeError("rollback test")
        assert connection.execute("SELECT COUNT(*) FROM emails WHERE email_id = 'E-TX'").fetchone()[0] == 0
    finally:
        connection.close()


def test_schema_rejects_missing_foreign_parent(tmp_path: Path) -> None:
    connection = connect_db(tmp_path / "replyflow.sqlite3")
    try:
        initialize_schema(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO shipping_events(event_id, order_id, event_time, location, status, description) VALUES ('S-X', 'ORD-NOT-FOUND', '2026-08-21T00:00:00Z', 'x', 'x', 'x')"
            )
            connection.commit()
    finally:
        connection.close()
