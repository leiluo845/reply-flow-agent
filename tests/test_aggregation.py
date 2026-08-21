from __future__ import annotations

from pathlib import Path

from replyflow.aggregation import get_aggregate_inbox, get_inbox_counts, is_buyer_message
from replyflow.db import connect_db, initialize_schema, seed_database
from replyflow.ingestion import ingest_simulated_email


def test_source_classifier_keeps_non_buyer_boundary_explicit() -> None:
    assert is_buyer_message(source="demo_console", sender_email="buyer@example.com", subject="Help", body="Hi")
    assert not is_buyer_message(
        source="platform_notification",
        sender_email="notifications@example.com",
        subject="Notice",
        body="Platform notification",
    )


def test_aggregate_inbox_is_sorted_by_latest_update(tmp_path: Path) -> None:
    connection = connect_db(tmp_path / "replyflow.sqlite3")
    try:
        initialize_schema(connection)
        seed_database(connection)
        first = ingest_simulated_email(connection, body="First message", source_message_id="SRC-A")
        second = ingest_simulated_email(connection, body="Second message", source_message_id="SRC-B")
        rows = get_aggregate_inbox(connection)
        assert {row["thread_id"] for row in rows} == {first.thread_id, second.thread_id}
        assert rows[0]["thread_id"] == second.thread_id
        assert get_inbox_counts(connection)["pending_aggregate_threads"] == 2
    finally:
        connection.close()
