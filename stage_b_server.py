from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import threading
import time
from copy import deepcopy
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from replyflow.coze_client import CozeClient
from replyflow.config import load_settings
from replyflow.db import connect_db, initialize_schema, seed_database
from replyflow.interactive_orchestrator import InteractiveOrchestrator
from replyflow.ingestion import ingest_simulated_email
from replyflow.repositories import EmailRepository, ThreadRepository
from replyflow.ui_helpers import build_source_message_id


CASE_DEFS: list[dict[str, Any]] = [
    # Preloaded demo senders intentionally match their linked buyer account.
    # This keeps identity verification from turning every case into L3.
    {"key": "andrea", "name": "Andrea", "email": "buyer03@example.com", "subject": "Return label has not been received", "body": "I have not received a return label yet for this order. Please send it to me.", "order": "ORD-1003"},
    {"key": "john", "name": "John", "email": "buyer01@example.com", "subject": "Order delivery inquiry from Amazon customer", "body": "The tracking for ORD-1001 has not changed for several days. Could you please check it?", "order": "ORD-1001"},
    {"key": "michael", "name": "Michael", "email": "buyer07@example.com", "subject": "Package shows delivered but not received", "body": "My package for ORD-1007 shows delivered, but I have not received it. Please refund me or I will file a chargeback.", "order": "ORD-1007"},
    {"key": "meghan", "name": "Meghan", "email": "buyer03@example.com", "subject": "Return label has not been received", "body": "Please resend the return label for ORD-1003 as an attachment.", "order": "ORD-1003"},
    {"key": "cindy", "name": "Cindy", "email": "buyer07@example.com", "subject": "Package shows delivered but not received", "body": "The carrier shows delivered, but the package is not at my address. Order ORD-1007.", "order": "ORD-1007"},
    {"key": "matt", "name": "Matt", "email": "buyer02@example.com", "subject": "Product details inquiry", "body": "Could you confirm whether the jacket in ORD-1002 is water resistant enough for light rain?", "order": "ORD-1002"},
]


def _source(case: dict[str, Any]) -> str:
    return "STAGE-B-" + build_source_message_id(
        subject=case["subject"], body=case["body"], sender_email=case["email"], order_context_id=case.get("order")
    )


