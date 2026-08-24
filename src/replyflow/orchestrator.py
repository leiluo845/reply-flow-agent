from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .audit import record_state_transition
from .demo_router import DemoAnalysis, analyze_demo_email, basis_query_for, draft_demo_reply
from .mcp_tools import ReplyFlowTools
from .models import RiskDecision, TaskRun
from .repositories import RiskDecisionRepository, TaskRunRepository, ThreadRepository
from .risk_gateway import BasisRiskContext, RiskGatewayDecision, ToolError, evaluate_risk
from .skill_loader import SkillLoader
from .state_machine import InvalidStateTransition, StateMachine


PRESET_DEMO_CASES: dict[str, dict[str, str]] = {
    "logistics": {
        "subject": "Where is my order?",
        "body": "Hi, where is order ORD-1001? The tracking page has not changed since yesterday.",
        "sender_name": "Maya Stone",
        "sender_email": "buyer01@example.com",
    },
    "missing_order": {
        "subject": "Where is my package?",
        "body": "Where is my package? I cannot find the order number right now.",
        "sender_name": "Demo Buyer",
        "sender_email": "buyer-missing@example.com",
    },
    "refund_chargeback": {
        "subject": "Delivered but not received",
        "body": "Tracking says delivered but I received nothing. Refund me or I will file a chargeback. ORD-1007.",
        "sender_name": "Olivia Hale",
        "sender_email": "buyer07@example.com",
    },
}


class DemoRunResult(BaseModel):
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
    trace_ids: list[str] = Field(default_factory=list)
    state_history: list[str] = Field(default_factory=list)
    notice: str | None = None
    error_code: str | None = None
    replayed: bool = False


