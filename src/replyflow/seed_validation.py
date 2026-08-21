from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = ROOT / "data" / "seed"
REPLY_BASIS_DIR = ROOT / "data" / "reply_basis"
SCENARIO_CATALOG_PATH = ROOT / "docs" / "scenario_catalog.md"

ALLOWED_FULFILLMENT_STATUSES = {"processing", "paid", "in_transit", "delivered"}
ALLOWED_ORDER_STATUSES = {"paid"}
ALLOWED_PAYMENT_STATUSES = {"paid"}
ALLOWED_CURRENCIES = {"USD"}
RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}


@dataclass(frozen=True)
class ReplyBasisDoc:
    basis_id: str
    version: str
    sections: list[dict[str, str]]
    path: Path


@dataclass(frozen=True)
class SeedValidationReport:
    email_count: int
    order_count: int
    shipping_event_count: int
    tool_failure_count: int
    reply_basis_count: int
    case_count: int
    r2_case_count: int
    level_counts: dict[str, int]
    risk_counts: dict[str, int]
    scenario_counts: dict[str, int]
    issues: list[str]

    @property
    def ok(self) -> bool:
        return not self.issues


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_reply_basis_docs() -> list[ReplyBasisDoc]:
    docs: list[ReplyBasisDoc] = []
    for path in sorted(REPLY_BASIS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        basis_match = re.search(r"^basis_id:\s*(.+)$", text, flags=re.MULTILINE)
        version_match = re.search(r"^version:\s*(.+)$", text, flags=re.MULTILINE)
        section_matches = list(
            re.finditer(
                r"^section_id:\s*(?P<section_id>.+?)\ncontent:\s*(?P<content>.+?)(?=\n\nsection_id:|\Z)",
                text,
                flags=re.MULTILINE | re.DOTALL,
            )
        )
        if not basis_match or not version_match:
            raise ValueError(f"Malformed reply basis doc: {path}")

        sections = [
            {"section_id": match.group("section_id").strip(), "content": match.group("content").strip()}
            for match in section_matches
        ]
        if not sections:
            raise ValueError(f"Reply basis doc has no sections: {path}")

        docs.append(
            ReplyBasisDoc(
                basis_id=basis_match.group(1).strip(),
                version=version_match.group(1).strip(),
                sections=sections,
                path=path,
            )
        )
    return docs


def _parse_iso_datetime(value: str, *, field_name: str, path_label: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid datetime for {field_name} in {path_label}: {value}") from exc


def _validate_email_record(record: dict[str, Any], index: int, issues: list[str]) -> None:
    required = {
        "email_id",
        "source_message_id",
        "sender_name",
        "sender_email",
        "subject",
        "body",
        "received_at",
        "source",
        "order_context_id",
        "attachments",
    }
    missing = required - record.keys()
    if missing:
        issues.append(f"email[{index}] missing keys: {sorted(missing)}")

    sender_email = str(record.get("sender_email", ""))
    if not sender_email.endswith("@example.com"):
        issues.append(f"email[{index}] sender_email must end with @example.com: {sender_email}")

    received_at = str(record.get("received_at", ""))
    _parse_iso_datetime(received_at, field_name="received_at", path_label=f"email[{index}]")

    attachments = record.get("attachments")
    if not isinstance(attachments, list):
        issues.append(f"email[{index}] attachments must be a list")

    for key in record.keys():
        if key.startswith("expected_"):
            issues.append(f"email[{index}] must not contain evaluation-only key: {key}")


def _validate_order_record(record: dict[str, Any], index: int, issues: list[str]) -> None:
    required = {
        "order_id",
        "customer_email",
        "customer_name",
        "product_name",
        "sku",
        "amount",
        "currency",
        "order_status",
        "payment_status",
        "fulfillment_status",
        "ordered_at",
        "shipped_at",
        "delivered_at",
        "return_deadline",
    }
    missing = required - record.keys()
    if missing:
        issues.append(f"order[{index}] missing keys: {sorted(missing)}")

    customer_email = str(record.get("customer_email", ""))
    if not customer_email.endswith("@example.com"):
        issues.append(f"order[{index}] customer_email must end with @example.com: {customer_email}")

    currency = str(record.get("currency", ""))
    if currency not in ALLOWED_CURRENCIES:
        issues.append(f"order[{index}] unsupported currency: {currency}")

    order_status = str(record.get("order_status", ""))
    payment_status = str(record.get("payment_status", ""))
    fulfillment_status = str(record.get("fulfillment_status", ""))
    if order_status not in ALLOWED_ORDER_STATUSES:
        issues.append(f"order[{index}] unsupported order_status: {order_status}")
    if payment_status not in ALLOWED_PAYMENT_STATUSES:
        issues.append(f"order[{index}] unsupported payment_status: {payment_status}")
    if fulfillment_status not in ALLOWED_FULFILLMENT_STATUSES:
        issues.append(f"order[{index}] unsupported fulfillment_status: {fulfillment_status}")

    amount = Decimal(str(record.get("amount", "0")))
    if amount <= 0:
        issues.append(f"order[{index}] amount must be positive")

    ordered_at = _parse_iso_datetime(str(record.get("ordered_at", "")), field_name="ordered_at", path_label=f"order[{index}]")
    shipped_at_raw = record.get("shipped_at")
    delivered_at_raw = record.get("delivered_at")
    return_deadline = date.fromisoformat(str(record.get("return_deadline", "")))

    if shipped_at_raw:
        shipped_at = _parse_iso_datetime(str(shipped_at_raw), field_name="shipped_at", path_label=f"order[{index}]")
        if shipped_at < ordered_at:
            issues.append(f"order[{index}] shipped_at is earlier than ordered_at")
    else:
        shipped_at = None

    if delivered_at_raw:
        delivered_at = _parse_iso_datetime(str(delivered_at_raw), field_name="delivered_at", path_label=f"order[{index}]")
        if shipped_at and delivered_at < shipped_at:
            issues.append(f"order[{index}] delivered_at is earlier than shipped_at")
        if delivered_at.date() > return_deadline:
            issues.append(f"order[{index}] return_deadline must not precede delivered_at")
    else:
        delivered_at = None

    if fulfillment_status == "delivered" and not delivered_at_raw:
        issues.append(f"order[{index}] delivered orders must set delivered_at")
    if fulfillment_status == "processing" and (shipped_at_raw or delivered_at_raw):
        issues.append(f"order[{index}] processing orders should not have shipping timestamps")
    if fulfillment_status == "in_transit" and not shipped_at_raw:
        issues.append(f"order[{index}] in_transit orders must set shipped_at")


def _validate_shipping_event_record(record: dict[str, Any], index: int, order_ids: set[str], issues: list[str]) -> None:
    required = {"event_id", "order_id", "event_time", "location", "status", "description"}
    missing = required - record.keys()
    if missing:
        issues.append(f"shipping_event[{index}] missing keys: {sorted(missing)}")

    order_id = str(record.get("order_id", ""))
    if order_id not in order_ids:
        issues.append(f"shipping_event[{index}] references unknown order_id: {order_id}")

    _parse_iso_datetime(str(record.get("event_time", "")), field_name="event_time", path_label=f"shipping_event[{index}]")


def _validate_case_record(
    record: dict[str, Any],
    index: int,
    email_ids: set[str],
    order_ids: set[str],
    scenario_ids: set[str],
    issues: list[str],
) -> None:
    required = {
        "case_id",
        "email_id",
        "scenario_id",
        "source_type",
        "expected_intent",
        "expected_order_id",
        "expected_tools",
        "expected_ai_level",
        "expected_risk",
        "expected_terminal_state",
        "must_not_claim",
    }
    missing = required - record.keys()
    if missing:
        issues.append(f"case[{index}] missing keys: {sorted(missing)}")

    email_id = str(record.get("email_id", ""))
    if email_id not in email_ids:
        issues.append(f"case[{index}] references unknown email_id: {email_id}")

    scenario_id = str(record.get("scenario_id", ""))
    if scenario_id not in scenario_ids:
        issues.append(f"case[{index}] references unknown scenario_id: {scenario_id}")

    expected_order_id = record.get("expected_order_id")
    if expected_order_id is not None and expected_order_id not in order_ids and scenario_id != "S06":
        issues.append(f"case[{index}] references unknown expected_order_id: {expected_order_id}")

    tools = record.get("expected_tools")
    if not isinstance(tools, list) or not tools:
        issues.append(f"case[{index}] expected_tools must be a non-empty list")

    must_not_claim = record.get("must_not_claim")
    if not isinstance(must_not_claim, list):
        issues.append(f"case[{index}] must_not_claim must be a list")

    source_type = str(record.get("source_type", ""))
    if source_type not in {"buyer_message", "non_buyer_message"}:
        issues.append(f"case[{index}] invalid source_type: {source_type}")

    level = record.get("expected_ai_level")
    if level is not None and level not in {"L1", "L2", "L3"}:
        issues.append(f"case[{index}] invalid expected_ai_level: {level}")

    risk = record.get("expected_risk")
    if risk is not None and risk not in RISK_ORDER:
        issues.append(f"case[{index}] invalid expected_risk: {risk}")


def _validate_tool_failure_record(record: dict[str, Any], index: int, order_ids: set[str], issues: list[str]) -> None:
    required = {"failure_id", "tool_name", "error_code", "message"}
    missing = required - record.keys()
    if missing:
        issues.append(f"tool_failure[{index}] missing keys: {sorted(missing)}")

    tool_name = str(record.get("tool_name", ""))
    if tool_name not in {"find_order", "get_shipping_status", "search_reply_basis"}:
        issues.append(f"tool_failure[{index}] invalid tool_name: {tool_name}")

    trigger_order_id = record.get("trigger_order_id")
    if trigger_order_id is not None and trigger_order_id not in order_ids:
        issues.append(f"tool_failure[{index}] references unknown trigger_order_id: {trigger_order_id}")

    if tool_name == "search_reply_basis":
        trigger_phrase = str(record.get("trigger_phrase", ""))
        if not trigger_phrase:
            issues.append(f"tool_failure[{index}] search_reply_basis failures need trigger_phrase")
    else:
        if not trigger_order_id:
            issues.append(f"tool_failure[{index}] {tool_name} failures need trigger_order_id")


def _extract_scenario_ids() -> set[str]:
    text = SCENARIO_CATALOG_PATH.read_text(encoding="utf-8")
    return set(match.group(1).strip() for match in re.finditer(r"^\|\s*(S\d{2})\s", text, flags=re.MULTILINE))


def validate_seed_data() -> SeedValidationReport:
    issues: list[str] = []

    emails = load_json(SEED_DIR / "emails.json")
    orders = load_json(SEED_DIR / "orders.json")
    shipping_events = load_json(SEED_DIR / "shipping_events.json")
    tool_failures = load_json(SEED_DIR / "tool_failures.json")
    case_manifest = load_json(SEED_DIR / "case_manifest.json")
    reply_basis_docs = load_reply_basis_docs()
    scenario_ids = _extract_scenario_ids()

    if len(emails) < 30:
        issues.append(f"expected at least 30 emails, found {len(emails)}")
    if len(orders) < 20:
        issues.append(f"expected at least 20 orders, found {len(orders)}")
    if len(reply_basis_docs) != 4:
        issues.append(f"expected exactly 4 reply basis docs, found {len(reply_basis_docs)}")
    if len(case_manifest) != 30:
        issues.append(f"expected 30 evaluation cases, found {len(case_manifest)}")

    email_ids = set()
    for index, record in enumerate(emails, start=1):
        if record.get("email_id") in email_ids:
            issues.append(f"duplicate email_id: {record.get('email_id')}")
        email_ids.add(str(record.get("email_id")))
        _validate_email_record(record, index, issues)

    order_ids = set()
    for index, record in enumerate(orders, start=1):
        if record.get("order_id") in order_ids:
            issues.append(f"duplicate order_id: {record.get('order_id')}")
        order_ids.add(str(record.get("order_id")))
        _validate_order_record(record, index, issues)

    for index, record in enumerate(shipping_events, start=1):
        _validate_shipping_event_record(record, index, order_ids, issues)

    for index, record in enumerate(case_manifest, start=1):
        _validate_case_record(record, index, email_ids, order_ids, scenario_ids, issues)

    for index, record in enumerate(tool_failures, start=1):
        _validate_tool_failure_record(record, index, order_ids, issues)

    risk_counts = Counter(
        str(case.get("expected_risk"))
        for case in case_manifest
        if case.get("expected_risk") is not None
    )
    level_counts = Counter(
        str(case.get("expected_ai_level"))
        for case in case_manifest
        if case.get("expected_ai_level") is not None
    )
    scenario_counts = Counter(str(case.get("scenario_id")) for case in case_manifest)

    if risk_counts.get("R2", 0) < 10:
        issues.append(f"expected at least 10 R2 cases, found {risk_counts.get('R2', 0)}")
    for required_level in ("L1", "L2", "L3"):
        if level_counts.get(required_level, 0) < 1:
            issues.append(f"expected at least one {required_level} case")
    if len({case.get("source_type") for case in case_manifest}) < 2:
        issues.append("expected both buyer_message and non_buyer_message cases")

    for record in emails + orders + shipping_events:
        if any(key.startswith("expected_") for key in record):
            issues.append("runtime seed data must not contain evaluation-only expected_* fields")

    return SeedValidationReport(
        email_count=len(emails),
        order_count=len(orders),
        shipping_event_count=len(shipping_events),
        tool_failure_count=len(tool_failures),
        reply_basis_count=len(reply_basis_docs),
        case_count=len(case_manifest),
        r2_case_count=risk_counts.get("R2", 0),
        level_counts=dict(level_counts),
        risk_counts=dict(risk_counts),
        scenario_counts=dict(scenario_counts),
        issues=issues,
    )


def main() -> int:
    report = validate_seed_data()
    if report.ok:
        print("Seed data validation passed.")
        print(
            f"emails={report.email_count} orders={report.order_count} "
            f"shipping_events={report.shipping_event_count} basis_docs={report.reply_basis_count} "
            f"cases={report.case_count} r2_cases={report.r2_case_count}"
        )
        return 0

    print("Seed data validation failed.")
    for issue in report.issues:
        print(f"- {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
