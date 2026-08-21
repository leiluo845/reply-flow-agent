from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .db import transaction
from .ingestion import IngestionError, ingest_simulated_email
from .models import AuditLog, OutboxMessage, ReplyDraft, TaskRun, ToolTrace
from .repositories import (
    AuditLogRepository,
    EmailRepository,
    IdempotencyRepository,
    OrderRepository,
    OutboxRepository,
    ReplyBasisRepository,
    ReplyDraftRepository,
    TaskRunRepository,
    ThreadRepository,
    ToolTraceRepository,
)


TOOL_NAMES = (
    "ingest_simulated_email",
    "get_email",
    "find_order",
    "get_shipping_status",
    "search_reply_basis",
    "get_reply_tone",
    "save_reply_draft",
    "send_simulated_reply",
)


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngestEmailInput(ToolInput):
    body: str
    subject: str | None = None
    sender_name: str | None = None
    sender_email: str | None = None
    source: str = "demo_console"
    source_message_id: str | None = None
    order_context_id: str | None = None


class EmailLookupInput(ToolInput):
    email_id: str = Field(min_length=1)


class OrderLookupInput(ToolInput):
    order_id: str | None = None
    customer_email: str | None = None

    @model_validator(mode="after")
    def require_lookup_key(self) -> "OrderLookupInput":
        if not (self.order_id and self.order_id.strip()) and not (self.customer_email and self.customer_email.strip()):
            raise ValueError("order_id or customer_email is required")
        return self


class ShippingLookupInput(ToolInput):
    order_id: str = Field(min_length=1)


class BasisSearchInput(ToolInput):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class DraftInput(ToolInput):
    thread_id: str = Field(min_length=1)
    agent_content: str = Field(min_length=1)
    edited_content: str | None = None
    ai_level: str | None = None
    risk_level: str | None = None
    confirmed: bool = False
    operation_id: str = Field(min_length=1)

    @field_validator("operation_id")
    @classmethod
    def operation_id_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("operation_id cannot be blank")
        return value.strip()


class SendInput(ToolInput):
    thread_id: str = Field(min_length=1)
    recipient: str = Field(min_length=1)
    subject: str = "ReplyFlow simulated reply"
    body: str = Field(min_length=1)
    confirmed: bool = False
    operation_id: str = Field(min_length=1)

    @field_validator("operation_id")
    @classmethod
    def operation_id_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("operation_id cannot be blank")
        return value.strip()


class ToolResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    tool_name: str
    trace_id: str
    error_code: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class ToolFailure(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _summary(value: object, *, limit: int = 500) -> str:
    """Keep trace records useful without retaining full buyer or draft text."""
    content_fields = {"body", "agent_content", "edited_content", "content", "output_summary"}
    identity_fields = {"sender_email", "customer_email", "recipient"}

    def scrub(item: object, field_name: str | None = None) -> object:
        if field_name in content_fields and isinstance(item, str):
            return {"redacted": True, "characters": len(item)}
        if field_name in identity_fields and isinstance(item, str):
            local, separator, domain = item.partition("@")
            return f"{local[:2]}***{separator}{domain}" if separator else "***"
        if isinstance(item, dict):
            return {str(key): scrub(value, str(key)) for key, value in item.items()}
        if isinstance(item, list):
            return [scrub(entry) for entry in item]
        return item

    text = json.dumps(scrub(value), ensure_ascii=False, default=str, separators=(",", ":"))
    return text[:limit]


class _TraceContext:
    def __init__(self, connection: sqlite3.Connection, tool_name: str, payload: object, thread_id: str | None = None):
        self.connection = connection
        self.tool_name = tool_name
        self.task_id = f"TASK-{uuid4().hex[:12].upper()}"
        self.trace_id = f"TRACE-{uuid4().hex[:12].upper()}"
        TaskRunRepository(connection).create(
            TaskRun(
                task_id=self.task_id,
                thread_id=thread_id,
                mode="tool",
                state="RUNNING",
                started_at=_now(),
            )
        )
        self.payload = payload

    def finish(self, *, status: str, output: object, error_code: str | None = None) -> None:
        ToolTraceRepository(self.connection).create(
            ToolTrace(
                trace_id=self.trace_id,
                task_id=self.task_id,
                tool_name=self.tool_name,
                input_summary=_summary(self.payload),
                output_summary=_summary(output),
                status=status,
                duration_ms=None,
                error_code=error_code,
                created_at=_now(),
            )
        )
        TaskRunRepository(self.connection).complete(
            self.task_id,
            state="COMPLETED" if status == "SUCCESS" else "FAILED",
            error_code=error_code,
        )


def _begin(connection: sqlite3.Connection, tool_name: str, payload: object, thread_id: str | None = None) -> _TraceContext:
    return _TraceContext(connection, tool_name, payload, thread_id=thread_id)


def _ok(context: _TraceContext, data: dict[str, Any]) -> dict[str, Any]:
    context.finish(status="SUCCESS", output=data)
    return ToolResponse(ok=True, tool_name=context.tool_name, trace_id=context.trace_id, data=data).model_dump()


def _error(context: _TraceContext, code: str, message: str) -> dict[str, Any]:
    payload = {"message": message}
    context.finish(status="ERROR", output=payload, error_code=code)
    return ToolResponse(
        ok=False,
        tool_name=context.tool_name,
        trace_id=context.trace_id,
        error_code=code,
        data=payload,
    ).model_dump()


def _run(
    connection: sqlite3.Connection,
    tool_name: str,
    payload: object,
    action: Callable[[_TraceContext], dict[str, Any]],
    *,
    thread_id: str | None = None,
) -> dict[str, Any]:
    context = _begin(connection, tool_name, payload, thread_id=thread_id)
    try:
        return _ok(context, action(context))
    except ToolFailure as exc:
        return _error(context, exc.code, exc.message)
    except Exception as exc:
        return _error(context, "TOOL_ERROR", str(exc))


class ReplyFlowTools:
    """Direct-call implementation shared by tests, Demo Mode and the MCP adapter."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def _validate(self, model: type[ToolInput], tool_name: str, kwargs: dict[str, Any]) -> ToolInput | dict[str, Any]:
        try:
            return model.model_validate(kwargs)
        except ValidationError:
            context = _begin(self.connection, tool_name, {"input_fields": sorted(kwargs)})
            return _error(context, "INVALID_INPUT", "Tool input did not match the required schema.")

    def ingest_simulated_email(self, **kwargs: Any) -> dict[str, Any]:
        request = self._validate(IngestEmailInput, "ingest_simulated_email", kwargs)
        if isinstance(request, dict):
            return request

        def action(_: _TraceContext) -> dict[str, Any]:
            try:
                result = ingest_simulated_email(self.connection, **request.model_dump())
            except IngestionError as exc:
                raise ToolFailure(exc.code, exc.message) from exc
            return result.model_dump()

        return _run(self.connection, "ingest_simulated_email", request.model_dump(), action)

    def get_email(self, **kwargs: Any) -> dict[str, Any]:
        request = self._validate(EmailLookupInput, "get_email", kwargs)
        if isinstance(request, dict):
            return request

        def action(_: _TraceContext) -> dict[str, Any]:
            row = EmailRepository(self.connection).get(request.email_id)
            if not row:
                raise ToolFailure("EMAIL_NOT_FOUND", f"Email not found: {request.email_id}")
            row["attachments"] = json.loads(row.pop("attachments_json", "[]"))
            return {"email": row}

        return _run(self.connection, "get_email", request.model_dump(), action)

    def find_order(self, **kwargs: Any) -> dict[str, Any]:
        request = self._validate(OrderLookupInput, "find_order", kwargs)
        if isinstance(request, dict):
            return request

        def action(_: _TraceContext) -> dict[str, Any]:
            repository = OrderRepository(self.connection)
            if request.order_id:
                row = repository.get(request.order_id.strip())
                orders = [row] if row else []
            else:
                orders = repository.find_by_customer_email(request.customer_email.strip())  # type: ignore[union-attr]
            if not orders:
                raise ToolFailure("ORDER_NOT_FOUND", "No matching simulated order was found.")
            return {"orders": orders}

        return _run(self.connection, "find_order", request.model_dump(), action)

    def get_shipping_status(self, **kwargs: Any) -> dict[str, Any]:
        request = self._validate(ShippingLookupInput, "get_shipping_status", kwargs)
        if isinstance(request, dict):
            return request

        def action(_: _TraceContext) -> dict[str, Any]:
            repository = OrderRepository(self.connection)
            order = repository.get(request.order_id)
            if not order:
                raise ToolFailure("ORDER_NOT_FOUND", f"Order not found: {request.order_id}")
            events = repository.list_shipping_events(request.order_id)
            if not events:
                raise ToolFailure("SHIPPING_NOT_FOUND", f"No shipping events for {request.order_id}")
            return {"order_id": request.order_id, "latest": events[-1], "events": events}

        return _run(self.connection, "get_shipping_status", request.model_dump(), action)

    def search_reply_basis(self, **kwargs: Any) -> dict[str, Any]:
        request = self._validate(BasisSearchInput, "search_reply_basis", kwargs)
        if isinstance(request, dict):
            return request

        def action(_: _TraceContext) -> dict[str, Any]:
            rows = ReplyBasisRepository(self.connection).search(request.query, limit=request.limit)
            if not rows:
                raise ToolFailure("BASIS_NOT_FOUND", "No matching internal reply basis was found.")
            return {"results": rows, "query": request.query}

        return _run(self.connection, "search_reply_basis", request.model_dump(), action)

    def get_reply_tone(self, **kwargs: Any) -> dict[str, Any]:
        request = self._validate(ToolInput, "get_reply_tone", kwargs)
        if isinstance(request, dict):
            return request

        def action(_: _TraceContext) -> dict[str, Any]:
            rows = ReplyBasisRepository(self.connection).get_tone()
            if not rows:
                raise ToolFailure("BASIS_NOT_FOUND", "Reply tone basis is unavailable.")
            return {"tone": rows}

        return _run(self.connection, "get_reply_tone", request.model_dump(), action)

    def save_reply_draft(self, **kwargs: Any) -> dict[str, Any]:
        request = self._validate(DraftInput, "save_reply_draft", kwargs)
        if isinstance(request, dict):
            return request
        known_thread = request.thread_id if ThreadRepository(self.connection).get(request.thread_id) else None
        context = _begin(self.connection, "save_reply_draft", request.model_dump(), thread_id=known_thread)
        try:
            if not request.confirmed:
                return _error(context, "CONFIRMATION_REQUIRED", "confirmed=true is required to save a draft.")
            thread = ThreadRepository(self.connection).get(request.thread_id)
            if not thread:
                return _error(context, "THREAD_NOT_FOUND", f"Thread not found: {request.thread_id}")
            draft_id = f"DRF-{uuid4().hex[:12].upper()}"
            payload = {
                "thread_id": request.thread_id,
                "agent_content": request.agent_content,
                "edited_content": request.edited_content,
                "ai_level": request.ai_level,
                "risk_level": request.risk_level,
            }
            with transaction(self.connection):
                idempotency = IdempotencyRepository(self.connection)
                decision = idempotency.reserve(
                    request.operation_id,
                    "save_reply_draft",
                    payload,
                    result_ref=draft_id,
                    commit=False,
                )
                if decision == "IDEMPOTENCY_CONFLICT":
                    raise ToolFailure("IDEMPOTENCY_CONFLICT", "operation_id was already used with a different payload.")
                if decision == "REPLAY":
                    existing = idempotency.get(request.operation_id)
                    draft = ReplyDraftRepository(self.connection).get(existing["result_ref"])
                    return _ok(context, {"draft": draft, "replayed": True})
                now = _now()
                draft = ReplyDraft(
                    draft_id=draft_id,
                    thread_id=request.thread_id,
                    agent_content=request.agent_content,
                    edited_content=request.edited_content,
                    ai_level=request.ai_level,
                    risk_level=request.risk_level,
                    created_at=now,
                    updated_at=now,
                )
                ReplyDraftRepository(self.connection).create(draft, commit=False)
                AuditLogRepository(self.connection).create(
                    AuditLog(
                        audit_id=f"AUD-{uuid4().hex[:12].upper()}",
                        task_id=context.task_id,
                        action="SAVE_REPLY_DRAFT",
                        before_summary="No draft created for this operation.",
                        after_summary=f"Saved draft_id={draft.draft_id} for thread_id={draft.thread_id}.",
                        created_at=_now(),
                    ),
                    commit=False,
                )
            return _ok(context, {"draft": draft.model_dump(mode="json"), "replayed": False})
        except ToolFailure as exc:
            return _error(context, exc.code, exc.message)
        except Exception as exc:
            return _error(context, "TOOL_ERROR", str(exc))

    def send_simulated_reply(self, **kwargs: Any) -> dict[str, Any]:
        request = self._validate(SendInput, "send_simulated_reply", kwargs)
        if isinstance(request, dict):
            return request
        known_thread = request.thread_id if ThreadRepository(self.connection).get(request.thread_id) else None
        context = _begin(self.connection, "send_simulated_reply", request.model_dump(), thread_id=known_thread)
        try:
            if not request.confirmed:
                return _error(context, "CONFIRMATION_REQUIRED", "confirmed=true is required to simulate sending.")
            thread = ThreadRepository(self.connection).get(request.thread_id)
            if not thread:
                return _error(context, "THREAD_NOT_FOUND", f"Thread not found: {request.thread_id}")
            payload = {
                "thread_id": request.thread_id,
                "recipient": request.recipient,
                "subject": request.subject,
                "body": request.body,
            }
            outbox_id = f"OUT-{uuid4().hex[:12].upper()}"
            with transaction(self.connection):
                idempotency = IdempotencyRepository(self.connection)
                decision = idempotency.reserve(
                    request.operation_id,
                    "send_simulated_reply",
                    payload,
                    result_ref=outbox_id,
                    commit=False,
                )
                if decision == "IDEMPOTENCY_CONFLICT":
                    raise ToolFailure("IDEMPOTENCY_CONFLICT", "operation_id was already used with a different payload.")
                if decision == "REPLAY":
                    existing = idempotency.get(request.operation_id)
                    message = OutboxRepository(self.connection).get_by_operation_id(request.operation_id)
                    return _ok(context, {"outbox": message, "replayed": True, "result_ref": existing["result_ref"]})
                message = OutboxMessage(
                    outbox_id=outbox_id,
                    thread_id=request.thread_id,
                    recipient=request.recipient,
                    subject=request.subject,
                    body=request.body,
                    simulated_sent_at=_now(),
                    operation_id=request.operation_id,
                )
                OutboxRepository(self.connection).create(message, commit=False)
                AuditLogRepository(self.connection).create(
                    AuditLog(
                        audit_id=f"AUD-{uuid4().hex[:12].upper()}",
                        task_id=context.task_id,
                        action="SEND_SIMULATED_REPLY",
                        before_summary="No simulated reply sent for this operation.",
                        after_summary=f"Saved outbox_id={message.outbox_id} for thread_id={message.thread_id}.",
                        created_at=_now(),
                    ),
                    commit=False,
                )
            return _ok(context, {"outbox": message.model_dump(mode="json"), "replayed": False})
        except ToolFailure as exc:
            return _error(context, exc.code, exc.message)
        except Exception as exc:
            return _error(context, "TOOL_ERROR", str(exc))


def create_mcp_server(connection: sqlite3.Connection):
    """Register exactly the eight project Tools on a FastMCP server."""
    from mcp.server.fastmcp import FastMCP

    tools = ReplyFlowTools(connection)
    server = FastMCP("ReplyFlow Tools")

    @server.tool(name="ingest_simulated_email")
    def ingest_tool(
        body: str,
        subject: str | None = None,
        sender_name: str | None = None,
        sender_email: str | None = None,
        source: str = "demo_console",
        source_message_id: str | None = None,
        order_context_id: str | None = None,
    ) -> dict[str, Any]:
        return tools.ingest_simulated_email(
            body=body,
            subject=subject,
            sender_name=sender_name,
            sender_email=sender_email,
            source=source,
            source_message_id=source_message_id,
            order_context_id=order_context_id,
        )

    @server.tool(name="get_email")
    def get_email_tool(email_id: str) -> dict[str, Any]:
        return tools.get_email(email_id=email_id)

    @server.tool(name="find_order")
    def find_order_tool(order_id: str | None = None, customer_email: str | None = None) -> dict[str, Any]:
        return tools.find_order(order_id=order_id, customer_email=customer_email)

    @server.tool(name="get_shipping_status")
    def get_shipping_status_tool(order_id: str) -> dict[str, Any]:
        return tools.get_shipping_status(order_id=order_id)

    @server.tool(name="search_reply_basis")
    def search_reply_basis_tool(query: str, limit: int = 5) -> dict[str, Any]:
        return tools.search_reply_basis(query=query, limit=limit)

    @server.tool(name="get_reply_tone")
    def get_reply_tone_tool() -> dict[str, Any]:
        return tools.get_reply_tone()

    @server.tool(name="save_reply_draft")
    def save_reply_draft_tool(
        thread_id: str,
        agent_content: str,
        edited_content: str | None = None,
        ai_level: str | None = None,
        risk_level: str | None = None,
        confirmed: bool = False,
        operation_id: str = "",
    ) -> dict[str, Any]:
        return tools.save_reply_draft(
            thread_id=thread_id,
            agent_content=agent_content,
            edited_content=edited_content,
            ai_level=ai_level,
            risk_level=risk_level,
            confirmed=confirmed,
            operation_id=operation_id,
        )

    @server.tool(name="send_simulated_reply")
    def send_simulated_reply_tool(
        thread_id: str,
        recipient: str,
        body: str,
        subject: str = "ReplyFlow simulated reply",
        confirmed: bool = False,
        operation_id: str = "",
    ) -> dict[str, Any]:
        return tools.send_simulated_reply(
            thread_id=thread_id,
            recipient=recipient,
            body=body,
            subject=subject,
            confirmed=confirmed,
            operation_id=operation_id,
        )

    return server