class DemoOrchestrator:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.tools = ReplyFlowTools(connection)
        self.skill_versions = {name: skill.version for name, skill in SkillLoader().load_all().items()}

    def run_preset_case(self, name: str, *, source_message_id: str | None = None) -> DemoRunResult:
        if name not in PRESET_DEMO_CASES:
            raise ValueError(f"Unknown Demo Mode preset: {name}")
        return self.run_demo_email(**PRESET_DEMO_CASES[name], source_message_id=source_message_id)

    def run_demo_email(
        self,
        *,
        body: str,
        subject: str | None = None,
        sender_name: str | None = None,
        sender_email: str | None = None,
        source_message_id: str | None = None,
        order_context_id: str | None = None,
    ) -> DemoRunResult:
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
            return DemoRunResult(email_id="", trace_ids=trace_ids, error_code=ingested["error_code"], notice=ingested["data"]["message"])

        ingestion = ingested["data"]
        if not ingestion["is_buyer_message"]:
            return DemoRunResult(
                email_id=ingestion["email_id"],
                thread_status="NOT_BUYER_MESSAGE",
                trace_ids=trace_ids,
                notice="This message stays in the raw inbox because it is not a buyer message.",
                replayed=ingestion["duplicate"],
            )
        thread_id = ingestion["thread_id"]
        thread = ThreadRepository(self.connection).get(thread_id)
        if ingestion["duplicate"] and thread and thread["status"] != "WAITING_ANALYSIS":
            return DemoRunResult(
                email_id=ingestion["email_id"],
                thread_id=thread_id,
                thread_status=thread["status"],
                risk_level=thread["risk_level"],
                ai_level=thread["ai_level"],
                trace_ids=trace_ids,
                notice="This source message was already processed; no duplicate reply was created.",
                replayed=True,
            )
        return self._run_thread(ingestion["email_id"], thread_id, trace_ids)

    def _run_thread(self, email_id: str, thread_id: str, trace_ids: list[str]) -> DemoRunResult:
        task_id = f"TASK-DEMO-{uuid4().hex[:12].upper()}"
        TaskRunRepository(self.connection).create(
            TaskRun(
                task_id=task_id,
                thread_id=thread_id,
                mode="demo",
                state="WAITING_ANALYSIS",
                skill_versions=self.skill_versions,
                workflow_version="demo-router-1.0",
                started_at=datetime.now(timezone.utc),
            )
        )
        machine = StateMachine()
        thread_repository = ThreadRepository(self.connection)
        thread_repository.update_status(thread_id, "AI_ANALYZING")

        def transition(target: str, note: str = "") -> None:
            before = machine.current_state
            machine.transition_to(target)
            TaskRunRepository(self.connection).update_state(task_id, target)
            record_state_transition(
                self.connection,
                task_id=task_id,
                before_state=before,
                after_state=target,
                note=note,
            )

        try:
            transition("ANALYZING", "Read original email and apply Demo Mode rules.")
            email_result = self.tools.get_email(email_id=email_id)
            trace_ids.append(email_result["trace_id"])
            if not email_result["ok"]:
                return self._fail(task_id, email_id, thread_id, machine, trace_ids, email_result["error_code"], email_result["data"]["message"])
            email = email_result["data"]["email"]
            analysis = analyze_demo_email(email["subject"], email["body"])
            if not analysis.supported:
                transition("WAITING_USER_INFO", "Demo Mode scope limitation.")
                decision = self._evaluate_and_record(
                    task_id,
                    email,
                    analysis,
                    verified_facts={},
                    basis=BasisRiskContext(status="HIT", results_count=1),
                    tool_errors=[],
                    draft=None,
                )
                transition("RISK_CHECKING", "Apply local risk gateway to the scope-limited message.")
                transition("WAITING_USER_CONFIRMATION", "Store operator can switch mode or handle manually.")
                thread_repository.update_status(
                    thread_id,
                    "WAITING_USER_CONFIRMATION",
                    ai_level=decision.ai_level,
                    risk_level=decision.risk_level,
                )
                TaskRunRepository(self.connection).complete(task_id, state="WAITING_USER_CONFIRMATION")
                return DemoRunResult(
                    task_id=task_id,
                    email_id=email_id,
                    thread_id=thread_id,
                    thread_status="WAITING_USER_CONFIRMATION",
                    intent=analysis.intent,
                    risk_level=decision.risk_level,
                    ai_level=decision.ai_level,
                    trace_ids=trace_ids,
                    state_history=machine.history,
                    notice=analysis.limitation_message,
                )

            tool_errors: list[ToolError] = []
            verified_facts: dict[str, Any] = {}
            if analysis.order_id:
                transition("COLLECTING_FACTS", "Query an explicit order ID only.")
                order_result = self.tools.find_order(order_id=analysis.order_id)
                trace_ids.append(order_result["trace_id"])
                if order_result["ok"]:
                    order = order_result["data"]["orders"][0]
                    verified_facts.update({"order_found": True, "order": order, "fulfillment_status": order["fulfillment_status"]})
                    if email["sender_email"].lower() != order["customer_email"].lower():
                        verified_facts["identity_conflict"] = True
                    if analysis.intent in {"shipment_inquiry", "high_risk_after_sales"}:
                        shipping_result = self.tools.get_shipping_status(order_id=analysis.order_id)
                        trace_ids.append(shipping_result["trace_id"])
                        if shipping_result["ok"]:
                            verified_facts.update(
                                {
                                    "shipping_found": True,
                                    "latest_shipping": shipping_result["data"]["latest"],
                                    "shipping_events": shipping_result["data"]["events"],
                                }
                            )
                        else:
                            tool_errors.append(
                                ToolError(
                                    tool_name="get_shipping_status",
                                    error_code=shipping_result["error_code"],
                                    message=shipping_result["data"]["message"],
                                )
                            )
                elif order_result["error_code"] == "ORDER_NOT_FOUND":
                    verified_facts["order_not_found"] = True
                else:
                    tool_errors.append(
                        ToolError(
                            tool_name="find_order",
                            error_code=order_result["error_code"],
                            message=order_result["data"]["message"],
                        )
                    )
            else:
                transition("WAITING_USER_INFO", "No explicit order ID; do not use demo order context as a fact.")

            transition("RETRIEVING_REPLY_BASIS", "Retrieve read-only reply basis and tone guidance.")
            basis_result = self.tools.search_reply_basis(query=basis_query_for(analysis))
            trace_ids.append(basis_result["trace_id"])
            if basis_result["ok"]:
                basis = BasisRiskContext(
                    status=basis_result["data"]["status"],
                    results_count=len(basis_result["data"]["results"]),
                )
            elif basis_result["error_code"] == "BASIS_NOT_FOUND":
                basis = BasisRiskContext(status="NO_HIT", results_count=0)
            else:
                basis = BasisRiskContext(status="NO_HIT", results_count=0)
                tool_errors.append(
                    ToolError(
                        tool_name="search_reply_basis",
                        error_code=basis_result["error_code"],
                        message=basis_result["data"]["message"],
                    )
                )
            tone_result = self.tools.get_reply_tone()
            trace_ids.append(tone_result["trace_id"])
            if not tone_result["ok"]:
                tool_errors.append(
                    ToolError(
                        tool_name="get_reply_tone",
                        error_code=tone_result["error_code"],
                        message=tone_result["data"]["message"],
                    )
                )

            transition("DRAFTING", "Create a bounded English draft from verified facts and read-only basis.")
            draft = draft_demo_reply(
                analysis=analysis,
                email=email,
                facts=verified_facts,
                tool_errors=[error.model_dump() for error in tool_errors],
            )
            transition("RISK_CHECKING", "Run local gateway after analysis and draft.")
            decision = self._evaluate_and_record(task_id, email, analysis, verified_facts, basis, tool_errors, draft)
            if decision.ai_level == "BLOCKED":
                return self._fail(task_id, email_id, thread_id, machine, trace_ids, "R3_BLOCKED", "Local architecture boundary blocked this action.")
            if not draft:
                transition("WAITING_USER_CONFIRMATION", "No generic draft is produced outside Demo Mode scope.")
                thread_repository.update_status(
                    thread_id,
                    "WAITING_USER_CONFIRMATION",
                    ai_level=decision.ai_level,
                    risk_level=decision.risk_level,
                )
                TaskRunRepository(self.connection).complete(task_id, state="WAITING_USER_CONFIRMATION")
                return DemoRunResult(
                    task_id=task_id,
                    email_id=email_id,
                    thread_id=thread_id,
                    thread_status="WAITING_USER_CONFIRMATION",
                    intent=analysis.intent,
                    risk_level=decision.risk_level,
                    ai_level=decision.ai_level,
                    trace_ids=trace_ids,
                    state_history=machine.history,
                    notice=analysis.limitation_message,
                )

            draft_result = self.tools.save_reply_draft(
                thread_id=thread_id,
                agent_content=draft,
                ai_level=decision.ai_level,
                risk_level=decision.risk_level,
                confirmed=True,
                operation_id=f"demo-draft-{thread_id}",
            )
            trace_ids.append(draft_result["trace_id"])
            if not draft_result["ok"]:
                return self._fail(task_id, email_id, thread_id, machine, trace_ids, draft_result["error_code"], draft_result["data"]["message"])
            draft_id = draft_result["data"]["draft"]["draft_id"]
            if decision.ai_level == "L1":
                transition("AUTO_REPLYING", "Risk gateway allowed the low-risk logistics allowlist.")
                sent_result = self.tools.send_simulated_reply(
                    thread_id=thread_id,
                    recipient=email["sender_email"],
                    subject=f"Re: {email['subject']}",
                    body=draft,
                    confirmed=True,
                    operation_id=f"demo-send-{thread_id}",
                )
                trace_ids.append(sent_result["trace_id"])
                if not sent_result["ok"]:
                    return self._fail(task_id, email_id, thread_id, machine, trace_ids, sent_result["error_code"], sent_result["data"]["message"])
                transition("SIMULATED_SENT", "Write only to local simulated outbox.")
                transition("COMPLETED", "Low-risk Demo Mode flow completed.")
                thread_repository.update_status(thread_id, "AI_REPLIED", ai_level="L1", risk_level=decision.risk_level)
                TaskRunRepository(self.connection).complete(task_id, state="COMPLETED")
                return DemoRunResult(
                    task_id=task_id,
                    email_id=email_id,
                    thread_id=thread_id,
                    thread_status="AI_REPLIED",
                    intent=analysis.intent,
                    risk_level=decision.risk_level,
                    ai_level=decision.ai_level,
                    draft_id=draft_id,
                    outbox_id=sent_result["data"]["outbox"]["outbox_id"],
                    trace_ids=trace_ids,
                    state_history=machine.history,
                    replayed=bool(draft_result["data"]["replayed"] or sent_result["data"]["replayed"]),
                )

            transition("DRAFT_SAVED", "Save the AI draft locally for store-operator review.")
            if decision.ai_level == "L2":
                transition("WAITING_USER_CONFIRMATION", "Store operator confirmation is required.")
                final_thread_status = "WAITING_USER_CONFIRMATION"
            else:
                transition("WAITING_HIGH_RISK_CHECK", "High-risk checklist and second confirmation are required.")
                final_thread_status = "WAITING_HIGH_RISK_CHECK"
            thread_repository.update_status(
                thread_id,
                final_thread_status,
                ai_level=decision.ai_level,
                risk_level=decision.risk_level,
            )
            TaskRunRepository(self.connection).complete(task_id, state=final_thread_status)
            return DemoRunResult(
                task_id=task_id,
                email_id=email_id,
                thread_id=thread_id,
                thread_status=final_thread_status,
                intent=analysis.intent,
                risk_level=decision.risk_level,
                ai_level=decision.ai_level,
                draft_id=draft_id,
                trace_ids=trace_ids,
                state_history=machine.history,
            )
        except (InvalidStateTransition, KeyError, ValueError) as exc:
            return self._fail(task_id, email_id, thread_id, machine, trace_ids, "DEMO_ORCHESTRATION_ERROR", str(exc))

    def _evaluate_and_record(
        self,
        task_id: str,
        email: dict[str, Any],
        analysis: DemoAnalysis,
        verified_facts: dict[str, Any],
        basis: BasisRiskContext,
        tool_errors: list[ToolError],
        draft: str | None,
    ) -> RiskGatewayDecision:
        decision = evaluate_risk(
            {
                "email": {
                    "subject": email["subject"],
                    "body": email["body"],
                    "sender_email": email["sender_email"],
                    "attachments": email.get("attachments", []),
                },
                "analysis": {
                    "intent": analysis.intent,
                    "order_id": analysis.order_id,
                    "missing_fields": analysis.missing_fields,
                    "confidence": analysis.confidence,
                },
                "verified_facts": verified_facts,
                "basis": basis.model_dump(),
                "tool_errors": [error.model_dump() for error in tool_errors],
                "draft": draft,
            }
        )
        RiskDecisionRepository(self.connection).create(
            RiskDecision(
                decision_id=f"RISK-{uuid4().hex[:12].upper()}",
                task_id=task_id,
                risk_level=decision.risk_level,
                ai_level=decision.ai_level,
                matched_rules=decision.matched_rules,
                checklist={item.item_id: item.label for item in decision.checklist},
                created_at=datetime.now(timezone.utc),
            )
        )
        return decision

    def _fail(
        self,
        task_id: str,
        email_id: str,
        thread_id: str,
        machine: StateMachine,
        trace_ids: list[str],
        error_code: str | None,
        notice: str,
    ) -> DemoRunResult:
        if machine.current_state != "FAILED":
            try:
                before = machine.current_state
                machine.fail()
                TaskRunRepository(self.connection).update_state(task_id, "FAILED")
                record_state_transition(
                    self.connection,
                    task_id=task_id,
                    before_state=before,
                    after_state="FAILED",
                    note=error_code or "Unknown error",
                )
            except InvalidStateTransition:
                pass
        ThreadRepository(self.connection).update_status(thread_id, "FAILED")
        TaskRunRepository(self.connection).complete(task_id, state="FAILED", error_code=error_code)
        return DemoRunResult(
            task_id=task_id,
            email_id=email_id,
            thread_id=thread_id,
            thread_status="FAILED",
            trace_ids=trace_ids,
            state_history=machine.history,
            error_code=error_code,
            notice=notice,
        )
