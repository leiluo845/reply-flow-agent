from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .audit import record_state_transition
from .coze_client import AnalyzeOutput, CozeError, DraftOutput
from .mcp_tools import ReplyFlowTools
from .models import RiskDecision, TaskRun
from .repositories import RiskDecisionRepository, TaskRunRepository, ThreadRepository
from .risk_gateway import BasisRiskContext, RiskGatewayDecision, ToolError, evaluate_risk
from .state_machine import StateMachine


class InteractiveClient(Protocol):
    def analyze(self, *, subject: str, body: str, order_context_id: str | None = None) -> AnalyzeOutput: ...

    def draft(
        self,
        *,
        email_json: dict[str, Any],
        verified_facts_json: dict[str, Any],
        reply_basis_json: dict[str, Any],
        risk_context_json: dict[str, Any],
    ) -> DraftOutput: ...


class InteractiveRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str | None = None
    email_id: str
    thread_id: str | None = None
    thread_status: str | None = None
    intent: str | None = None
    risk_level: str | None = None
    ai_level: str | None = None
    draft_id: str | None = None
    outbox_id: str | None = None
    coze_request_ids: list[str] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    state_history: list[str] = Field(default_factory=list)
    error_code: str | None = None
    notice: str | None = None
    downgraded_to_demo: bool = False


def _basis_query(intent: str) -> str:
    return {
        "shipping_status": "delivery status",
        "delivered_not_received": "delivered not received",
        "size_or_fit": "size exchange",
        "return_or_exchange": "return exchange",
        "damaged_item": "damaged item photo",
        "refund_request": "refund request",
        "chargeback_threat": "chargeback complaint",
    }.get(intent, "customer service next step")


