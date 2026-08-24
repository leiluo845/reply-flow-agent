from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from replyflow.aggregation import get_aggregate_inbox, get_inbox_counts
from replyflow.coze_client import CozeClient
from replyflow.config import AppSettings, load_settings
from replyflow.db import connect_db, initialize_schema, seed_database
from replyflow.interactive_orchestrator import InteractiveOrchestrator
from replyflow.mcp_tools import ReplyFlowTools
from replyflow.orchestrator import DemoOrchestrator
from replyflow.repositories import EmailRepository, ThreadRepository
from replyflow.ui_helpers import build_source_message_id, can_send, status_label


FOLDER_OPTIONS = {
    "顶部聚合站内信": "aggregate",
    "原始收件箱": "raw",
    "本地模拟发件箱": "outbox",
    "原邮箱站内信": "raw",
    "亚马逊邮件": "raw",
}


def _json_load(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default


def get_demo_connection(settings: AppSettings) -> sqlite3.Connection:
    # Streamlit can run successive reruns in different script threads. Keep
    # SQLite connections request-scoped; schema setup and seed insertion are idempotent.
    connection = connect_db(settings.replyflow_db_path)
    initialize_schema(connection)
    seed_database(connection)
    return connection


def reset_runtime_data(connection: sqlite3.Connection) -> None:
    """Clear demo-generated records while retaining fictional orders and basis."""
    for table in (
        "audit_logs",
        "confirmations",
        "risk_decisions",
        "tool_traces",
        "idempotency_keys",
        "task_runs",
        "outbox",
        "reply_drafts",
        "aggregate_threads",
        "emails",
    ):
        connection.execute(f"DELETE FROM {table}")
    connection.commit()


def _source_id(subject: str, body: str, sender_email: str, order_context_id: str) -> str:
    return build_source_message_id(
        subject=subject,
        body=body,
        sender_email=sender_email,
        order_context_id=order_context_id or None,
    )


def _run_processing(
    connection: sqlite3.Connection,
    settings: AppSettings,
    mode: str,
    *,
    body: str,
    subject: str,
    sender_name: str,
    sender_email: str,
    source_message_id: str,
    order_context_id: str,
):
    if mode == "Interactive Mode":
        return InteractiveOrchestrator(connection, CozeClient(settings)).run(
            body=body,
            subject=subject,
            sender_name=sender_name,
            sender_email=sender_email,
            source_message_id=source_message_id,
            order_context_id=order_context_id or None,
        )
    return DemoOrchestrator(connection).run_demo_email(
        body=body,
        subject=subject,
        sender_name=sender_name,
        sender_email=sender_email,
        source_message_id=source_message_id,
        order_context_id=order_context_id or None,
    )


def _email_for_thread(connection: sqlite3.Connection, thread_id: str) -> dict[str, Any] | None:
    thread = ThreadRepository(connection).get(thread_id)
    if not thread:
        return None
    return EmailRepository(connection).get(thread["email_id"])


def _thread_artifacts(connection: sqlite3.Connection, thread_id: str) -> dict[str, Any]:
    thread = ThreadRepository(connection).get(thread_id)
    if not thread:
        return {}
    draft = connection.execute(
        "SELECT * FROM reply_drafts WHERE thread_id = ? ORDER BY created_at DESC LIMIT 1", (thread_id,)
    ).fetchone()
    task = connection.execute(
        "SELECT * FROM task_runs WHERE thread_id = ? ORDER BY started_at DESC LIMIT 1", (thread_id,)
    ).fetchone()
    risk = None
    traces: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    if task:
        risk = connection.execute(
            "SELECT * FROM risk_decisions WHERE task_id = ? ORDER BY created_at DESC LIMIT 1", (task["task_id"],)
        ).fetchone()
        traces = [dict(row) for row in connection.execute("SELECT * FROM tool_traces WHERE task_id = ? ORDER BY created_at", (task["task_id"],)).fetchall()]
        audits = [dict(row) for row in connection.execute("SELECT * FROM audit_logs WHERE task_id = ? ORDER BY created_at", (task["task_id"],)).fetchall()]
    outbox = connection.execute(
        "SELECT * FROM outbox WHERE thread_id = ? ORDER BY simulated_sent_at DESC LIMIT 1", (thread_id,)
    ).fetchone()
    return {
        "thread": thread,
        "draft": dict(draft) if draft else None,
        "task": dict(task) if task else None,
        "risk": dict(risk) if risk else None,
        "traces": traces,
        "audits": audits,
        "outbox": dict(outbox) if outbox else None,
    }


def _record_confirmation(connection: sqlite3.Connection, task_id: str | None, action: str, checklist: dict[str, bool]) -> None:
    if not task_id:
        return
    connection.execute(
        "INSERT OR IGNORE INTO confirmations(confirmation_id, task_id, action, confirmed_by, confirmed_at, checklist_json) VALUES (?, ?, ?, ?, datetime('now'), ?)",
        (f"CNF-{hashlib.sha256((task_id + action).encode()).hexdigest()[:12].upper()}", task_id, action, "store_operator", json.dumps(checklist, ensure_ascii=False)),
    )
    connection.commit()


def _send_from_detail(connection: sqlite3.Connection, thread_id: str, email: dict[str, Any], artifacts: dict[str, Any], body: str, checklist: dict[str, bool]) -> tuple[bool, str]:
    thread = artifacts["thread"]
    ai_level = thread.get("ai_level")
    risk_level = thread.get("risk_level")
    if not can_send(ai_level=ai_level, checklist=checklist):
        return False, "三级核对清单未完成，不能模拟发送。"
    tools = ReplyFlowTools(connection)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    save = tools.save_reply_draft(
        thread_id=thread_id,
        agent_content=artifacts.get("draft", {}).get("agent_content", body) if artifacts.get("draft") else body,
        edited_content=body,
        ai_level=ai_level,
        risk_level=risk_level,
        confirmed=True,
        operation_id=f"UI-DRAFT-{thread_id}-{digest}",
    )
    if not save["ok"]:
        return False, save["data"]["message"]
    send = tools.send_simulated_reply(
        thread_id=thread_id,
        recipient=email["sender_email"],
        subject=f"Re: {email['subject']}",
        body=body,
        confirmed=True,
        operation_id=f"UI-SEND-{thread_id}-{digest}",
    )
    if not send["ok"]:
        return False, send["data"]["message"]
    ThreadRepository(connection).update_status(thread_id, "AI_REPLIED", ai_level=ai_level, risk_level=risk_level)
    _record_confirmation(connection, artifacts.get("task", {}).get("task_id") if artifacts.get("task") else None, "SIMULATE_SEND", checklist)
    return True, "已写入本地模拟发件箱，未发送到真实邮箱。"


def clear_console() -> None:
    for key in ("console_subject", "console_body", "console_sender_name", "console_sender_email", "console_order_context"):
        st.session_state[key] = ""


def render_sidebar(settings: AppSettings, connection: sqlite3.Connection) -> str:
    st.sidebar.caption("ReplyFlow 演示设置")
    mode = st.sidebar.radio("运行模式", ["Demo Mode", "Interactive Mode"], index=0, key="run_mode")
    if mode == "Interactive Mode" and not settings.interactive_mode_configured:
        st.sidebar.warning("Interactive Mode 未配置 Coze PAT，将无法调用模型。")
    elif mode == "Interactive Mode":
        st.sidebar.success("Interactive Mode 已连接已发布 Workflow。")
    else:
        st.sidebar.info("Demo Mode 使用本地可解释规则，不调用模型。")
    st.sidebar.caption("所有邮件、订单、回复和发送均为虚构/本地模拟。")
    if st.sidebar.button("重置演示数据", key="reset_demo"):
        st.session_state["confirm_reset"] = True
    if st.session_state.get("confirm_reset"):
        st.sidebar.warning("将清空本地演示邮件、草稿、审计和模拟发件箱。")
        if st.sidebar.button("确认重置", key="confirm_reset_button"):
            reset_runtime_data(connection)
            st.session_state["selected_thread_id"] = None
            st.session_state["selected_email_id"] = None
            st.session_state["confirm_reset"] = False
            st.rerun()
    return mode


def render_demo_console(connection: sqlite3.Connection, settings: AppSettings, mode: str) -> None:
    with st.expander("演示控制台（模拟邮件接入）", expanded=True):
        st.caption("输入一封虚构站内信，观察它从原始收件箱进入顶部聚合并经过 AI/风险处理。")
        with st.form("simulated_email_form", clear_on_submit=False):
            subject = st.text_input("主题（可选）", key="console_subject", placeholder="Where is my order?")
            body = st.text_area("正文（必填）", key="console_body", height=100)
            col_a, col_b = st.columns(2)
            with col_a:
                sender_name = st.text_input("模拟发件人", key="console_sender_name", placeholder="Demo Buyer")
            with col_b:
                sender_email = st.text_input("模拟邮箱", key="console_sender_email", placeholder="buyer@example.com")
            order_context = st.text_input("关联模拟订单（可选）", key="console_order_context", placeholder="ORD-1001")
            auto_run = st.checkbox("接收后自动运行 AI", value=True, key="console_auto_run")
            receive = st.form_submit_button("模拟收到邮件", type="primary")
            receive_only = st.form_submit_button("仅接收不处理")
        st.button("清空输入", on_click=clear_console, key="clear_console")
        if receive or receive_only:
            if not body.strip():
                st.error("正文不能为空。")
                return
            sender = sender_email.strip() or "demo-buyer@example.com"
            source_id = build_source_message_id(subject=subject, body=body, sender_email=sender, order_context_id=order_context or None)
            if receive_only or not auto_run:
                result = ReplyFlowTools(connection).ingest_simulated_email(
                    body=body,
                    subject=subject or None,
                    sender_name=sender_name or None,
                    sender_email=sender,
                    source_message_id=source_id,
                    order_context_id=order_context or None,
                )
                if result["ok"]:
                    data = result["data"]
                    st.session_state["selected_thread_id"] = data.get("thread_id")
                    st.session_state["selected_email_id"] = data.get("email_id")
                    st.session_state["flash_notice"] = "邮件已接收；当前未运行 AI。"
                else:
                    st.session_state["flash_notice"] = result["data"]["message"]
            else:
                result = _run_processing(
                    connection, settings, mode,
                    body=body, subject=subject or "Message from buyer",
                    sender_name=sender_name or "Demo Buyer", sender_email=sender,
                    source_message_id=source_id, order_context_id=order_context,
                )
                result_data = result.model_dump() if hasattr(result, "model_dump") else result
                st.session_state["selected_thread_id"] = result_data.get("thread_id")
                st.session_state["selected_email_id"] = result_data.get("email_id")
                st.session_state["flash_notice"] = result_data.get("notice") or ("AI 处理完成。" if not result_data.get("error_code") else result_data.get("error_code"))
            st.rerun()


def render_folder_column(connection: sqlite3.Connection) -> tuple[str | None, str | None]:
    counts = get_inbox_counts(connection)
    st.subheader("文件夹")
    st.metric("顶部聚合站内信", counts["aggregate_threads"])
    st.metric("原始收件箱", counts["raw_inbox"])
    st.metric("本地模拟发件箱", counts["outbox"])
    folder_label = st.radio("查看", list(FOLDER_OPTIONS), key="folder_choice", label_visibility="collapsed")
    folder = FOLDER_OPTIONS[folder_label]
    selected_thread = st.session_state.get("selected_thread_id")
    selected_email = st.session_state.get("selected_email_id")
    if folder == "aggregate":
        threads = get_aggregate_inbox(connection)
        st.caption(f"待处理 {counts['pending_aggregate_threads']} 条")
        if not threads:
            st.info("暂无聚合会话。请在上方控制台模拟收到一封邮件。")
        for thread in threads:
            label = f"{status_label(thread['status'])} · {thread['subject'][:28]}"
            if st.button(label, key=f"thread_{thread['thread_id']}", use_container_width=True):
                st.session_state["selected_thread_id"] = thread["thread_id"]
                st.session_state["selected_email_id"] = thread["email_id"]
                st.rerun()
    elif folder == "outbox":
        rows = [dict(row) for row in connection.execute("SELECT * FROM outbox ORDER BY simulated_sent_at DESC").fetchall()]
        for row in rows:
            st.caption(f"已模拟发送 · {row['subject'][:28]}")
            st.write(row["recipient"])
    else:
        rows = [dict(row) for row in connection.execute("SELECT * FROM emails ORDER BY received_at DESC LIMIT 50").fetchall()]
        for row in rows:
            label = f"{row['status']} · {row['subject'][:24]}"
            if st.button(label, key=f"email_{row['email_id']}", use_container_width=True):
                st.session_state["selected_email_id"] = row["email_id"]
                selected_thread_row = connection.execute("SELECT thread_id FROM aggregate_threads WHERE email_id = ?", (row["email_id"],)).fetchone()
                st.session_state["selected_thread_id"] = selected_thread_row["thread_id"] if selected_thread_row else None
                st.rerun()
    return selected_thread, selected_email


def render_evidence(connection: sqlite3.Connection, artifacts: dict[str, Any]) -> None:
    with st.expander("订单事实、风险与 Tool Trace", expanded=False):
        risk = artifacts.get("risk")
        if risk:
            st.write(f"风险等级：{risk['risk_level']} · 处理级别：{risk['ai_level']}")
            st.write("命中规则：", ", ".join(_json_load(risk.get("matched_rules_json"), [])) or "无")
            checklist = _json_load(risk.get("checklist_json"), {})
            if checklist:
                st.write("核对清单：", "; ".join(checklist.values()))
        else:
            st.caption("尚未产生风险决策。")
        for trace in artifacts.get("traces", []):
            st.caption(f"{trace['tool_name']} · {trace['status']} · trace_id={trace['trace_id']}")
        for audit in artifacts.get("audits", []):
            st.caption(f"{audit['action']} · {audit['after_summary']}")


def render_detail(connection: sqlite3.Connection, settings: AppSettings, mode: str, thread_id: str | None, email_id: str | None) -> None:
    st.subheader("会话详情")
    if thread_id:
        artifacts = _thread_artifacts(connection, thread_id)
        thread = artifacts.get("thread")
        email = _email_for_thread(connection, thread_id)
        if not thread or not email:
            st.info("会话已不存在，请重新选择。")
            return
        st.markdown(f"**{email['subject']}**  ·  `{status_label(thread['status'])}`")
        meta_a, meta_b, meta_c = st.columns(3)
        meta_a.metric("处理级别", thread.get("ai_level") or "待分析")
        meta_b.metric("风险", thread.get("risk_level") or "待分析")
        meta_c.metric("会话 ID", thread_id[-8:])
        st.caption(f"发件人：{email['sender_name']} <{email['sender_email']}> · 仅模拟数据")
        with st.chat_message("user"):
            st.write(email["body"])
        if thread["status"] == "WAITING_ANALYSIS":
            if st.button("运行 AI 处理", type="primary", key=f"process_{thread_id}"):
                source_row = connection.execute("SELECT source_message_id FROM emails WHERE email_id = ?", (email["email_id"],)).fetchone()
                result = _run_processing(connection, settings, mode, body=email["body"], subject=email["subject"], sender_name=email["sender_name"], sender_email=email["sender_email"], source_message_id=source_row["source_message_id"], order_context_id=email.get("order_context_id") or "")
                result_data = result.model_dump() if hasattr(result, "model_dump") else result
                st.session_state["flash_notice"] = result_data.get("notice") or ("AI 处理完成。" if not result_data.get("error_code") else result_data.get("error_code"))
                st.rerun()
        draft = artifacts.get("draft")
        if draft:
            draft_key = f"draft_body_{thread_id}"
            st.session_state.setdefault(draft_key, draft.get("edited_content") or draft.get("agent_content") or "")
            st.markdown("#### AI 回复草稿")
            editable = thread.get("ai_level") in {"L2", "L3"}
            body = st.text_area("回复内容", key=draft_key, height=170, disabled=not editable)
            if thread.get("status") == "AI_REPLIED":
                st.success("已写入本地模拟发件箱，当前会话不会重复发送。")
            elif thread.get("ai_level") == "L1":
                st.success("一级低风险：已通过本地风险网关并写入模拟发件箱。")
            elif thread.get("ai_level") == "L2":
                if st.button("确认并模拟发送", key=f"send_l2_{thread_id}", type="primary"):
                    ok, notice = _send_from_detail(connection, thread_id, email, artifacts, body, {})
                    (st.success if ok else st.error)(notice)
                    if ok:
                        st.session_state["flash_notice"] = notice
                        st.rerun()
            elif thread.get("ai_level") == "L3":
                st.warning("三级高风险：仅生成参考回复，发送前必须完成全部核对。")
                checklist = {
                    "verify_facts": st.checkbox("我已核对订单与物流事实", key=f"check_facts_{thread_id}"),
                    "review_customer_text": st.checkbox("我已检查回复中的事实和承诺", key=f"check_draft_{thread_id}"),
                    "confirm_simulated_only": st.checkbox("我确认这里只写入本地模拟发件箱", key=f"check_sim_{thread_id}"),
                }
                if st.button("完成核对并模拟发送", key=f"send_l3_{thread_id}", type="primary", disabled=not can_send(ai_level="L3", checklist=checklist)):
                    ok, notice = _send_from_detail(connection, thread_id, email, artifacts, body, checklist)
                    (st.success if ok else st.error)(notice)
                    if ok:
                        st.session_state["flash_notice"] = notice
                        st.rerun()
        elif thread["status"] == "FAILED":
            st.error("AI 处理失败。可切换 Demo Mode 或点击重试，不会伪造草稿。")
        render_evidence(connection, artifacts)
    elif email_id:
        email = EmailRepository(connection).get(email_id)
        if email:
            st.markdown(f"**{email['subject']}**  ·  `{status_label(email['status'])}`")
            st.caption(f"原始收件箱邮件 · {email['sender_email']}")
            st.write(email["body"])
            if email["status"] == "NOT_BUYER_MESSAGE":
                st.info("这封邮件保留在原始收件箱，不进入客服回复流程。")
    else:
        st.info("请选择一条顶部聚合站内信，或在上方控制台模拟收到邮件。")


def render_app() -> None:
    st.set_page_config(page_title="ReplyFlow · 聚合站内信工作台", page_icon="✉", layout="wide")
    settings = load_settings()
    connection = get_demo_connection(settings)
    mode = render_sidebar(settings, connection)
    st.session_state.setdefault("selected_thread_id", None)
    st.session_state.setdefault("selected_email_id", None)
    st.title("ReplyFlow · 顶部聚合站内信工作台")
    st.caption("个人作品演示 · 虚构数据 · 本地模拟发送 · 店管单角色")
    notice = st.session_state.pop("flash_notice", None)
    if notice:
        st.success(notice)
    render_demo_console(connection, settings, mode)
    folder_col, thread_col, detail_col = st.columns([1.05, 1.55, 3.4], gap="medium")
    with folder_col:
        thread_id, email_id = render_folder_column(connection)
    with thread_col:
        st.subheader("聚合会话")
        counts = get_inbox_counts(connection)
        st.caption(f"顶部聚合 {counts['aggregate_threads']} · 待处理 {counts['pending_aggregate_threads']}")
        if not counts["aggregate_threads"]:
            st.info("新邮件会在这里置顶。")
        else:
            for item in get_aggregate_inbox(connection):
                st.write(f"{status_label(item['status'])}")
                st.caption(item["subject"])
    with detail_col:
        render_detail(connection, settings, mode, thread_id, email_id)


if __name__ == "__main__":
    render_app()
