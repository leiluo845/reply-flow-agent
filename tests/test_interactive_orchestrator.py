from __future__ import annotations

from pathlib import Path

from replyflow.coze_client import AnalyzeOutput, CozeError, DraftOutput
from replyflow.db import connect_db, initialize_schema, seed_database
from replyflow.interactive_orchestrator import InteractiveOrchestrator


class FakeInteractiveClient:
    def __init__(self, *, intent: str = "shipping_status", is_buyer_message: bool = True, draft_body: str = "Hello, the verified status is in transit.", error: CozeError | None = None):
        self.intent = intent
        self.is_buyer_message = is_buyer_message
        self.draft_body = draft_body
        self.error = error
        self.analyze_calls: list[dict] = []
        self.draft_calls: list[dict] = []

    def analyze(self, *, subject: str, body: str, order_context_id: str | None = None) -> AnalyzeOutput:
        self.analyze_calls.append({"subject": subject, "body": body, "order_context_id": order_context_id})
        if self.error:
            raise self.error
        order_id = "ORD-1001" if "ORD-1001" in body else None
        return AnalyzeOutput(
            is_buyer_message=self.is_buyer_message,
            intent=self.intent,
            order_id=order_id,
            missing_fields=[] if order_id else ["order_id"],
            confidence=0.95,
        )

    def draft(self, *, email_json, verified_facts_json, reply_basis_json, risk_context_json) -> DraftOutput:
        self.draft_calls.append(
            {
                "email_json": email_json,
                "verified_facts_json": verified_facts_json,
                "reply_basis_json": reply_basis_json,
                "risk_context_json": risk_context_json,
            }
        )
        if self.error:
            raise self.error
        return DraftOutput(
            draft_subject="Re: Your message",
            draft_body=self.draft_body,
            used_basis=["basis-logistics-v1#delivery-status"],
            uncertainties=[],
        )


def _orchestrator(tmp_path: Path, client: FakeInteractiveClient):
    connection = connect_db(tmp_path / "replyflow.sqlite3")
    initialize_schema(connection)
    seed_database(connection)
    return connection, InteractiveOrchestrator(connection, client)


def test_interactive_orchestrator_keeps_business_control_local(tmp_path: Path) -> None:
    client = FakeInteractiveClient()
    connection, orchestrator = _orchestrator(tmp_path, client)
    try:
        result = orchestrator.run(
            subject="Where is my order?",
            body="Could you check tracking for ORD-1001?",
            sender_email="buyer01@example.com",
            source_message_id="SRC-INTERACTIVE-001",
        )

        assert (result.ai_level, result.risk_level, result.thread_status) == ("L1", "R0", "AI_REPLIED")
        assert result.outbox_id is not None
        assert len(client.analyze_calls) == 1
        assert len(client.draft_calls) == 1
        draft_call = client.draft_calls[0]
        assert draft_call["verified_facts_json"]["order_found"] is True
        assert "ORD-1001" in json_dumps(draft_call["verified_facts_json"])
        assert "expected" not in json_dumps(draft_call).lower()
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 1
    finally:
        connection.close()


def test_interactive_high_risk_stops_before_outbox(tmp_path: Path) -> None:
    client = FakeInteractiveClient(intent="chargeback_threat", draft_body="We will refund you immediately.")
    connection, orchestrator = _orchestrator(tmp_path, client)
    try:
        result = orchestrator.run(
            subject="Chargeback warning",
            body="Refund me or I will file a chargeback. ORD-1001.",
            sender_email="buyer01@example.com",
            source_message_id="SRC-INTERACTIVE-002",
        )

        assert result.thread_status == "WAITING_HIGH_RISK_CHECK"
        assert result.ai_level == "L3"
        assert result.risk_level == "R2"
        assert result.outbox_id is None
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
    finally:
        connection.close()


def test_interactive_model_error_marks_thread_failed_without_faking_result(tmp_path: Path) -> None:
    client = FakeInteractiveClient(error=CozeError("COZE_TIMEOUT", "Coze timed out", retryable=True))
    connection, orchestrator = _orchestrator(tmp_path, client)
    try:
        result = orchestrator.run(body="Where is my order?", source_message_id="SRC-INTERACTIVE-003")

        assert result.thread_status == "FAILED"
        assert result.error_code == "COZE_TIMEOUT"
        assert result.outbox_id is None
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
    finally:
        connection.close()


def test_interactive_model_can_classify_non_buyer_and_stops_reply_flow(tmp_path: Path) -> None:
    client = FakeInteractiveClient(is_buyer_message=False, intent="non_buyer_message")
    connection, orchestrator = _orchestrator(tmp_path, client)
    try:
        result = orchestrator.run(
            body="Platform notification: listing update.",
            sender_email="notifications@example.com",
            source_message_id="SRC-INTERACTIVE-004",
            # Demo source is still used for a controlled input; Analyze is authoritative for Interactive Mode.
        )

        assert result.thread_status == "NOT_BUYER_MESSAGE"
        assert result.outbox_id is None
        assert len(client.draft_calls) == 0
    finally:
        connection.close()


def json_dumps(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, default=str)
