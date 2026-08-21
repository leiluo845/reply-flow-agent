from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReplyFlowModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class EmailRecord(ReplyFlowModel):
    email_id: str
    source_message_id: str
    sender_name: str
    sender_email: str
    subject: str
    body: str
    received_at: datetime
    source: str
    order_context_id: str | None = None
    attachments: list[str] = Field(default_factory=list)
    status: str = "RECEIVED"


class AggregateThread(ReplyFlowModel):
    thread_id: str
    email_id: str
    scenario: str | None = None
    ai_level: str | None = None
    risk_level: str | None = None
    status: str = "WAITING_ANALYSIS"
    created_at: datetime
    updated_at: datetime


class OrderRecord(ReplyFlowModel):
    order_id: str
    customer_email: str
    customer_name: str
    product_name: str
    sku: str
    amount: str
    currency: str
    order_status: str
    payment_status: str
    fulfillment_status: str
    ordered_at: datetime
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    return_deadline: str


class ShippingEvent(ReplyFlowModel):
    event_id: str
    order_id: str
    event_time: datetime
    location: str
    status: str
    description: str


class ReplyBasisRecord(ReplyFlowModel):
    basis_id: str
    title: str
    basis_type: str
    section_id: str
    content: str
    version: str
    active: bool = True


class ReplyDraft(ReplyFlowModel):
    draft_id: str
    thread_id: str
    agent_content: str
    edited_content: str | None = None
    ai_level: str | None = None
    risk_level: str | None = None
    created_at: datetime
    updated_at: datetime


class OutboxMessage(ReplyFlowModel):
    outbox_id: str
    thread_id: str
    recipient: str
    subject: str
    body: str
    simulated_sent_at: datetime
    operation_id: str


class TaskRun(ReplyFlowModel):
    task_id: str
    thread_id: str
    mode: str
    state: str
    skill_versions: dict[str, str] = Field(default_factory=dict)
    workflow_version: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    error_code: str | None = None


class ToolTrace(ReplyFlowModel):
    trace_id: str
    task_id: str
    tool_name: str
    input_summary: str
    output_summary: str
    status: str
    duration_ms: int | None = None
    error_code: str | None = None
    created_at: datetime


class RiskDecision(ReplyFlowModel):
    decision_id: str
    task_id: str
    risk_level: str
    ai_level: str
    matched_rules: list[str] = Field(default_factory=list)
    checklist: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class Confirmation(ReplyFlowModel):
    confirmation_id: str
    task_id: str
    action: str
    confirmed_by: str
    confirmed_at: datetime
    checklist: dict[str, Any] = Field(default_factory=dict)


class AuditLog(ReplyFlowModel):
    audit_id: str
    task_id: str
    action: str
    before_summary: str
    after_summary: str
    created_at: datetime


class IdempotencyKey(ReplyFlowModel):
    operation_id: str
    action: str
    payload_hash: str
    result_ref: str | None = None
    created_at: datetime


class EvaluationResult(ReplyFlowModel):
    run_id: str
    case_id: str
    expected: dict[str, Any]
    actual: dict[str, Any]
    passed: bool
    failure_types: list[str] = Field(default_factory=list)
    trace_ref: str | None = None
