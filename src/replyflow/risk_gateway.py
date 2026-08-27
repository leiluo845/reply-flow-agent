from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


RiskLevel = Literal["R0", "R1", "R2", "R3"]
AiLevel = Literal["L1", "L2", "L3", "BLOCKED"]
RISK_ORDER: dict[RiskLevel, int] = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}
LOW_CONFIDENCE_THRESHOLD = 0.75


class GatewayModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmailRiskContext(GatewayModel):
    subject: str = ""
    body: str = Field(min_length=1)
    sender_email: str | None = None
    attachments: list[str] = Field(default_factory=list)


class AnalysisRiskContext(GatewayModel):
    intent: str | None = None
    order_id: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0, le=1)
    model_suggested_risk_level: RiskLevel | None = None
    model_suggested_ai_level: Literal["L1", "L2", "L3"] | None = None


class BasisRiskContext(GatewayModel):
    status: Literal["HIT", "NO_HIT", "CONFLICT"] = "HIT"
    results_count: int = Field(default=1, ge=0)


class ToolError(GatewayModel):
    tool_name: str
    error_code: str
    message: str = ""


class RiskGatewayInput(GatewayModel):
    email: EmailRiskContext
    analysis: AnalysisRiskContext = Field(default_factory=AnalysisRiskContext)
    verified_facts: dict[str, Any] = Field(default_factory=dict)
    basis: BasisRiskContext = Field(default_factory=BasisRiskContext)
    tool_errors: list[ToolError] = Field(default_factory=list)
    draft: str | None = None
    requested_action: str = "simulate_reply"

    @field_validator("requested_action")
    @classmethod
    def normalize_requested_action(cls, value: str) -> str:
        return value.strip().lower()


class ChecklistItem(GatewayModel):
    item_id: str
    label: str
    required: bool = True


class RiskGatewayDecision(GatewayModel):
    risk_level: RiskLevel
    ai_level: AiLevel
    matched_rules: list[str]
    allowed_actions: list[str]
    blocked_actions: list[str]
    checklist: list[ChecklistItem] = Field(default_factory=list)


R3_ACTIONS = {
    "real_send": "R3_REAL_EXTERNAL_SEND_BLOCKED",
    "real_refund": "R3_REAL_REFUND_BLOCKED",
    "modify_order": "R3_ORDER_MODIFICATION_BLOCKED",
    "change_address": "R3_ORDER_MODIFICATION_BLOCKED",
    "bypass_confirmation": "R3_CONFIRMATION_BYPASS_BLOCKED",
}

R2_PATTERNS: dict[str, tuple[str, ...]] = {
    "R2_REFUND_OR_COMPENSATION": ("refund", "compensat", "reimburse"),
    "R2_CHARGEBACK_OR_DISPUTE": ("chargeback", "dispute"),
    "R2_COMPLAINT_OR_LEGAL": (
        "complaint",
        "complain",
        "report your store",
        "report the store",
        "legal action",
        "sue",
        "lawyer",
        "attorney",
    ),
    "R2_PROMPT_INJECTION": ("ignore previous", "ignore all", "system prompt", "hidden instruction", "developer message"),
}

COMMITMENT_PATTERNS: dict[str, tuple[str, ...]] = {
    "R2_DRAFT_REFUND_PROMISE": ("we will refund", "refund is approved", "refund has been approved", "refund you immediately"),
    "R2_DRAFT_COMPENSATION_PROMISE": ("we will compensate", "compensation is approved", "we will reimburse"),
    "R2_DRAFT_RESPONSIBILITY_PROMISE": ("our fault", "we are liable", "we accept responsibility"),
    "R2_DRAFT_EXACT_TIME_PROMISE": (
        "arrive tomorrow",
        "delivered tomorrow",
        "guaranteed delivery",
        "will arrive by",
        "will be delivered by",
    ),
    "R2_DRAFT_UNSUPPORTED_POLICY_ASSERTION": (
        "as required by our policies",
        "our policy requires",
        "under our policy",
    ),
}

R1_PATTERNS: dict[str, tuple[str, ...]] = {
    "R1_SIZE_OR_EXCHANGE": ("too small", "too large", "size", "exchange"),
    "R1_RETURN_INQUIRY": ("return",),
    "R1_DAMAGE_OR_WRONG_ITEM": ("damaged", "damage", "wrong item", "wrong color", "not what i ordered"),
}

