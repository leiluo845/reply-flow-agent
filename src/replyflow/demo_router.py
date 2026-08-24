from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


ORDER_ID_PATTERN = re.compile(r"\b(ORD-\d{4})\b", flags=re.IGNORECASE)
LOGISTICS_TERMS = ("where is", "tracking", "track", "shipping", "shipment", "package", "status")
HIGH_RISK_TERMS = ("refund", "chargeback", "dispute", "legal action", "complaint", "report your store")
RETURN_TERMS = ("return", "exchange", "too small", "too large", "damaged", "wrong item", "wrong color")


class DemoAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    order_id: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    supported: bool
    limitation_message: str | None = None


def _text(subject: str, body: str) -> str:
    return f"{subject}\n{body}".lower()


def _order_id(text: str) -> str | None:
    match = ORDER_ID_PATTERN.search(text)
    return match.group(1).upper() if match else None


def analyze_demo_email(subject: str, body: str) -> DemoAnalysis:
    """Small deterministic classifier for explainable Demo Mode only."""
    text = _text(subject, body)
    order_id = _order_id(text)
    if len(body) > 600:
        return DemoAnalysis(
            intent="demo_scope_limited",
            order_id=order_id,
            confidence=0.8,
            supported=False,
            limitation_message="Demo Mode cannot reliably classify this long message. Switch to Interactive Mode for model analysis.",
        )
    if any(term in text for term in HIGH_RISK_TERMS):
        return DemoAnalysis(intent="high_risk_after_sales", order_id=order_id, confidence=0.97, supported=True)
    matched_groups = sum(
        [
            any(term in text for term in LOGISTICS_TERMS),
            any(term in text for term in RETURN_TERMS),
        ]
    )
    if matched_groups > 1 and ("address" in text or "cancel" in text):
        return DemoAnalysis(
            intent="demo_scope_limited",
            order_id=order_id,
            confidence=0.8,
            supported=False,
            limitation_message="Demo Mode only supports one clear request at a time. Switch to Interactive Mode for this message.",
        )
    if any(term in text for term in LOGISTICS_TERMS):
        return DemoAnalysis(
            intent="shipment_inquiry",
            order_id=order_id,
            missing_fields=[] if order_id else ["order_id"],
            confidence=0.93 if order_id else 0.86,
            supported=True,
        )
    if any(term in text for term in RETURN_TERMS):
        intent = "size_or_exchange" if any(term in text for term in ("exchange", "too small", "too large", "size")) else "return_or_item_issue"
        return DemoAnalysis(intent=intent, order_id=order_id, confidence=0.9, supported=True)
    return DemoAnalysis(
        intent="demo_scope_limited",
        order_id=order_id,
        confidence=0.8,
        supported=False,
        limitation_message="Demo Mode cannot reliably classify this message. Switch to Interactive Mode for model analysis.",
    )


def basis_query_for(analysis: DemoAnalysis) -> str:
    return {
        "shipment_inquiry": "delivery status",
        "high_risk_after_sales": "refund chargeback",
        "size_or_exchange": "size exchange",
        "return_or_item_issue": "return damaged wrong item",
    }.get(analysis.intent, "missing order")


def draft_demo_reply(
    *,
    analysis: DemoAnalysis,
    email: dict[str, Any],
    facts: dict[str, Any],
    tool_errors: list[dict[str, str]],
) -> str | None:
    """Create a bounded draft from facts; no generic answer for unsupported input."""
    if not analysis.supported:
        return None
    order_id = analysis.order_id or "your order"
    if tool_errors:
        return (
            "Hello,\n\n"
            "Thank you for your message. We need to recheck the latest order or carrier details before sending a final update. "
            "We will review the available information carefully.\n\nBest regards,"
        )
    if analysis.intent == "shipment_inquiry" and not analysis.order_id:
        return (
            "Hello,\n\n"
            "I can help check the shipment. Could you please share your order number so we can verify the latest details?\n\n"
            "Best regards,"
        )
    if analysis.intent == "shipment_inquiry":
        latest = facts.get("latest_shipping") or {}
        latest_status = latest.get("status", "available")
        latest_time = latest.get("event_time", "the latest carrier update")
        return (
            "Hello,\n\n"
            f"Thank you for your message about {order_id}. The latest verified carrier update is '{latest_status}' at {latest_time}. "
            "We will continue to monitor the carrier updates.\n\nBest regards,"
        )
    if analysis.intent == "high_risk_after_sales":
        return (
            "Hello,\n\n"
            f"I understand your concern about {order_id}. We need to carefully verify the order and delivery details before providing a final update. "
            "Please share any safe details that may help us review the situation.\n\nBest regards,"
        )
    if analysis.intent == "size_or_exchange":
        return (
            "Hello,\n\n"
            f"Thank you for letting us know about {order_id}. Could you please confirm the size you received and the size you need? "
            "We will verify the available order details before confirming next steps.\n\nBest regards,"
        )
    return (
        "Hello,\n\n"
        f"Thank you for your message about {order_id}. We will review the available order details and may need a little more information before confirming next steps.\n\n"
        "Best regards,"
    )
