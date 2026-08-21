from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import (
    EmailRecord,
    OrderRecord,
    ReplyBasisRecord,
    ShippingEvent,
)
from .seed_validation import REPLY_BASIS_DIR, SEED_DIR, load_json, load_reply_basis_docs

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS emails (
    email_id TEXT PRIMARY KEY,
    source_message_id TEXT NOT NULL UNIQUE,
    sender_name TEXT NOT NULL,
    sender_email TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    received_at TEXT NOT NULL,
    source TEXT NOT NULL,
    order_context_id TEXT,
    attachments_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'RECEIVED',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS aggregate_threads (
    thread_id TEXT PRIMARY KEY,
    email_id TEXT NOT NULL REFERENCES emails(email_id),
    scenario TEXT,
    ai_level TEXT,
    risk_level TEXT,
    status TEXT NOT NULL DEFAULT 'WAITING_ANALYSIS',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_threads_status_updated
    ON aggregate_threads(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    customer_email TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    product_name TEXT NOT NULL,
    sku TEXT NOT NULL,
    amount TEXT NOT NULL,
    currency TEXT NOT NULL,
    order_status TEXT NOT NULL,
    payment_status TEXT NOT NULL,
    fulfillment_status TEXT NOT NULL,
    ordered_at TEXT NOT NULL,
    shipped_at TEXT,
    delivered_at TEXT,
    return_deadline TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shipping_events (
    event_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    event_time TEXT NOT NULL,
    location TEXT NOT NULL,
    status TEXT NOT NULL,
    description TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shipping_order_time
    ON shipping_events(order_id, event_time DESC);

CREATE TABLE IF NOT EXISTS reply_basis (
    basis_id TEXT NOT NULL,
    title TEXT NOT NULL,
    basis_type TEXT NOT NULL,
    section_id TEXT NOT NULL,
    content TEXT NOT NULL,
    version TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (basis_id, section_id, version)
);

CREATE TABLE IF NOT EXISTS reply_drafts (
    draft_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES aggregate_threads(thread_id),
    agent_content TEXT NOT NULL,
    edited_content TEXT,
    ai_level TEXT,
    risk_level TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outbox (
    outbox_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES aggregate_threads(thread_id),
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    simulated_sent_at TEXT NOT NULL,
    operation_id TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS task_runs (
    task_id TEXT PRIMARY KEY,
    thread_id TEXT REFERENCES aggregate_threads(thread_id),
    mode TEXT NOT NULL,
    state TEXT NOT NULL,
    skill_versions_json TEXT NOT NULL DEFAULT '{}',
    workflow_version TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    error_code TEXT
);

CREATE TABLE IF NOT EXISTS tool_traces (
    trace_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES task_runs(task_id),
    tool_name TEXT NOT NULL,
    input_summary TEXT NOT NULL,
    output_summary TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms INTEGER,
    error_code TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_decisions (
    decision_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES task_runs(task_id),
    risk_level TEXT NOT NULL,
    ai_level TEXT NOT NULL,
    matched_rules_json TEXT NOT NULL DEFAULT '[]',
    checklist_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS confirmations (
    confirmation_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES task_runs(task_id),
    action TEXT NOT NULL,
    confirmed_by TEXT NOT NULL,
    confirmed_at TEXT NOT NULL,
    checklist_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES task_runs(task_id),
    action TEXT NOT NULL,
    before_summary TEXT NOT NULL,
    after_summary TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    operation_id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    result_ref TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_results (
    run_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    expected_json TEXT NOT NULL,
    actual_json TEXT NOT NULL,
    passed INTEGER NOT NULL,
    failure_types_json TEXT NOT NULL DEFAULT '[]',
    trace_ref TEXT
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def connect_db(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)
    connection.commit()


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a callback-friendly transaction and roll back all owned writes on error."""
    owns_transaction = not connection.in_transaction
    try:
        if owns_transaction:
            connection.execute("BEGIN")
        yield connection
    except Exception:
        if owns_transaction:
            connection.rollback()
        raise
    else:
        if owns_transaction:
            connection.commit()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def seed_database(
    connection: sqlite3.Connection,
    *,
    seed_dir: Path = SEED_DIR,
    reply_basis_dir: Path = REPLY_BASIS_DIR,
) -> dict[str, int]:
    """Insert fictional read-only seed data. Re-running is idempotent."""
    basis_docs = load_reply_basis_docs() if reply_basis_dir == REPLY_BASIS_DIR else _load_basis_from_dir(reply_basis_dir)
    emails = [EmailRecord.model_validate(item) for item in load_json(seed_dir / "emails.json")]
    orders = [OrderRecord.model_validate(item) for item in load_json(seed_dir / "orders.json")]
    shipping_events = [ShippingEvent.model_validate(item) for item in load_json(seed_dir / "shipping_events.json")]

    with transaction(connection):
        for item in emails:
            connection.execute(
                """INSERT OR IGNORE INTO emails
                (email_id, source_message_id, sender_name, sender_email, subject, body,
                 received_at, source, order_context_id, attachments_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item.email_id,
                    item.source_message_id,
                    item.sender_name,
                    item.sender_email,
                    item.subject,
                    item.body,
                    item.received_at.isoformat().replace("+00:00", "Z"),
                    item.source,
                    item.order_context_id,
                    _json(item.attachments),
                    item.status,
                    utc_now(),
                ),
            )
        for item in orders:
            connection.execute(
                """INSERT OR IGNORE INTO orders
                (order_id, customer_email, customer_name, product_name, sku, amount,
                 currency, order_status, payment_status, fulfillment_status, ordered_at,
                 shipped_at, delivered_at, return_deadline)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item.order_id,
                    item.customer_email,
                    item.customer_name,
                    item.product_name,
                    item.sku,
                    item.amount,
                    item.currency,
                    item.order_status,
                    item.payment_status,
                    item.fulfillment_status,
                    item.ordered_at.isoformat().replace("+00:00", "Z"),
                    item.shipped_at.isoformat().replace("+00:00", "Z") if item.shipped_at else None,
                    item.delivered_at.isoformat().replace("+00:00", "Z") if item.delivered_at else None,
                    item.return_deadline,
                ),
            )
        for item in shipping_events:
            connection.execute(
                """INSERT OR IGNORE INTO shipping_events
                (event_id, order_id, event_time, location, status, description)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    item.event_id,
                    item.order_id,
                    item.event_time.isoformat().replace("+00:00", "Z"),
                    item.location,
                    item.status,
                    item.description,
                ),
            )
        basis_titles = {
            "logistics_basis": ("Logistics reply basis", "logistics"),
            "returns_exchange_basis": ("Returns and exchange reply basis", "returns_exchange"),
            "damage_refund_basis": ("Damage and refund reply basis", "damage_refund"),
            "tone_basis": ("Reply tone basis", "tone"),
        }
        for doc in basis_docs:
            title, basis_type = basis_titles.get(doc.path.stem, (doc.path.stem, doc.path.stem))
            for section in doc.sections:
                record = ReplyBasisRecord(
                    basis_id=doc.basis_id,
                    title=title,
                    basis_type=basis_type,
                    section_id=section["section_id"],
                    content=section["content"],
                    version=doc.version,
                    active=True,
                )
                connection.execute(
                    """INSERT OR IGNORE INTO reply_basis
                    (basis_id, title, basis_type, section_id, content, version, active)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.basis_id,
                        record.title,
                        record.basis_type,
                        record.section_id,
                        record.content,
                        record.version,
                        int(record.active),
                    ),
                )

    return {
        "emails": len(emails),
        "orders": len(orders),
        "shipping_events": len(shipping_events),
        "reply_basis": sum(len(doc.sections) for doc in basis_docs),
    }


def _load_basis_from_dir(directory: Path):
    """Load custom basis directories using the same small markdown format."""
    import re
    from .seed_validation import ReplyBasisDoc

    docs = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        basis = re.search(r"^basis_id:\s*(.+)$", text, re.MULTILINE)
        version = re.search(r"^version:\s*(.+)$", text, re.MULTILINE)
        sections = [
            {"section_id": m.group("section_id").strip(), "content": m.group("content").strip()}
            for m in re.finditer(
                r"^section_id:\s*(?P<section_id>.+?)\ncontent:\s*(?P<content>.+?)(?=\n\nsection_id:|\Z)",
                text,
                re.MULTILINE | re.DOTALL,
            )
        ]
        if not basis or not version or not sections:
            raise ValueError(f"Malformed reply basis doc: {path}")
        docs.append(ReplyBasisDoc(basis_id=basis.group(1).strip(), version=version.group(1).strip(), sections=sections, path=path))
    return docs


def payload_hash(payload: object) -> str:
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()
