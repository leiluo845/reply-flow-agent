from __future__ import annotations

import asyncio
from pathlib import Path

from replyflow.db import connect_db, initialize_schema, seed_database
from replyflow.mcp_tools import TOOL_NAMES, ReplyFlowTools, create_mcp_server


def _fixture(tmp_path: Path):
    connection = connect_db(tmp_path / "replyflow.sqlite3")
    initialize_schema(connection)
    seed_database(connection)
    return connection, ReplyFlowTools(connection)


def test_mcp_server_exposes_exactly_eight_tools(tmp_path: Path) -> None:
    connection, _ = _fixture(tmp_path)
    try:
        server = create_mcp_server(connection)

        async def list_names() -> list[str]:
            return [tool.name for tool in await server.list_tools()]

        assert asyncio.run(list_names()) == list(TOOL_NAMES)
    finally:
        connection.close()


def test_read_tools_return_facts_and_structured_not_found_errors(tmp_path: Path) -> None:
    connection, tools = _fixture(tmp_path)
    try:
        email = tools.get_email(email_id="EML-0001")
        assert email["ok"] is True
        assert email["data"]["email"]["email_id"] == "EML-0001"
        assert email["data"]["email"]["attachments"] == []

        missing_email = tools.get_email(email_id="EML-NOT-FOUND")
        assert missing_email["ok"] is False
        assert missing_email["error_code"] == "EMAIL_NOT_FOUND"

        invalid_email = tools.get_email(email_id="", unexpected="not allowed")
        assert invalid_email["ok"] is False
        assert invalid_email["error_code"] == "INVALID_INPUT"
        assert invalid_email["trace_id"].startswith("TRACE-")

        order = tools.find_order(order_id="ORD-1001")
        assert order["ok"] is True
        assert order["data"]["orders"][0]["order_id"] == "ORD-1001"

        customer_orders = tools.find_order(customer_email="buyer01@example.com")
        assert customer_orders["ok"] is True
        assert customer_orders["data"]["orders"][0]["customer_email"] == "buyer01@example.com"

        missing_order = tools.find_order(order_id="ORD-9999")
        assert missing_order["ok"] is False
        assert missing_order["error_code"] == "ORDER_NOT_FOUND"

        shipping = tools.get_shipping_status(order_id="ORD-1001")
        assert shipping["ok"] is True
        assert shipping["data"]["latest"]["status"] == "In transit"

        basis = tools.search_reply_basis(query="carrier status")
        assert basis["ok"] is True
        assert basis["data"]["results"][0]["version"] == "1.0"

        tone = tools.get_reply_tone()
        assert tone["ok"] is True
        assert len(tone["data"]["tone"]) == 4
    finally:
        connection.close()


def test_ingest_tool_creates_trace_and_aggregate_thread(tmp_path: Path) -> None:
    connection, tools = _fixture(tmp_path)
    try:
        result = tools.ingest_simulated_email(body="Where is order ORD-1001?", source_message_id="SRC-TOOL-001")
        assert result["ok"] is True
        assert result["data"]["thread_status"] == "WAITING_ANALYSIS"
        trace = connection.execute("SELECT tool_name, status FROM tool_traces WHERE trace_id = ?", (result["trace_id"],)).fetchone()
        assert tuple(trace) == ("ingest_simulated_email", "SUCCESS")
    finally:
        connection.close()


def test_write_tools_enforce_confirmation_and_idempotency(tmp_path: Path) -> None:
    connection, tools = _fixture(tmp_path)
    try:
        ingested = tools.ingest_simulated_email(body="Where is order ORD-1001?", source_message_id="SRC-TOOL-002")
        thread_id = ingested["data"]["thread_id"]

        blocked_draft = tools.save_reply_draft(
            thread_id=thread_id,
            agent_content="Hello",
            confirmed=False,
            operation_id="draft-op-1",
        )
        assert blocked_draft["ok"] is False
        assert blocked_draft["error_code"] == "CONFIRMATION_REQUIRED"

        missing_thread = tools.save_reply_draft(
            thread_id="THR-NOT-FOUND",
            agent_content="Hello",
            confirmed=True,
            operation_id="draft-op-missing-thread",
        )
        assert missing_thread["ok"] is False
        assert missing_thread["error_code"] == "THREAD_NOT_FOUND"

        draft = tools.save_reply_draft(
            thread_id=thread_id,
            agent_content="Hello",
            confirmed=True,
            operation_id="draft-op-1",
        )
        assert draft["ok"] is True
        replay_draft = tools.save_reply_draft(
            thread_id=thread_id,
            agent_content="Hello",
            confirmed=True,
            operation_id="draft-op-1",
        )
        assert replay_draft["ok"] is True
        assert replay_draft["data"]["replayed"] is True
        conflict_draft = tools.save_reply_draft(
            thread_id=thread_id,
            agent_content="Changed",
            confirmed=True,
            operation_id="draft-op-1",
        )
        assert conflict_draft["ok"] is False
        assert conflict_draft["error_code"] == "IDEMPOTENCY_CONFLICT"

        blocked_send = tools.send_simulated_reply(
            thread_id=thread_id,
            recipient="buyer@example.com",
            body="Hello",
            confirmed=False,
            operation_id="send-op-1",
        )
        assert blocked_send["ok"] is False
        assert blocked_send["error_code"] == "CONFIRMATION_REQUIRED"

        sent = tools.send_simulated_reply(
            thread_id=thread_id,
            recipient="buyer@example.com",
            body="Hello",
            confirmed=True,
            operation_id="send-op-1",
        )
        assert sent["ok"] is True
        assert sent["data"]["replayed"] is False
        replay_sent = tools.send_simulated_reply(
            thread_id=thread_id,
            recipient="buyer@example.com",
            body="Hello",
            confirmed=True,
            operation_id="send-op-1",
        )
        assert replay_sent["ok"] is True
        assert replay_sent["data"]["replayed"] is True
        conflict_sent = tools.send_simulated_reply(
            thread_id=thread_id,
            recipient="buyer@example.com",
            body="Changed",
            confirmed=True,
            operation_id="send-op-1",
        )
        assert conflict_sent["ok"] is False
        assert conflict_sent["error_code"] == "IDEMPOTENCY_CONFLICT"
        assert connection.execute("SELECT COUNT(*) FROM reply_drafts").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0] == 2
        trace_text = " ".join(
            row[0]
            for row in connection.execute("SELECT input_summary FROM tool_traces").fetchall()
            if row[0]
        )
        assert "Changed" not in trace_text
    finally:
        connection.close()