class StageBManager:
    def __init__(self, db_path: Path | None = None) -> None:
        self.settings = load_settings()
        self.db_path = db_path or (ROOT / "data" / "local" / "stage_b_demo.sqlite3")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        initialize_schema(self.connection)
        seed_database(self.connection)
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS stage_b_cases (
                case_key TEXT PRIMARY KEY,
                sender_name TEXT NOT NULL,
                sender_email TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                order_context_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS stage_b_rollback_events (
                event_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                case_key TEXT NOT NULL,
                previous_status TEXT NOT NULL,
                previous_ai_level TEXT,
                previous_risk_level TEXT,
                removed_draft INTEGER NOT NULL DEFAULT 0,
                removed_outbox INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.connection.commit()
        self.lock = threading.RLock()
        self.agent_enabled = False
        self.dynamic_cases: dict[str, dict[str, Any]] = {
            row["case_key"]: {
                "key": row["case_key"], "name": row["sender_name"], "email": row["sender_email"],
                "subject": row["subject"], "body": row["body"], "order": row["order_context_id"], "dynamic": True,
            }
            for row in self.connection.execute("SELECT * FROM stage_b_cases ORDER BY created_at, case_key").fetchall()
        }
        self.queue: list[str] = []
        self.worker: threading.Thread | None = None
        self.batch: dict[str, Any] | None = None
        self.last_batch: dict[str, Any] | None = None
        self.last_rollback: dict[str, Any] | None = None

    def _all_cases(self) -> list[dict[str, Any]]:
        return CASE_DEFS + list(self.dynamic_cases.values())

    def _thread(self, case: dict[str, Any]) -> dict[str, Any] | None:
        row = self.connection.execute(
            """SELECT t.*, e.email_id, e.source_message_id, e.sender_name, e.sender_email, e.subject, e.body
               FROM aggregate_threads t JOIN emails e ON e.email_id = t.email_id
               WHERE e.source_message_id = ?""",
            (_source(case),),
        ).fetchone()
        return dict(row) if row else None

    def _artifacts(self, thread_id: str | None) -> dict[str, Any]:
        if not thread_id:
            return {}
        draft = self.connection.execute("SELECT * FROM reply_drafts WHERE thread_id = ? ORDER BY created_at DESC LIMIT 1", (thread_id,)).fetchone()
        outbox = self.connection.execute("SELECT * FROM outbox WHERE thread_id = ? ORDER BY simulated_sent_at DESC LIMIT 1", (thread_id,)).fetchone()
        return {"draft": dict(draft) if draft else None, "outbox": dict(outbox) if outbox else None}

    def state(self) -> dict[str, Any]:
        with self.lock:
            items: list[dict[str, Any]] = []
            for case in self._all_cases():
                thread = self._thread(case)
                artifacts = self._artifacts(thread.get("thread_id") if thread else None)
                order = None
                if case.get("order"):
                    row = self.connection.execute("SELECT * FROM orders WHERE order_id = ?", (case["order"],)).fetchone()
                    order = dict(row) if row else None
                item = {**case, "status": thread.get("status", "WAITING_ANALYSIS") if thread else "WAITING_ANALYSIS", "ai_level": thread.get("ai_level") if thread else None, "risk_level": thread.get("risk_level") if thread else None, "thread_id": thread.get("thread_id") if thread else None, "draft": artifacts.get("draft"), "outbox": artifacts.get("outbox"), "order_details": order}
                items.append(item)
            batch = deepcopy(self.batch or self.last_batch)
            if batch:
                batch.pop("cases", None)
            pending = [item for item in items if item["status"] in {"WAITING_ANALYSIS", "FAILED"}]
            return {"agent_enabled": self.agent_enabled, "items": items, "batch": batch, "pending_count": len(pending), "can_rollback": bool(self.last_batch and self.last_batch.get("status") == "completed"), "last_rollback": getattr(self, "last_rollback", None)}

    def toggle(self, enabled: bool) -> dict[str, Any]:
        with self.lock:
            self.agent_enabled = bool(enabled)
            if not self.agent_enabled:
                # Finish the item currently in flight, but do not start queued
                # messages after the operator turns the global switch off.
                self.queue.clear()
            else:
                pending = [case["key"] for case in self._all_cases() if self._thread(case) is None or self._thread(case).get("status") in {"WAITING_ANALYSIS", "FAILED"}]
                self.queue.extend(key for key in pending if key not in self.queue)
                self._ensure_worker()
            return self.state()

    def add_case(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = str(payload.get("body", "")).strip()
        if not body:
            raise ValueError("正文不能为空")
        name = str(payload.get("name") or "Demo Buyer").strip()
        email_input = str(payload.get("email") or "").strip()
        subject = str(payload.get("subject") or "New simulated customer message").strip()
        order = str(payload.get("order") or "").strip() or None
        # The modal uses demo-buyer@example.com as a visible placeholder. When
        # an order is selected, resolve that placeholder to the linked buyer so
        # the normal demo path does not create a false identity conflict.
        email = email_input or "demo-buyer@example.com"
        if order and email.lower() == "demo-buyer@example.com":
            linked = self.connection.execute("SELECT customer_email FROM orders WHERE order_id = ?", (order,)).fetchone()
            if linked and linked["customer_email"]:
                email = linked["customer_email"]
        key = "demo-" + hashlib.sha256(f"{name}|{email}|{subject}|{body}|{order}".encode()).hexdigest()[:10]
        case = {"key": key, "name": name, "email": email, "subject": subject, "body": body, "order": order, "dynamic": True}
        with self.lock:
            self.dynamic_cases[key] = case
            self.connection.execute(
                "INSERT OR REPLACE INTO stage_b_cases(case_key, sender_name, sender_email, subject, body, order_context_id) VALUES (?, ?, ?, ?, ?, ?)",
                (key, name, email, subject, body, order),
            )
            ingest_simulated_email(
                self.connection,
                body=body,
                subject=subject,
                sender_name=name,
                sender_email=email,
                source="demo_console",
                source_message_id=_source(case),
                order_context_id=order,
            )
            self.connection.commit()
            if self.agent_enabled:
                self.queue.append(key)
                self._ensure_worker()
            return case

    def _ensure_worker(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.worker = threading.Thread(target=self._run_batch, name="replyflow-stage-b", daemon=True)
        self.worker.start()

    def _run_batch(self) -> None:
        with self.lock:
            keys = []
            for key in self.queue:
                if key not in keys:
                    keys.append(key)
            self.queue.clear()
            if not keys:
                return
            batch_id = "BATCH-" + hashlib.sha256(f"{time.time_ns()}".encode()).hexdigest()[:12].upper()
            self.batch = {"batch_id": batch_id, "status": "running", "total": len(keys), "completed": 0, "current": None, "counts": {"L1": 0, "L2": 0, "L3": 0, "failed": 0}, "started_at": time.time(), "results": {}, "cases": keys}
        while True:
            with self.lock:
                if self.queue and self.agent_enabled:
                    for key in self.queue:
                        if key not in self.batch["cases"]:
                            self.batch["cases"].append(key)
                            self.batch["total"] += 1
                    self.queue.clear()
                elif not self.agent_enabled:
                    self.queue.clear()
                index = self.batch["completed"]
                if index >= self.batch["total"]:
                    self.batch["status"] = "completed"
                    self.batch["finished_at"] = time.time()
                    self.last_batch = deepcopy(self.batch)
                    self.batch = deepcopy(self.last_batch)
                    return
                key = self.batch["cases"][index]
                self.batch["current"] = key
                case = next((item for item in self._all_cases() if item["key"] == key), None)
            if not case:
                result = {"status": "FAILED", "error_code": "CASE_NOT_FOUND"}
            else:
                try:
                    result_obj = InteractiveOrchestrator(self.connection, CozeClient(self.settings)).run(
                        body=case["body"], subject=case["subject"], sender_name=case["name"], sender_email=case["email"], source_message_id=_source(case), order_context_id=case.get("order")
                    )
                    result = result_obj.model_dump()
                except Exception as exc:  # pragma: no cover - final safety boundary for demo server
                    result = {"status": "FAILED", "error_code": "STAGE_B_SERVER_ERROR", "notice": str(exc)}
            with self.lock:
                status = result.get("thread_status") or result.get("status") or "FAILED"
                level = result.get("ai_level")
                self.batch["results"][key] = result
                self.batch["completed"] += 1
                self.batch["counts"][level if level in {"L1", "L2", "L3"} else "failed"] += 1

    def send(self, key: str, body: str, checklist: dict[str, bool] | None = None) -> dict[str, Any]:
        with self.lock:
            case = next((item for item in self._all_cases() if item["key"] == key), None)
            if not case:
                raise ValueError("邮件不存在")
            thread = self._thread(case)
            if not thread:
                raise ValueError("该邮件尚未完成 AI 处理")
            level = thread.get("ai_level")
            if level == "L3" and not all((checklist or {}).values()):
                raise ValueError("L3 邮件必须完成高风险核对清单")
            if level not in {"L2", "L3"}:
                raise ValueError("当前邮件不处于人工发送状态")
            email = EmailRepository(self.connection).get(thread["email_id"])
            operation = "stage-b-manual-send-" + hashlib.sha256(f"{thread['thread_id']}|{body}".encode()).hexdigest()[:20]
            result = self._send_tool(thread["thread_id"], email, body, operation, checklist=checklist or {})
            return result

    def _send_tool(self, thread_id: str, email: dict[str, Any], body: str, operation: str, *, checklist: dict[str, bool] | None = None) -> dict[str, Any]:
        from replyflow.mcp_tools import ReplyFlowTools

        result = ReplyFlowTools(self.connection).send_simulated_reply(thread_id=thread_id, recipient=email["sender_email"], subject="Re: " + email["subject"], body=body, confirmed=True, checklist=checklist or {}, operation_id=operation)
        if not result["ok"]:
            raise ValueError(result["data"]["message"])
        ThreadRepository(self.connection).update_status(thread_id, "AI_REPLIED", ai_level=None, risk_level=None)
        return result["data"]["outbox"]

    def rollback(self) -> dict[str, Any]:
        with self.lock:
            if self.batch and self.batch.get("status") == "running":
                raise ValueError("当前批次仍在处理，完成后才可撤回")
            if not self.last_batch or self.last_batch.get("status") != "completed":
                raise ValueError("当前没有可撤回的已完成演示批次")
            rolled = 0
            batch_id = self.last_batch["batch_id"]
            for key in self.last_batch.get("cases", []):
                case = next((item for item in self._all_cases() if item["key"] == key), None)
                if not case:
                    continue
                thread = self._thread(case)
                if not thread:
                    continue
                thread_id = thread["thread_id"]
                draft_exists = self.connection.execute("SELECT 1 FROM reply_drafts WHERE thread_id = ? LIMIT 1", (thread_id,)).fetchone() is not None
                outbox_exists = self.connection.execute("SELECT 1 FROM outbox WHERE thread_id = ? LIMIT 1", (thread_id,)).fetchone() is not None
                self.connection.execute(
                    "INSERT INTO stage_b_rollback_events(event_id, batch_id, case_key, previous_status, previous_ai_level, previous_risk_level, removed_draft, removed_outbox) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    ("RB-" + hashlib.sha256(f"{batch_id}|{key}".encode()).hexdigest()[:16].upper(), batch_id, key, thread["status"], thread.get("ai_level"), thread.get("risk_level"), int(draft_exists), int(outbox_exists)),
                )
                self.connection.execute("DELETE FROM outbox WHERE thread_id = ?", (thread_id,))
                self.connection.execute("DELETE FROM reply_drafts WHERE thread_id = ?", (thread_id,))
                self.connection.execute("DELETE FROM idempotency_keys WHERE operation_id IN (?, ?)", (f"interactive-draft-{thread_id}", f"interactive-send-{thread_id}"))
                self.connection.execute("UPDATE aggregate_threads SET status = 'WAITING_ANALYSIS', ai_level = NULL, risk_level = NULL, updated_at = datetime('now') WHERE thread_id = ?", (thread_id,))
                rolled += 1
            self.connection.commit()
            self.last_rollback = {"batch_id": batch_id, "rolled_back": rolled, "status": "completed"}
            self.last_batch = None
            self.batch = None
            return {"rolled_back": rolled}

    def retry_failed(self) -> dict[str, Any]:
        with self.lock:
            failed = []
            for case in self._all_cases():
                thread = self._thread(case)
                if thread and thread.get("status") == "FAILED":
                    failed.append(case["key"])
            self.queue.extend(key for key in failed if key not in self.queue)
            if failed and self.agent_enabled:
                self._ensure_worker()
            return {"queued": len(failed)}


MANAGER = StageBManager()


class Handler(BaseHTTPRequestHandler):
    server_version = "ReplyFlowStageB/1.0"

    def _json(self, status: int, payload: Any) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path == "/api/state":
            self._json(HTTPStatus.OK, MANAGER.state())
            return
        path = ROOT / "prototype" / "stage_b" / ("index.html" if urlparse(self.path).path in {"/", ""} else urlparse(self.path).path.lstrip("/"))
        if path.exists() and path.is_file() and ROOT / "prototype" / "stage_b" in path.parents:
            data = path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self._json(HTTPStatus.NOT_FOUND, {"message": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        try:
            path = urlparse(self.path).path
            body = self._body()
            if path == "/api/toggle":
                self._json(HTTPStatus.OK, MANAGER.toggle(bool(body.get("enabled"))))
            elif path == "/api/demo-email":
                self._json(HTTPStatus.OK, {"case": MANAGER.add_case(body), "state": MANAGER.state()})
            elif path == "/api/send":
                self._json(HTTPStatus.OK, {"outbox": MANAGER.send(str(body.get("key")), str(body.get("body", "")), body.get("checklist"))})
            elif path == "/api/rollback":
                self._json(HTTPStatus.OK, {"result": MANAGER.rollback(), "state": MANAGER.state()})
            elif path == "/api/retry":
                self._json(HTTPStatus.OK, {"result": MANAGER.retry_failed(), "state": MANAGER.state()})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"message": "Not found"})
        except ValueError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:  # pragma: no cover
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="ReplyFlow Stage B HTML + Coze bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8511)
    parser.add_argument("--db", type=Path, default=None, help="本地演示 SQLite 路径")
    args = parser.parse_args()
    global MANAGER
    if args.db:
        MANAGER = StageBManager(args.db)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"ReplyFlow Stage B: http://{args.host}:{args.port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