class InteractiveOrchestrator:
    def __init__(self, connection: sqlite3.Connection, client: InteractiveClient):
        self.connection = connection
        self.client = client
        self.tools = ReplyFlowTools(connection)

    def run(
        self,
        *,
        body: str,
        subject: str | None = None,
        sender_name: str | None = None,
        sender_email: str | None = None,
        source_message_id: str | None = None,
        order_context_id: str | None = None,
    ) -> InteractiveRunResult:
        trace_ids: list[str] = []
        ingested = self.tools.ingest_simulated_email(
            body=body,
            subject=subject,
            sender_name=sender_name,
            sender_email=sender_email,
            source_message_id=source_message_id,
            order_context_id=order_context_id,
        )
        trace_ids.append(ingested["trace_id"])
        if not ingested["ok"]:
            return InteractiveRunResult(email_id="", trace_ids=trace_ids, error_code=ingested["error_code"], notice=ingested["data"]["message"])
        data = ingested["data"]
        if not data["is_buyer_message"]:
            return InteractiveRunResult(email_id=data["email_id"], thread_status="NOT_BUYER_MESSAGE", trace_ids=trace_ids)
        thread_id = data["thread_id"]
        thread = ThreadRepository(self.connection).get(thread_id)
        # A failed Coze run is retryable. Other terminal states remain
        # idempotent replays and must not create a second AI task.
        if data["duplicate"] and thread and thread["status"] not in {"WAITING_ANALYSIS", "FAILED"}:
            return InteractiveRunResult(
                email_id=data["email_id"],
                thread_id=thread_id,
                thread_status=thread["status"],
                risk_level=thread["risk_level"],
                ai_level=thread["ai_level"],
                trace_ids=trace_ids,
                notice="This source message was already processed.",
            )

        task_id = f"TASK-INTERACTIVE-{uuid4().hex[:12].upper()}"
        TaskRunRepository(self.connection).create(
            TaskRun(task_id=task_id, thread_id=thread_id, mode="interactive", state="WAITING_ANALYSIS", workflow_version="coze", started_at=datetime.now(timezone.utc))
        )
        machine = StateMachine()
        ThreadRepository(self.connection).update_status(thread_id, "AI_ANALYZING")

        def transition(target: str, note: str = "") -> None:
            before = machine.current_state
            machine.transition_to(target)
            TaskRunRepository(self.connection).update_state(task_id, target)
            record_state_transition(self.connection, task_id=task_id, before_state=before, after_state=target, note=note)

        try:
            transition("ANALYZING", "Coze Analyze output is validated locally.")
            email_result = self.tools.get_email(email_id=data["email_id"])
            trace_ids.append(email_result["trace_id"])
            if not email_result["ok"]:
                return self._fail(task_id, data["email_id"], thread_id, machine, trace_ids, email_result["error_code"], email_result["data"]["message"])
            email = email_result["data"]["email"]
            analysis = self.client.analyze(subject=email["subject"], body=email["body"], order_context_id=email["order_context_id"])
            if not analysis.is_buyer_message:
                ThreadRepository(self.connection).update_status(thread_id, "NOT_BUYER_MESSAGE")
                TaskRunRepository(self.connection).complete(task_id, state="COMPLETED")
                return InteractiveRunResult(
                    task_id=task_id,
                    email_id=data["email_id"],
                    thread_id=thread_id,
                    thread_status="NOT_BUYER_MESSAGE",
                    intent=analysis.intent,
                    state_history=machine.history,
                )

            verified_facts: dict[str, Any] = {}
            tool_errors: list[ToolError] = []
            if analysis.order_id:
                transition("COLLECTING_FACTS", "Only an explicit order ID is sent to local Tools.")
                order_result = self.tools.find_order(order_id=analysis.order_id)
                trace_ids.append(order_result["trace_id"])
                if order_result["ok"]:
                    order = order_result["data"]["orders"][0]
                    verified_facts.update({"order_found": True, "order": order, "fulfillment_status": order["fulfillment_status"]})
                    if email["sender_email"].lower() != order["customer_email"].lower():
                        verified_facts["identity_conflict"] = True
                    if analysis.intent in {"shipping_status", "delivered_not_received"}:
                        shipping_result = self.tools.get_shipping_status(order_id=analysis.order_id)
                        trace_ids.append(shipping_result["trace_id"])
                        if shipping_result["ok"]:
                            verified_facts.update({"shipping_found": True, "latest_shipping": shipping_result["data"]["latest"], "shipping_events": shipping_result["data"]["events"]})
                        else:
                            tool_errors.append(ToolError(tool_name="get_shipping_status", error_code=shipping_result["error_code"], message=shipping_result["data"]["message"]))
                elif order_result["error_code"] == "ORDER_NOT_FOUND":
                    verified_facts["order_not_found"] = True
                else:
                    tool_errors.append(ToolError(tool_name="find_order", error_code=order_result["error_code"], message=order_result["data"]["message"]))
            else:
                transition("WAITING_USER_INFO", "No explicit order ID; no order is guessed.")

            transition("RETRIEVING_REPLY_BASIS", "Reply basis remains local and read-only.")
            basis_result = self.tools.search_reply_basis(query=_basis_query(analysis.intent))
            trace_ids.append(basis_result["trace_id"])
            if basis_result["ok"]:
                basis_payload = basis_result["data"]
                basis_context = BasisRiskContext(status=basis_payload["status"], results_count=len(basis_payload["results"]))
            else:
                basis_payload = {"status": "NO_HIT", "results": []}
                basis_context = BasisRiskContext(status="NO_HIT", results_count=0)
                if basis_result["error_code"] != "BASIS_NOT_FOUND":
                    tool_errors.append(ToolError(tool_name="search_reply_basis", error_code=basis_result["error_code"], message=basis_result["data"]["message"]))
            tone_result = self.tools.get_reply_tone()
            trace_ids.append(tone_result["trace_id"])
            if tone_result["ok"]:
                basis_payload["tone"] = tone_result["data"]["tone"]

            preliminary = evaluate_risk(
                {
                    "email": {"subject": email["subject"], "body": email["body"], "sender_email": email["sender_email"], "attachments": email.get("attachments", [])},
                    "analysis": self._risk_analysis(analysis),
                    "verified_facts": verified_facts,
                    "basis": basis_context.model_dump(),
                    "tool_errors": [error.model_dump() for error in tool_errors],
                }
            )
            transition("DRAFTING", "Coze receives only local verified facts, basis and risk context.")
            draft = self.client.draft(
                email_json={"email_id": email["email_id"], "subject": email["subject"], "body": email["body"], "sender_email": email["sender_email"]},
                verified_facts_json=verified_facts,
                reply_basis_json=basis_payload,
                risk_context_json={"risk_level": preliminary.risk_level, "ai_level": preliminary.ai_level, "matched_rules": preliminary.matched_rules},
            )
            transition("RISK_CHECKING", "Local gateway scans the Coze draft again.")
            final_decision = evaluate_risk(
                {
                    "email": {"subject": email["subject"], "body": email["body"], "sender_email": email["sender_email"], "attachments": email.get("attachments", [])},
                    "analysis": self._risk_analysis(analysis),
                    "verified_facts": verified_facts,
                    "basis": basis_context.model_dump(),
                    "tool_errors": [error.model_dump() for error in tool_errors],
                    "draft": draft.draft_body,
                }
            )
            RiskDecisionRepository(self.connection).create(
                RiskDecision(decision_id=f"RISK-{uuid4().hex[:12].upper()}", task_id=task_id, risk_level=final_decision.risk_level, ai_level=final_decision.ai_level, matched_rules=final_decision.matched_rules, checklist={item.item_id: item.label for item in final_decision.checklist}, created_at=datetime.now(timezone.utc))
            )
            if final_decision.ai_level == "BLOCKED":
                return self._fail(task_id, data["email_id"], thread_id, machine, trace_ids, "R3_BLOCKED", "Local architecture boundary blocked this action.")
            draft_result = self.tools.save_reply_draft(thread_id=thread_id, agent_content=draft.draft_body, ai_level=final_decision.ai_level, risk_level=final_decision.risk_level, confirmed=True, operation_id=f"interactive-draft-{thread_id}")
            trace_ids.append(draft_result["trace_id"])
            if not draft_result["ok"]:
                return self._fail(task_id, data["email_id"], thread_id, machine, trace_ids, draft_result["error_code"], draft_result["data"]["message"])
            draft_id = draft_result["data"]["draft"]["draft_id"]
            if final_decision.ai_level == "L1":
                transition("AUTO_REPLYING", "Local allowlist permits simulated auto-reply.")
                sent = self.tools.send_simulated_reply(thread_id=thread_id, recipient=email["sender_email"], subject=draft.draft_subject, body=draft.draft_body, confirmed=True, operation_id=f"interactive-send-{thread_id}")
                trace_ids.append(sent["trace_id"])
                if not sent["ok"]:
                    return self._fail(task_id, data["email_id"], thread_id, machine, trace_ids, sent["error_code"], sent["data"]["message"])
                transition("SIMULATED_SENT", "Only local outbox is written.")
                transition("COMPLETED", "Interactive low-risk flow completed.")
                ThreadRepository(self.connection).update_status(thread_id, "AI_REPLIED", ai_level="L1", risk_level=final_decision.risk_level)
                TaskRunRepository(self.connection).complete(task_id, state="COMPLETED")
                return InteractiveRunResult(task_id=task_id, email_id=data["email_id"], thread_id=thread_id, thread_status="AI_REPLIED", intent=analysis.intent, risk_level=final_decision.risk_level, ai_level=final_decision.ai_level, draft_id=draft_id, outbox_id=sent["data"]["outbox"]["outbox_id"], coze_request_ids=[], trace_ids=trace_ids, state_history=machine.history)
            transition("DRAFT_SAVED", "Store operator review is required after Coze drafting.")
            final_status = "WAITING_USER_CONFIRMATION" if final_decision.ai_level == "L2" else "WAITING_HIGH_RISK_CHECK"
            transition(final_status, "Local confirmation boundary remains outside Coze.")
            ThreadRepository(self.connection).update_status(thread_id, final_status, ai_level=final_decision.ai_level, risk_level=final_decision.risk_level)
            TaskRunRepository(self.connection).complete(task_id, state=final_status)
            return InteractiveRunResult(task_id=task_id, email_id=data["email_id"], thread_id=thread_id, thread_status=final_status, intent=analysis.intent, risk_level=final_decision.risk_level, ai_level=final_decision.ai_level, draft_id=draft_id, trace_ids=trace_ids, state_history=machine.history)
        except CozeError as exc:
            return self._fail(task_id, data["email_id"], thread_id, machine, trace_ids, exc.code, exc.message)
        except Exception as exc:
            return self._fail(task_id, data["email_id"], thread_id, machine, trace_ids, "INTERACTIVE_ORCHESTRATION_ERROR", str(exc))

    def _fail(self, task_id: str, email_id: str, thread_id: str, machine: StateMachine, trace_ids: list[str], error_code: str, notice: str) -> InteractiveRunResult:
        if machine.current_state != "FAILED":
            before = machine.current_state
            machine.fail()
            TaskRunRepository(self.connection).update_state(task_id, "FAILED")
            record_state_transition(self.connection, task_id=task_id, before_state=before, after_state="FAILED", note=error_code)
        ThreadRepository(self.connection).update_status(thread_id, "FAILED")
        TaskRunRepository(self.connection).complete(task_id, state="FAILED", error_code=error_code)
        return InteractiveRunResult(task_id=task_id, email_id=email_id, thread_id=thread_id, thread_status="FAILED", trace_ids=trace_ids, state_history=machine.history, error_code=error_code, notice=notice)

    @staticmethod
    def _risk_analysis(analysis: AnalyzeOutput) -> dict[str, Any]:
        return {
            "intent": analysis.intent,
            "order_id": analysis.order_id,
            "missing_fields": analysis.missing_fields,
            "confidence": analysis.confidence,
        }
