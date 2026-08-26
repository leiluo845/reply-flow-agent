from __future__ import annotations

import json
import re
from pathlib import Path

from replyflow.coze_client import AnalyzeOutput, DraftOutput, CozeError
from replyflow.db import connect_db, initialize_schema, seed_database
from replyflow.interactive_orchestrator import InteractiveOrchestrator
from replyflow.mcp_tools import ReplyFlowTools
from replyflow.ui_helpers import can_send


class FakeCozeClient:
    """Deterministic Coze stand-in used to exercise the full local control loop."""

    def __init__(self, *, intent: str, draft_body: str = "Thanks for contacting us. We are checking this for you.", error: CozeError | None = None):
        self.intent = intent
        self.draft_body = draft_body
        self.error = error

    def analyze(self, *, subject: str, body: str, order_context_id: str | None = None) -> AnalyzeOutput:
        if self.error:
            raise self.error
        match = re.search(r"\bORD-\d+\b", body)
        order_id = match.group(0) if match else None
        return AnalyzeOutput(
            is_buyer_message=True,
            intent=self.intent,  # type: ignore[arg-type]
            order_id=order_id,
            missing_fields=[] if order_id else ["order_id"],
            confidence=0.95,
        )

    def draft(self, *, email_json, verified_facts_json, reply_basis_json, risk_context_json) -> DraftOutput:
        if self.error:
            raise self.error
        return DraftOutput(
            draft_subject="Re: Your message",
            draft_body=self.draft_body,
            used_basis=["basis-logistics-v1#delivery-status"],
            uncertainties=[],
        )


def _fixture(tmp_path: Path):
    connection = connect_db(tmp_path / "replyflow.sqlite3")
    initialize_schema(connection)
    seed_database(connection)
    return connection


def _send_args(connection, thread_id: str, body: str, operation_id: str, *, confirmed: bool, checklist: dict[str, bool] | None = None) -> dict:
    email = connection.execute(
        """SELECT e.sender_email, e.subject
           FROM emails e JOIN aggregate_threads t ON t.email_id = e.email_id
           WHERE t.thread_id = ?""",
        (thread_id,),
    ).fetchone()
    return ReplyFlowTools(connection).send_simulated_reply(
        thread_id=thread_id,
        recipient=email["sender_email"],
        subject=f"Re: {email['subject']}",
        body=body,
        confirmed=confirmed,
        checklist=checklist or {},
        operation_id=operation_id,
    )


def test_l1_auto_send_has_trace_audit_and_matching_ai_final_copy(tmp_path: Path) -> None:
    connection = _fixture(tmp_path)
    try:
        result = InteractiveOrchestrator(connection, FakeCozeClient(intent="shipping_status", draft_body="Your package is in transit.")).run(
            subject="Where is my order?",
            body="Where is order ORD-1001?",
            sender_email="buyer01@example.com",
            source_message_id="E2E-L1-001",
        )

        assert (result.ai_level, result.risk_level, result.thread_status) == ("L1", "R0", "AI_REPLIED")
        assert result.outbox_id and result.draft_id
        draft = connection.execute("SELECT * FROM reply_drafts WHERE draft_id = ?", (result.draft_id,)).fetchone()
        outbox = connection.execute("SELECT * FROM outbox WHERE outbox_id = ?", (result.outbox_id,)).fetchone()
        assert draft["edited_content"] is None
        assert draft["agent_content"] == outbox["body"] == "Your package is in transit."
        assert result.trace_ids and all(trace.startswith("TRACE-") for trace in result.trace_ids)
        assert connection.execute("SELECT COUNT(*) FROM audit_logs WHERE task_id = ?", (result.task_id,)).fetchone()[0] >= 1
        traced = connection.execute(
            "SELECT COUNT(*) FROM tool_traces WHERE trace_id IN ({})".format(",".join("?" for _ in result.trace_ids)),
            tuple(result.trace_ids),
        ).fetchone()[0]
        assert traced == len(result.trace_ids)
    finally:
        connection.close()


def test_l2_requires_confirmation_then_preserves_ai_edit_and_final_send(tmp_path: Path) -> None:
    connection = _fixture(tmp_path)
    try:
        result = InteractiveOrchestrator(connection, FakeCozeClient(intent="size_or_fit", draft_body="Please confirm the size you received.")).run(
            subject="The jacket is too small",
            body="The jacket is too small. Can I exchange it? Order ORD-1002.",
            sender_email="buyer02@example.com",
            source_message_id="E2E-L2-001",
        )
        assert (result.ai_level, result.risk_level, result.thread_status) == ("L2", "R1", "WAITING_USER_CONFIRMATION")
        draft = connection.execute("SELECT * FROM reply_drafts WHERE draft_id = ?", (result.draft_id,)).fetchone()
        assert draft["edited_content"] is None

        blocked = _send_args(connection, result.thread_id, "Please confirm the size you received.", "E2E-L2-BLOCKED", confirmed=False)
        assert blocked["ok"] is False
        assert blocked["error_code"] == "CONFIRMATION_REQUIRED"
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0

        edited = "Please confirm the size you received and the size you need."
        saved = ReplyFlowTools(connection).save_reply_draft(
            thread_id=result.thread_id,
            agent_content=draft["agent_content"],
            edited_content=edited,
            ai_level="L2",
            risk_level="R1",
            confirmed=True,
            operation_id="E2E-L2-DRAFT-EDIT",
        )
        assert saved["ok"] is True
        sent = _send_args(connection, result.thread_id, edited, "E2E-L2-SEND", confirmed=True)
        assert sent["ok"] is True
        assert connection.execute("SELECT body FROM outbox").fetchone()[0] == edited
        assert connection.execute("SELECT edited_content FROM reply_drafts ORDER BY updated_at DESC LIMIT 1").fetchone()[0] == edited
    finally:
        connection.close()


