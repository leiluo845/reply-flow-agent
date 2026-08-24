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

ORDER_STATUS_LABELS = {
    "paid": "已付款",
    "cancelled": "已取消",
    "refunded": "已退款",
}

FULFILLMENT_LABELS = {
    "processing": "处理中",
    "in_transit": "运输中",
    "delivered": "已送达",
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


def _list_orders(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM orders ORDER BY ordered_at DESC, order_id ASC"
    ).fetchall()
    return [dict(row) for row in rows]


def _order_label(order: dict[str, Any]) -> str:
    fulfillment = FULFILLMENT_LABELS.get(order.get("fulfillment_status", ""), order.get("fulfillment_status", "未知"))
    return f"{order['order_id']} · {order['product_name']} · ${order['amount']} · {fulfillment}"


def _order_by_id(connection: sqlite3.Connection, order_id: str | None) -> dict[str, Any] | None:
    if not order_id:
        return None
    row = connection.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    return dict(row) if row else None


def _render_order_card(order: dict[str, Any] | None, *, compact: bool = False) -> None:
    if not order:
        st.info("未关联订单。可在模拟邮件浮窗中选择一条虚构订单。")
        return
    fulfillment = FULFILLMENT_LABELS.get(order.get("fulfillment_status", ""), order.get("fulfillment_status", "未知"))
    payment = ORDER_STATUS_LABELS.get(order.get("payment_status", ""), order.get("payment_status", "未知"))
    if compact:
        st.markdown(
            f"<div class='rf-order-card'><div class='rf-order-head'><b>{order['order_id']}</b><span>{fulfillment}</span></div>"
            f"<div class='rf-order-product'>{order['product_name']}</div><div class='rf-order-meta'>${order['amount']} {order['currency']} · {payment} · {order['sku']}</div></div>",
            unsafe_allow_html=True,
        )
        return
    st.markdown(f"**{order['order_id']}**  ·  `{fulfillment}`")
    st.caption(order["product_name"])
    left, right = st.columns(2)
    left.metric("订单金额", f"{order['currency']} {order['amount']}")
    right.metric("付款状态", payment)
    st.caption(f"SKU：{order['sku']} · 买家：{order['customer_name']} <{order['customer_email']}>")
    st.caption(f"下单：{order['ordered_at'][:10]} · 预计退货截止：{order['return_deadline']}")


def render_topbar() -> None:
    st.markdown("<div class='rf-topbar'><span class='rf-brand'>ReplyFlow</span> <span style='color:#8a90a2;font-size:.82rem'>/ 亚马逊站内信 · Agent 工作台</span></div>", unsafe_allow_html=True)
    col_store, col_status, col_search, col_date, col_action = st.columns([1.15, 1.05, 2.1, 1.1, 0.8])
    with col_store:
        st.selectbox("店铺", ["Demo Store · US", "Demo Store · UK"], key="toolbar_store", label_visibility="collapsed")
    with col_status:
        st.selectbox("状态", ["全部状态", "待回复", "已回复", "高风险核对"], key="toolbar_status", label_visibility="collapsed")
    with col_search:
        st.text_input("搜索", key="toolbar_search", placeholder="搜索主题、买家或订单号", label_visibility="collapsed")
    with col_date:
        st.selectbox("日期", ["最近 30 天", "最近 7 天", "今天"], key="toolbar_date", label_visibility="collapsed")
    with col_action:
        st.button("筛选", key="toolbar_filter", use_container_width=True)


def render_order_panel(connection: sqlite3.Connection, thread_id: str | None, email_id: str | None) -> None:
    st.markdown("<div class='rf-section'>", unsafe_allow_html=True)
    st.markdown("### 订单信息")
    email = EmailRepository(connection).get(email_id) if email_id else None
    order = _order_by_id(connection, email.get("order_context_id") if email else None)
    _render_order_card(order)
    if order:
        events = [dict(row) for row in connection.execute(
            "SELECT * FROM shipping_events WHERE order_id = ? ORDER BY event_time DESC LIMIT 4",
            (order["order_id"],),
        ).fetchall()]
        with st.expander("物流轨迹", expanded=True):
            if events:
                for event in events:
                    st.caption(f"{event['event_time'][:16].replace('T', ' ')} · {event['status']} · {event['location']}")
                    st.write(event["description"])
            else:
                st.caption("暂无物流事件。")
    st.markdown("</div>", unsafe_allow_html=True)


def _receive_simulated_email(
    connection: sqlite3.Connection,
    settings: AppSettings,
    mode: str,
    *,
    subject: str,
    body: str,
    sender_name: str,
    sender_email: str,
    order_context_id: str,
    receive_only: bool,
) -> dict[str, Any]:
    sender = sender_email.strip() or "demo-buyer@example.com"
    source_id = build_source_message_id(
        subject=subject,
        body=body,
        sender_email=sender,
        order_context_id=order_context_id or None,
    )
    if receive_only:
        result = ReplyFlowTools(connection).ingest_simulated_email(
            body=body,
            subject=subject or None,
            sender_name=sender_name or None,
            sender_email=sender,
            source_message_id=source_id,
            order_context_id=order_context_id or None,
        )
        if result["ok"]:
            data = result["data"]
            return {"ok": True, "thread_id": data.get("thread_id"), "email_id": data.get("email_id"), "notice": "邮件已接收；当前未运行 AI。"}
        return {"ok": False, "notice": result["data"]["message"]}
    result = _run_processing(
        connection,
        settings,
        mode,
        body=body,
        subject=subject or "Message from buyer",
        sender_name=sender_name or "Demo Buyer",
        sender_email=sender,
        source_message_id=source_id,
        order_context_id=order_context_id,
    )
    result_data = result.model_dump() if hasattr(result, "model_dump") else result
    return {
        "ok": not bool(result_data.get("error_code")),
        "thread_id": result_data.get("thread_id"),
        "email_id": result_data.get("email_id"),
        "notice": result_data.get("notice") or ("AI 处理完成。" if not result_data.get("error_code") else result_data.get("error_code")),
    }


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
    for key in ("console_subject", "console_body", "console_sender_name", "console_sender_email", "console_order_context", "console_order_select"):
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


def _render_workspace_styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid='stAppViewContainer'] { background: #f5f6fa; }
        [data-testid='stHeader'] { background: #f5f6fa; }
        .block-container { padding-top: 1.15rem; padding-bottom: 5rem; max-width: 1660px; }
        .rf-topbar { background: #fff; border: 1px solid #e7e9f0; border-radius: 6px; padding: 0.55rem 0.8rem 0.15rem; margin-bottom: 0.7rem; }
        .rf-brand { color: #27305f; font-size: 1.05rem; font-weight: 700; letter-spacing: 0; }
        .rf-section { background: #fff; border: 1px solid #e7e9f0; border-radius: 6px; padding: 0.75rem; min-height: 560px; }
        .rf-section h3 { margin: 0 0 0.55rem; color: #252b42; font-size: 0.98rem; }
        .rf-order-card { background: #f8f9fd; border: 1px solid #e2e5f0; border-radius: 5px; padding: 0.65rem; margin: 0.35rem 0 0.6rem; }
        .rf-order-head { display: flex; justify-content: space-between; color: #28336f; font-size: 0.82rem; }
        .rf-order-head span { color: #168a65; font-size: 0.75rem; }
        .rf-order-product { color: #30364b; margin-top: 0.3rem; font-size: 0.86rem; }
        .rf-order-meta { color: #737a90; margin-top: 0.2rem; font-size: 0.74rem; }
        .rf-thread { border-bottom: 1px solid #eef0f5; padding: 0.55rem 0.1rem; }
        .rf-thread-subject { color: #2e3552; font-weight: 600; font-size: 0.84rem; }
        .rf-thread-meta { color: #7d8496; font-size: 0.73rem; margin-top: 0.18rem; }
        div.st-key-open_demo_console button { position: fixed; right: 28px; bottom: 24px; z-index: 1000; border-radius: 22px; box-shadow: 0 5px 18px rgba(37,49,108,.22); background: #3949ab; color: #fff; border: 0; padding: 0.55rem 1.1rem; }
        div.st-key-open_demo_console button:hover { background: #2f3d92; color: #fff; }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.dialog("模拟收到邮件", width="large")
def render_demo_dialog(connection: sqlite3.Connection, settings: AppSettings, mode: str) -> None:
    # Streamlit reruns dialog fragments in a worker thread; never reuse the
    # main page's SQLite connection across that boundary.
    connection = get_demo_connection(settings)
    st.caption("输入一封虚构站内信，观察它进入顶部聚合并经过 AI / 风险处理。不会连接真实 Amazon 或邮箱。")
    orders = _list_orders(connection)
    order_ids = [""] + [item["order_id"] for item in orders]
    selected_order = st.selectbox(
        "关联订单（可选）",
        order_ids,
        key="console_order_select",
        format_func=lambda value: "不关联订单" if not value else _order_label(_order_by_id(connection, value) or {"order_id": value, "product_name": "", "amount": "", "fulfillment_status": ""}),
    )
    chosen_order = _order_by_id(connection, selected_order)
    if chosen_order:
        st.markdown("**已选择订单**")
        _render_order_card(chosen_order, compact=True)
        st.caption("提交时若未填写发件人，将自动使用该订单的虚构买家信息。")
    with st.form("simulated_email_form", clear_on_submit=False):
        subject = st.text_input("主题（可选）", key="console_subject", placeholder="Where is my order?")
        body = st.text_area("正文（必填）", key="console_body", height=120, placeholder="例如：My order has not arrived yet.")
        col_a, col_b = st.columns(2)
        with col_a:
            sender_name = st.text_input("模拟发件人", key="console_sender_name", placeholder="Demo Buyer")
        with col_b:
            sender_email = st.text_input("模拟邮箱", key="console_sender_email", placeholder="buyer@example.com")
        auto_run = st.checkbox("接收后自动运行 AI", value=True, key="console_auto_run")
        receive = st.form_submit_button("模拟收到邮件", type="primary", use_container_width=True)
        receive_only = st.form_submit_button("仅接收不处理", use_container_width=True)
    st.button("清空输入", on_click=clear_console, key="clear_console", use_container_width=True)
    if receive or receive_only:
        if not body.strip():
            st.error("正文不能为空。")
            return
        resolved_name = sender_name.strip() or (chosen_order or {}).get("customer_name", "Demo Buyer")
        resolved_email = sender_email.strip() or (chosen_order or {}).get("customer_email", "demo-buyer@example.com")
        result = _receive_simulated_email(
            connection,
            settings,
            mode,
            subject=subject,
            body=body,
            sender_name=resolved_name,
            sender_email=resolved_email,
            order_context_id=selected_order,
            receive_only=bool(receive_only or not auto_run),
        )
        st.session_state["selected_thread_id"] = result.get("thread_id")
        st.session_state["selected_email_id"] = result.get("email_id")
        st.session_state["flash_notice"] = result.get("notice") or "邮件已接收。"
        st.session_state["show_demo_console"] = False
        st.rerun()


def render_demo_console(connection: sqlite3.Connection, settings: AppSettings, mode: str) -> None:
    """Keep the simulator out of the main workbench until the FAB is clicked."""
    if st.button("✉ 模拟收到邮件", key="open_demo_console", help="打开浮窗，创建一封虚构站内信"):
        st.session_state["show_demo_console"] = True
    if st.session_state.get("show_demo_console"):
        render_demo_dialog(connection, settings, mode)


def render_folder_column(connection: sqlite3.Connection) -> tuple[str | None, str | None]:
    counts = get_inbox_counts(connection)
    st.markdown("### 文件夹")
    st.caption("店铺邮箱")
    st.markdown(f"**顶部聚合站内信**　`{counts['aggregate_threads']}`")
    st.markdown(f"收件箱　`{counts['raw_inbox']}`")
    st.markdown(f"发件箱　`{counts['outbox']}`")
    st.divider()
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


def render_thread_list(connection: sqlite3.Connection) -> None:
    counts = get_inbox_counts(connection)
    st.markdown("### 聚合站内信")
    st.caption(f"全部会话 {counts['aggregate_threads']} · 待回复 {counts['pending_aggregate_threads']}")
    threads = get_aggregate_inbox(connection)
    search = st.session_state.get("toolbar_search", "").strip().lower()
    status_filter = st.session_state.get("toolbar_status", "全部状态")
    status_filter_map = {
        "待回复": {"WAITING_ANALYSIS", "WAITING_USER_CONFIRMATION", "WAITING_HIGH_RISK_CHECK", "FAILED"},
        "已回复": {"AI_REPLIED"},
        "高风险核对": {"WAITING_HIGH_RISK_CHECK"},
    }
    if status_filter in status_filter_map:
        threads = [item for item in threads if item.get("status") in status_filter_map[status_filter]]
    if search:
        threads = [
            item for item in threads
            if search in (item.get("subject", "") + item.get("sender_name", "") + item.get("thread_id", "")).lower()
        ]
    if not threads:
        st.info("暂无匹配会话。可点击右下角“模拟收到邮件”创建。")
        return
    for item in threads:
        status = status_label(item["status"])
        subject = item.get("subject", "")
        sender = item.get("sender_name", "Demo Buyer")
        with st.container(border=False):
            st.markdown(
                f"<div class='rf-thread'><div class='rf-thread-subject'>{subject[:38]}</div><div class='rf-thread-meta'>{sender} · {status}</div></div>",
                unsafe_allow_html=True,
            )
            if st.button("打开会话", key=f"open_thread_{item['thread_id']}", use_container_width=True):
                st.session_state["selected_thread_id"] = item["thread_id"]
                st.session_state["selected_email_id"] = item["email_id"]
                st.rerun()


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
    st.session_state.setdefault("show_demo_console", False)
    _render_workspace_styles()
    render_topbar()
    st.title("顶部聚合站内信")
    st.caption("Demo Store · US　|　虚构数据 · 本地模拟发送 · 店管单角色")
    notice = st.session_state.pop("flash_notice", None)
    if notice:
        st.success(notice)
    render_demo_console(connection, settings, mode)
    folder_col, thread_col, detail_col, order_col = st.columns([1.15, 1.65, 3.65, 2.05], gap="medium")
    with folder_col:
        thread_id, email_id = render_folder_column(connection)
    with thread_col:
        render_thread_list(connection)
    with detail_col:
        render_detail(connection, settings, mode, thread_id, email_id)
    with order_col:
        render_order_panel(connection, thread_id, email_id)


if __name__ == "__main__":
    render_app()