LOW_RISK_LOGISTICS_PATTERNS = ("where is", "tracking", "track", "shipment", "shipping status", "check the status")


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _fact_is_true(facts: dict[str, Any], *keys: str) -> bool:
    return any(facts.get(key) is True for key in keys)


def _has_missing_order_id(request: RiskGatewayInput) -> bool:
    missing = {field.strip().lower() for field in request.analysis.missing_fields}
    if "order_id" in missing or "order id" in missing or "order_number" in missing:
        return True
    text = f"{request.email.subject}\n{request.email.body}".lower()
    looks_like_logistics = (request.analysis.intent or "").lower() == "shipment_inquiry" or _contains_any(
        text, LOW_RISK_LOGISTICS_PATTERNS
    )
    return looks_like_logistics and not request.analysis.order_id


def _checklist(rules: list[str]) -> list[ChecklistItem]:
    items = [
        ChecklistItem(item_id="verify_facts", label="I verified the available order and logistics facts."),
        ChecklistItem(item_id="review_customer_text", label="I reviewed the buyer-facing draft for unsupported commitments."),
        ChecklistItem(item_id="confirm_simulated_only", label="I understand this action only writes to the local simulated outbox."),
    ]
    if any(rule.startswith("R2_TOOL_ERROR") for rule in rules):
        items.insert(1, ChecklistItem(item_id="recheck_tool_error", label="I rechecked the Tool error before sending any response."))
    if "R2_IDENTITY_CONFLICT" in rules:
        items.insert(1, ChecklistItem(item_id="verify_identity", label="I verified that the buyer identity can receive the referenced facts."))
    if "R2_FACT_CONFLICT" in rules:
        items.insert(1, ChecklistItem(item_id="resolve_fact_conflict", label="I checked the conflicting buyer statement and verified facts."))
    if any("REFUND" in rule or "COMPENSATION" in rule or "CHARGEBACK" in rule for rule in rules):
        items.insert(1, ChecklistItem(item_id="no_refund_promise", label="I confirmed the response does not approve a refund or compensation."))
    return items


def _actions_for(ai_level: AiLevel) -> tuple[list[str], list[str]]:
    if ai_level == "L1":
        return (
            ["GENERATE_DRAFT", "SIMULATE_AUTO_REPLY"],
            ["REAL_SEND", "REAL_REFUND", "ORDER_MODIFICATION"],
        )
    if ai_level == "L2":
        return (
            ["GENERATE_DRAFT", "STORE_OPERATOR_CONFIRM_AND_SIMULATE_SEND"],
            ["SIMULATE_AUTO_REPLY", "REAL_SEND", "REAL_REFUND", "ORDER_MODIFICATION"],
        )
    if ai_level == "L3":
        return (
            ["GENERATE_REFERENCE_DRAFT", "STORE_OPERATOR_REVIEW", "SIMULATE_SEND_AFTER_CHECKLIST"],
            ["SIMULATE_AUTO_REPLY", "SEND_WITHOUT_CHECKLIST", "REAL_SEND", "REAL_REFUND", "ORDER_MODIFICATION"],
        )
    return (["DISPLAY_BLOCK_REASON"], ["SIMULATE_AUTO_REPLY", "SIMULATE_SEND", "REAL_SEND", "REAL_REFUND", "ORDER_MODIFICATION"])