def test_l3_requires_full_checklist_at_ui_and_tool_boundaries(tmp_path: Path) -> None:
    connection = _fixture(tmp_path)
    try:
        result = InteractiveOrchestrator(
            connection,
            FakeCozeClient(intent="chargeback_threat", draft_body="We will refund you immediately."),
        ).run(
            subject="Chargeback warning",
            body="Refund me or I will file a chargeback. ORD-1007.",
            sender_email="buyer07@example.com",
            source_message_id="E2E-L3-001",
        )
        assert (result.ai_level, result.risk_level, result.thread_status) == ("L3", "R2", "WAITING_HIGH_RISK_CHECK")

        partial = {"verify_facts": True, "review_customer_text": True}
        assert can_send(ai_level="L3", checklist={"verify_facts": True, "review_customer_text": False}) is False
        blocked_ui = _send_args(connection, result.thread_id, "Conservative reference reply.", "E2E-L3-PARTIAL", confirmed=True, checklist=partial)
        assert blocked_ui["ok"] is False
        assert blocked_ui["error_code"] == "CHECKLIST_REQUIRED"
        blocked_unconfirmed = _send_args(connection, result.thread_id, "Conservative reference reply.", "E2E-L3-NO-CONFIRM", confirmed=False, checklist={})
        assert blocked_unconfirmed["ok"] is False
        assert blocked_unconfirmed["error_code"] == "CONFIRMATION_REQUIRED"
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0

        risk = connection.execute("SELECT checklist_json FROM risk_decisions WHERE task_id = ?", (result.task_id,)).fetchone()
        required = {key: True for key in json.loads(risk["checklist_json"])}
        assert can_send(ai_level="L3", checklist=required) is True
        sent = _send_args(connection, result.thread_id, "We can review the available options with you.", "E2E-L3-SEND", confirmed=True, checklist=required)
        assert sent["ok"] is True
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 1
    finally:
        connection.close()


def test_repeated_send_is_idempotent_and_payload_change_conflicts(tmp_path: Path) -> None:
    connection = _fixture(tmp_path)
    try:
        result = InteractiveOrchestrator(connection, FakeCozeClient(intent="size_or_fit")).run(
            body="The jacket is too small. Order ORD-1002.",
            sender_email="buyer02@example.com",
            source_message_id="E2E-IDEMPOTENCY-001",
        )
        first = _send_args(connection, result.thread_id, "Please confirm the size you received.", "E2E-IDEMPOTENT-SEND", confirmed=True)
        replay = _send_args(connection, result.thread_id, "Please confirm the size you received.", "E2E-IDEMPOTENT-SEND", confirmed=True)
        conflict = _send_args(connection, result.thread_id, "A different reply.", "E2E-IDEMPOTENT-SEND", confirmed=True)
        assert first["ok"] is True and first["data"]["replayed"] is False
        assert replay["ok"] is True and replay["data"]["replayed"] is True
        assert conflict["ok"] is False and conflict["error_code"] == "IDEMPOTENCY_CONFLICT"
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 1
    finally:
        connection.close()


def test_tool_failure_escalates_without_fabricated_reply(tmp_path: Path) -> None:
    connection = _fixture(tmp_path)
    try:
        result = InteractiveOrchestrator(connection, FakeCozeClient(intent="shipping_status")).run(
            subject="Where is my order?",
            body="Please check tracking for ORD-1012.",
            sender_email="buyer12@example.com",
            source_message_id="E2E-TOOL-FAIL-001",
        )
        assert (result.ai_level, result.risk_level, result.thread_status) == ("L3", "R2", "WAITING_HIGH_RISK_CHECK")
        assert result.outbox_id is None
        error_trace = connection.execute(
            "SELECT error_code, status FROM tool_traces WHERE tool_name = 'get_shipping_status' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert tuple(error_trace) == ("TOOL_TIMEOUT", "ERROR")
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 0
    finally:
        connection.close()


def test_model_failure_is_failed_and_retry_does_not_duplicate_email(tmp_path: Path) -> None:
    connection = _fixture(tmp_path)
    try:
        failing = InteractiveOrchestrator(
            connection,
            FakeCozeClient(intent="shipping_status", error=CozeError("COZE_TIMEOUT", "timeout", retryable=True)),
        )
        first = failing.run(body="Where is order ORD-1001?", sender_email="buyer01@example.com", source_message_id="E2E-RETRY-001")
        assert first.thread_status == "FAILED"
        successful = InteractiveOrchestrator(connection, FakeCozeClient(intent="shipping_status", draft_body="It is in transit."))
        second = successful.run(body="Where is order ORD-1001?", sender_email="buyer01@example.com", source_message_id="E2E-RETRY-001")
        assert second.thread_status == "AI_REPLIED"
        assert connection.execute("SELECT COUNT(*) FROM emails WHERE source_message_id = 'E2E-RETRY-001'").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0] == 1
    finally:
        connection.close()
