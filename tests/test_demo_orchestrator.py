from __future__ import annotations

from pathlib import Path

from replyflow.db import connect_db, initialize_schema, seed_database
from replyflow.orchestrator import DemoOrchestrator


def _orchestrator(tmp_path: Path) -> tuple:
    connection = connect_db(tmp_path / "replyflow.sqlite3")
    initialize_schema(connection)
    seed_database(connection)
    return connection, DemoOrchestrator(connection)


def test_demo_mode_runs_three_preset_paths_with_local_tools(tmp_path: Path) -> None:
    connection, orchestrator = _orchestrator(tmp_path)
    try:
        low = orchestrator.run_preset_case("logistics", source_message_id="SRC-DEMO-LOGISTICS")
        medium = orchestrator.run_preset_case("missing_order", source_message_id="SRC-DEMO-MISSING")
        high = orchestrator.run_preset_case("refund_chargeback", source_message_id="SRC-DEMO-HIGH")

        assert (low.ai_level, low.risk_level, low.thread_status) == ("L1", "R0", "AI_REPLIED")
        assert low.outbox_id is not None
        assert "AUTO_REPLYING" in low.state_history
        assert (medium.ai_level, medium.risk_level, medium.thread_status) == ("L2", "R1", "WAITING_USER_CONFIRMATION")
        assert medium.outbox_id is None
        assert (high.ai_level, high.risk_level, high.thread_status) == ("L3", "R2", "WAITING_HIGH_RISK_CHECK")
        assert high.outbox_id is None
        assert "WAITING_HIGH_RISK_CHECK" in high.state_history
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM tool_traces").fetchone()[0] >= 15
        assert connection.execute("SELECT COUNT(*) FROM risk_decisions").fetchone()[0] == 3
    finally:
        connection.close()


def test_demo_mode_source_message_is_idempotent_after_processing(tmp_path: Path) -> None:
    connection, orchestrator = _orchestrator(tmp_path)
    try:
        first = orchestrator.run_preset_case("logistics", source_message_id="SRC-DEMO-REPLAY")
        second = orchestrator.run_preset_case("logistics", source_message_id="SRC-DEMO-REPLAY")

        assert first.outbox_id is not None
        assert second.replayed is True
        assert second.thread_status == "AI_REPLIED"
        assert second.outbox_id is None
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 1
    finally:
        connection.close()


def test_demo_mode_handles_long_unsupported_input_without_generic_answer(tmp_path: Path) -> None:
    connection, orchestrator = _orchestrator(tmp_path)
    try:
        result = orchestrator.run_demo_email(
            subject="Many questions",
            body="Please help. " + ("This message contains many details. " * 30),
            source_message_id="SRC-DEMO-LONG",
        )

        assert result.thread_status == "WAITING_USER_CONFIRMATION"
        assert result.ai_level == "L2"
        assert result.outbox_id is None
        assert result.notice and "Interactive Mode" in result.notice
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
    finally:
        connection.close()


def test_demo_mode_surfaces_configured_tool_failure_and_does_not_auto_send(tmp_path: Path) -> None:
    connection, orchestrator = _orchestrator(tmp_path)
    try:
        result = orchestrator.run_demo_email(
            subject="Where is my order?",
            body="Please check tracking for ORD-1012.",
            sender_email="buyer12@example.com",
            source_message_id="SRC-DEMO-TOOL-FAIL",
        )

        assert result.thread_status == "WAITING_HIGH_RISK_CHECK"
        assert result.ai_level == "L3"
        assert result.risk_level == "R2"
        assert result.outbox_id is None
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
        trace = connection.execute(
            "SELECT COUNT(*) FROM tool_traces WHERE tool_name = 'get_shipping_status' AND error_code = 'TOOL_TIMEOUT'"
        ).fetchone()[0]
        assert trace == 1
    finally:
        connection.close()


def test_demo_mode_unknown_preset_is_rejected(tmp_path: Path) -> None:
    connection, orchestrator = _orchestrator(tmp_path)
    try:
        try:
            orchestrator.run_preset_case("not-a-case")
        except ValueError as error:
            assert "Unknown Demo Mode preset" in str(error)
        else:
            raise AssertionError("unknown preset should be rejected")
    finally:
        connection.close()