def _deterministic_rules(request: RiskGatewayInput) -> tuple[RiskLevel, list[str]]:
    text = f"{request.email.subject}\n{request.email.body}".lower()
    draft = (request.draft or "").lower()
    rules: list[str] = []
    risk: RiskLevel = "R0"

    if request.requested_action in R3_ACTIONS:
        return "R3", [R3_ACTIONS[request.requested_action]]

    for rule, terms in R2_PATTERNS.items():
        if _contains_any(text, terms):
            rules.append(rule)
    for rule, terms in COMMITMENT_PATTERNS.items():
        if _contains_any(draft, terms):
            rules.append(rule)
    if re.search(r"(?:\$|usd\s*)\d+(?:\.\d{1,2})?", draft):
        rules.append("R2_DRAFT_AMOUNT_PROMISE")
    if request.tool_errors:
        rules.extend(f"R2_TOOL_ERROR_{error.tool_name.upper()}" for error in request.tool_errors)
    if request.basis.status == "CONFLICT":
        rules.append("R2_BASIS_CONFLICT")
    if _fact_is_true(request.verified_facts, "identity_conflict", "identity_match_failed"):
        rules.append("R2_IDENTITY_CONFLICT")
    if _fact_is_true(request.verified_facts, "facts_conflict", "fact_conflict"):
        rules.append("R2_FACT_CONFLICT")
    delivered = str(request.verified_facts.get("fulfillment_status", "")).lower() == "delivered"
    buyer_denies_delivery = _contains_any(
        text,
        ("did not receive", "didn't receive", "not received", "never received", "received nothing", "missing package"),
    )
    delivery_context = _contains_any(text, ("package", "parcel", "delivery", "carrier", "tracking"))
    # A delivered order and a missing-package statement are materially
    # contradictory. A return-label request alone is not such a conflict.
    if delivered and delivery_context and buyer_denies_delivery:
        rules.append("R2_FACT_CONFLICT")
    if request.analysis.confidence < LOW_CONFIDENCE_THRESHOLD:
        rules.append("R2_LOW_CONFIDENCE")
    if rules:
        return "R2", sorted(set(rules))

    if _has_missing_order_id(request):
        return "R1", ["R1_MISSING_ORDER_ID"]
    if _fact_is_true(request.verified_facts, "order_not_found"):
        return "R1", ["R1_ORDER_NOT_FOUND"]
    if request.basis.status == "NO_HIT" or request.basis.results_count == 0:
        return "R1", ["R1_BASIS_NOT_FOUND"]
    for rule, terms in R1_PATTERNS.items():
        if _contains_any(text, terms):
            return "R1", [rule]

    intent = (request.analysis.intent or "").strip().lower()
    facts_complete = _fact_is_true(request.verified_facts, "order_found") and _fact_is_true(
        request.verified_facts, "shipping_found"
    )
    is_logistics = intent == "shipment_inquiry" or _contains_any(text, LOW_RISK_LOGISTICS_PATTERNS)
    if is_logistics and facts_complete and request.basis.status == "HIT" and not request.analysis.missing_fields:
        return "R0", ["R0_LOW_RISK_LOGISTICS_ALLOWLIST"]
    return "R1", ["R1_NOT_ON_AUTO_REPLY_ALLOWLIST"]


def _apply_model_floor(
    request: RiskGatewayInput,
    deterministic_risk: RiskLevel,
    rules: list[str],
) -> tuple[RiskLevel, list[str]]:
    suggested = request.analysis.model_suggested_risk_level
    suggested_from_ai: RiskLevel | None = {
        "L1": "R0",
        "L2": "R1",
        "L3": "R2",
    }.get(request.analysis.model_suggested_ai_level)
    if suggested_from_ai and (not suggested or RISK_ORDER[suggested_from_ai] > RISK_ORDER[suggested]):
        suggested = suggested_from_ai
    if not suggested:
        return deterministic_risk, rules
    if RISK_ORDER[suggested] < RISK_ORDER[deterministic_risk]:
        return deterministic_risk, [*rules, "MODEL_CANNOT_DOWNGRADE_LOCAL_RISK"]
    if RISK_ORDER[suggested] > RISK_ORDER[deterministic_risk]:
        return suggested, [*rules, "MODEL_ESCALATED_RISK"]
    return deterministic_risk, rules


def evaluate_risk(request: RiskGatewayInput | dict[str, Any]) -> RiskGatewayDecision:
    """Return the local, deterministic processing boundary for one reply attempt."""
    parsed = request if isinstance(request, RiskGatewayInput) else RiskGatewayInput.model_validate(request)
    deterministic_risk, rules = _deterministic_rules(parsed)
    risk, rules = _apply_model_floor(parsed, deterministic_risk, rules)
    ai_level: AiLevel = {"R0": "L1", "R1": "L2", "R2": "L3", "R3": "BLOCKED"}[risk]
    allowed_actions, blocked_actions = _actions_for(ai_level)
    return RiskGatewayDecision(
        risk_level=risk,
        ai_level=ai_level,
        matched_rules=sorted(set(rules)),
        allowed_actions=allowed_actions,
        blocked_actions=blocked_actions,
        checklist=_checklist(rules) if risk == "R2" else [],
    )
