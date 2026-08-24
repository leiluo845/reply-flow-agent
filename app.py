from __future__ import annotations

import hashlib
import html
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
    mode: str | None = None,
    *,
    body: str,
    subject: str,
    sender_name: str,
    sender_email: str,
    source_message_id: str,
    order_context_id: str,
):
    # The page intentionally exposes one AI path: Coze Interactive Mode.
    # Local orchestration still owns facts, risk, confirmation, idempotency
    # and the simulated outbox.
    return InteractiveOrchestrator(connection, CozeClient(settings)).run(
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


def _legacy_render_topbar() -> None:
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


def _legacy_render_order_panel(connection: sqlite3.Connection, thread_id: str | None, email_id: str | None) -> None:
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


def _legacy_render_sidebar(settings: AppSettings, connection: sqlite3.Connection) -> str:
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
def _legacy_render_demo_dialog(connection: sqlite3.Connection, settings: AppSettings, mode: str) -> None:
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


def _legacy_render_demo_console(connection: sqlite3.Connection, settings: AppSettings, mode: str) -> None:
    """Keep the simulator out of the main workbench until the FAB is clicked."""
    if st.button("✉ 模拟收到邮件", key="open_demo_console", help="打开浮窗，创建一封虚构站内信"):
        st.session_state["show_demo_console"] = True
    if st.session_state.get("show_demo_console"):
        _legacy_render_demo_dialog(connection, settings, mode)


def _legacy_render_folder_column(connection: sqlite3.Connection) -> tuple[str | None, str | None]:
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


def _legacy_render_thread_list(connection: sqlite3.Connection) -> None:
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


def _legacy_render_evidence(connection: sqlite3.Connection, artifacts: dict[str, Any]) -> None:
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


def _legacy_render_detail(connection: sqlite3.Connection, settings: AppSettings, mode: str, thread_id: str | None, email_id: str | None) -> None:
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


def _legacy_render_app() -> None:
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


def _ensure_default_demo_thread(connection: sqlite3.Connection) -> None:
    """Seed one visible, order-linked buyer thread for a clean demo database."""
    exists = connection.execute("SELECT 1 FROM aggregate_threads LIMIT 1").fetchone()
    if exists:
        return
    ReplyFlowTools(connection).ingest_simulated_email(
        body="Hi, where is my order? Order number: ORD-1001. The tracking page has not changed since yesterday.",
        subject="Where is my order?",
        sender_name="Maya Stone",
        sender_email="buyer01@example.com",
        source_message_id="UI-DEFAULT-ORD-1001",
        order_context_id="ORD-1001",
    )


def _sync_selection(connection: sqlite3.Connection) -> tuple[str | None, str | None]:
    threads = get_aggregate_inbox(connection)
    if not threads:
        st.session_state["selected_thread_id"] = None
        st.session_state["selected_email_id"] = None
        return None, None
    selected_id = st.session_state.get("selected_thread_id")
    selected = next((item for item in threads if item["thread_id"] == selected_id), threads[0])
    st.session_state["selected_thread_id"] = selected["thread_id"]
    st.session_state["selected_email_id"] = selected["email_id"]
    return selected["thread_id"], selected["email_id"]


def _safe(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def _level_badges(thread: dict[str, Any]) -> str:
    level = thread.get("ai_level")
    risk = thread.get("risk_level")
    status = thread.get("status")
    parts: list[str] = []
    if level:
        parts.append(f"<span class='rf-badge rf-level-{_safe(level.lower())}'>{_safe(level)}</span>")
    if risk:
        parts.append(f"<span class='rf-badge rf-risk'>{_safe(risk)}</span>")
    if level:
        parts.append("<span class='rf-badge rf-ai'>AI回复</span>")
    elif status == "FAILED":
        parts.append("<span class='rf-badge rf-failed'>AI处理失败</span>")
    return "".join(parts)


def _render_original_styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid='stSidebar'] { display: none; }
        [data-testid='stHeader'] { height: 0; background: transparent; }
        [data-testid='stToolbar'] { display: none; }
        [data-testid='stAppViewContainer'] { background: #f5f7fb; }
        .block-container { max-width: none; padding: 0 14px 78px 284px; }
        .rf-oms-nav { position: fixed; z-index: 20; left: 0; top: 0; width: 268px; height: 100vh; overflow: hidden; color: #eef2ff; background: #202f6c; }
        .rf-logo { height: 86px; padding: 18px 22px 12px; border-bottom: 1px solid rgba(255,255,255,.12); }
        .rf-logo-mark { display:inline-flex; width:30px; height:30px; align-items:center; justify-content:center; border:2px solid #fff; transform:rotate(45deg); margin-right:10px; }
        .rf-logo-mark span { transform:rotate(-45deg); font-size:15px; }
        .rf-logo-title { font-size:18px; vertical-align:top; line-height:32px; }
        .rf-logo-sub { display:block; color:#adb9e8; font-size:12px; margin-top:3px; }
        .rf-nav-search { margin:16px 18px; padding:10px 14px; color:#ced8ff; background:#34447e; border-radius:4px; text-align:center; }
        .rf-nav-group { color:#98a7df; font-size:12px; padding:13px 26px 6px; }
        .rf-nav-item { display:flex; justify-content:space-between; padding:12px 24px; color:#e8ecff; font-size:15px; }
        .rf-nav-item.active { margin:0 12px; padding:12px; border-radius:4px; background:#405496; }
        .rf-nav-item .arrow { color:#aeb9e9; }
        .rf-header { height:64px; display:flex; align-items:center; justify-content:space-between; padding:0 8px 0 24px; border-bottom:1px solid #e3e7f0; background:#fff; }
        .rf-header-title { color:#1d2b67; font-size:18px; font-weight:600; border-bottom:3px solid #4558e8; height:64px; padding-top:20px; }
        .rf-header-icons { color:#66708c; font-size:18px; letter-spacing:10px; }
        .rf-header-user { color:#5a6684; letter-spacing:0; }
        .rf-toolbar { margin-top:14px; padding:0 2px; display:flex; gap:8px; flex-wrap:wrap; }
        .rf-control { display:inline-flex; align-items:center; height:38px; padding:0 14px; white-space:nowrap; color:#25314f; border:1px solid #d7ddea; border-radius:4px; background:#fff; font-size:14px; }
        .rf-control.muted { color:#78829b; }
        .rf-control.primary { color:#fff; background:#4b57e8; border-color:#4b57e8; }
        .rf-control.link { color:#4b57e8; border-color:#4b57e8; }
        .rf-toolbar-sub { margin:8px 0 12px; padding:9px 0; color:#63708c; border-bottom:1px solid #dfe4ee; font-size:13px; }
        .rf-toolbar-sub span { margin-right:24px; }
        .rf-panel-title { color:#25314f; font-size:16px; font-weight:600; margin-bottom:10px; }
        .rf-panel-subtitle { color:#8892a8; font-size:12px; margin-bottom:12px; }
        .rf-static-panel { min-height:695px; }
        .rf-folder-item { display:flex; justify-content:space-between; padding:10px 8px; color:#46516c; border-bottom:1px solid #eef1f6; font-size:14px; }
        .rf-folder-item.active { color:#4658ed; background:#edf0ff; border-radius:4px; }
        .rf-count { color:#f04b4b; font-size:12px; }
        .rf-thread-row { padding:12px 10px; border-bottom:1px solid #e9edf4; }
        .rf-thread-row.selected { background:#f0f2ff; border-left:3px solid #4959ec; padding-left:7px; }
        .rf-thread-name { color:#273354; font-size:14px; font-weight:600; }
        .rf-thread-time { float:right; color:#8290aa; font-size:12px; }
        .rf-thread-subject { margin-top:5px; color:#4b5876; font-size:13px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .rf-thread-tags { margin-top:7px; }
        .rf-badge { display:inline-block; margin-right:5px; padding:2px 6px; border-radius:3px; font-size:11px; line-height:16px; }
        .rf-level-l1 { color:#167a54; background:#e4f6ec; }
        .rf-level-l2 { color:#9a6500; background:#fff2d8; }
        .rf-level-l3 { color:#b63432; background:#ffe5e4; }
        .rf-risk { color:#8f5f00; background:#fff4db; }
        .rf-ai { color:#4658df; background:#e9ebff; }
        .rf-failed { color:#b63432; background:#ffe5e4; }
        .rf-detail-head { display:flex; justify-content:space-between; align-items:center; padding-bottom:10px; border-bottom:1px solid #e4e8f1; }
        .rf-detail-subject { color:#25314f; font-size:17px; font-weight:600; }
        .rf-detail-meta { color:#79849c; font-size:12px; margin-top:5px; }
        .rf-mail-bubble { margin:16px 0; padding:14px 16px; color:#24304a; background:#eef1f6; border-radius:5px; font-size:15px; line-height:1.65; }
        .rf-agent-row { display:flex; align-items:center; gap:10px; margin:12px 0; color:#58647e; font-size:12px; }
        .rf-compose-tools { padding:8px 0; color:#5061eb; border-top:1px solid #e7ebf3; font-size:13px; }
        .rf-compose-label { color:#7a859e; font-size:12px; margin:4px 0; }
        .rf-risk-note { margin:8px 0; padding:9px 12px; color:#9a5d00; background:#fff6e1; border:1px solid #f1d99e; border-radius:4px; font-size:12px; }
        .rf-risk-note.high { color:#a63b39; background:#fff0ef; border-color:#efc0be; }
        .rf-order-head { display:flex; justify-content:space-between; align-items:flex-start; color:#3f4dd0; font-size:17px; font-weight:600; }
        .rf-order-tag { display:inline-block; margin:10px 6px 12px 0; padding:4px 8px; color:#bc7417; border:1px solid #e8b66c; border-radius:4px; font-size:11px; }
        .rf-order-table { width:100%; border-collapse:collapse; font-size:13px; }
        .rf-order-table td { padding:8px 0; border-bottom:1px solid #eef1f5; }
        .rf-order-table td:first-child { color:#7a859d; width:44%; }
        .rf-product-card { margin-top:14px; padding:10px; background:#f7f8fb; border:1px solid #e5e9f1; border-radius:4px; }
        .rf-product-name { color:#4a5774; font-size:13px; }
        .rf-product-meta { margin-top:6px; color:#8792a9; font-size:11px; line-height:1.7; }
        .rf-trace { margin-top:14px; padding-top:10px; border-top:1px solid #e6eaf2; color:#7d879b; font-size:11px; line-height:1.8; }
        div.st-key-open_demo_console { position:fixed; z-index:30; left:292px; bottom:22px; }
        div.st-key-open_demo_console button { border-radius:20px; color:#fff; background:#4658df; border-color:#4658df; box-shadow:0 5px 16px rgba(45,58,166,.25); }
        div.st-key-open_demo_console button:hover { color:#fff; background:#3345c9; border-color:#3345c9; }
        @media (max-width: 1100px) { .block-container { padding-left:18px; } .rf-oms-nav { display:none; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_original_chrome() -> None:
    nav_items = [
        ("基础业务", "", False),
        ("设计开发", "›", False), ("产品管理", "›", False), ("主数据", "›", False),
        ("OMS 订单管理", "", False), ("销售订单", "›", False), ("库存管理", "›", False),
        ("调拨管理", "›", False), ("客服邮件", "›", True), ("供应商", "›", False),
    ]
    nav_html = [
        "<div class='rf-oms-nav'><div class='rf-logo'><span class='rf-logo-mark'><span>7</span></span><span class='rf-logo-title'>七星 OMS</span><span class='rf-logo-sub'>子不语数字化平台</span></div>",
        "<div class='rf-nav-search'>⌕　搜索菜单</div>",
    ]
    for label, arrow, active in nav_items:
        if label in {"基础业务", "OMS 订单管理"}:
            nav_html.append(f"<div class='rf-nav-group'>{_safe(label)}</div>")
        else:
            active_class = " active" if active else ""
            nav_html.append(f"<div class='rf-nav-item{active_class}'><span>{_safe(label)}</span><span class='arrow'>{_safe(arrow)}</span></div>")
    nav_html.append("</div>")
    st.markdown("".join(nav_html), unsafe_allow_html=True)
    st.markdown(
        """
        <div class='rf-header'><div class='rf-header-title'>邮件消息</div><div class='rf-header-icons'>文　☷　♧　⛶　☼　 <span class='rf-header-user'>薛　薛杭源</span></div></div>
        <div class='rf-toolbar'>
          <span class='rf-control'>US 君在行Ptaesos-US美国⌄</span><span class='rf-control muted'>□ 仅看未读</span><span class='rf-control'>全部状态⌄</span><span class='rf-control'>发件人⌄</span><span class='rf-control muted' style='min-width:210px'>请输入搜索内容</span><span class='rf-control'>年 / 月 / 日　▣</span><span class='rf-control'>至　年 / 月 / 日　▣</span><span class='rf-control'>不限附件⌄</span><span class='rf-control link'>更多筛选（站内信）　<span class='rf-count'>1</span></span><span class='rf-control primary'>⌕ 搜索</span><span class='rf-control'>↶ 重置</span>
        </div>
        <div class='rf-toolbar-sub'><span>同步时间：2026-07-22 09:48　◉</span><span>□ 收件时间</span><span>最后修改时间⌄</span><span>↓ 降序</span><span>✉ 已读/未读</span><span>⊘ 无需回复</span><span>↗ 已在平台回复</span></div>
        """,
        unsafe_allow_html=True,
    )


def _ensure_thread_with_coze(connection: sqlite3.Connection, settings: AppSettings, thread_id: str) -> dict[str, Any]:
    email = _email_for_thread(connection, thread_id)
    if not email:
        return {"error_code": "EMAIL_NOT_FOUND", "notice": "邮件不存在。"}
    source_row = connection.execute("SELECT source_message_id FROM emails WHERE email_id = ?", (email["email_id"],)).fetchone()
    result = _run_processing(
        connection,
        settings,
        None,
        body=email["body"],
        subject=email["subject"],
        sender_name=email["sender_name"],
        sender_email=email["sender_email"],
        source_message_id=source_row["source_message_id"],
        order_context_id=email.get("order_context_id") or "",
    )
    return result.model_dump() if hasattr(result, "model_dump") else result


def _render_static_folder(connection: sqlite3.Connection) -> None:
    counts = get_inbox_counts(connection)
    st.markdown(
        f"<div class='rf-panel-title'>邮箱列表</div><div class='rf-panel-subtitle'>ptaesos2024@163.com</div>"
        f"<div class='rf-folder-item active'><span>▣　站内信</span><span class='rf-count'>{counts['aggregate_threads']}</span></div>"
        f"<div class='rf-folder-item'><span>⌂　收件箱</span><span class='rf-count'>{counts['raw_inbox']}</span></div>"
        f"<div class='rf-folder-item'><span>➤　发件箱</span><span class='rf-count'>{counts['outbox']}</span></div>"
        f"<div class='rf-folder-item'><span>▤　亚马逊邮件</span><span class='rf-count'>7</span></div>"
        f"<div style='margin-top:22px;color:#8a94aa;font-size:12px'>待处理 {counts['pending_aggregate_threads']} 条</div>",
        unsafe_allow_html=True,
    )


def _render_static_threads(connection: sqlite3.Connection, selected_thread_id: str | None) -> None:
    threads = get_aggregate_inbox(connection)[:8]
    body: list[str] = ["<div class='rf-panel-title'>邮件列表</div><div class='rf-panel-subtitle'>站内信　·　按最后修改时间排序</div>"]
    if not threads:
        body.append("<div class='rf-panel-subtitle'>暂无邮件</div>")
    for item in threads:
        selected = " selected" if item["thread_id"] == selected_thread_id else ""
        level_tags = _level_badges(item)
        level_tags = level_tags or "<span class='rf-badge'>待处理</span>"
        received = _safe(item.get("updated_at", "")[:10])
        body.append(
            f"<div class='rf-thread-row{selected}'><span class='rf-thread-name'>{_safe(item.get('sender_name', 'Demo Buyer'))}</span><span class='rf-thread-time'>{received}</span>"
            f"<div class='rf-thread-subject'>{_safe(item.get('subject', ''))}</div><div class='rf-thread-tags'>{level_tags}</div></div>"
        )
    st.markdown("".join(body), unsafe_allow_html=True)


def _render_static_trace(artifacts: dict[str, Any]) -> None:
    risk = artifacts.get("risk")
    risk_text = "尚未产生风险决策"
    if risk:
        rules = ", ".join(_json_load(risk.get("matched_rules_json"), [])) or "无命中规则"
        risk_text = f"风险 {risk['risk_level']} · 处理级别 {risk['ai_level']} · {rules}"
    traces = artifacts.get("traces", [])
    trace_lines = "<br>".join(f"{_safe(trace['tool_name'])} · {_safe(trace['status'])}" for trace in traces[-5:]) or "暂无 Tool Trace"
    st.markdown(f"<div class='rf-trace'><b>风险与处理依据</b><br>{_safe(risk_text)}<br>{trace_lines}</div>", unsafe_allow_html=True)


def _render_order_panel(connection: sqlite3.Connection, email_id: str | None) -> None:
    email = EmailRepository(connection).get(email_id) if email_id else None
    order = _order_by_id(connection, email.get("order_context_id") if email else None)
    st.markdown("<div class='rf-panel-title'>订单详情</div>", unsafe_allow_html=True)
    if not order:
        st.markdown("<div class='rf-panel-subtitle'>暂无关联订单</div>", unsafe_allow_html=True)
        return
    fulfillment = FULFILLMENT_LABELS.get(order.get("fulfillment_status", ""), order.get("fulfillment_status", "未知"))
    rows = [
        ("订单状态", ORDER_STATUS_LABELS.get(order.get("order_status", ""), order.get("order_status", "未知"))),
        ("履约方式", "FBM"), ("发货仓库", "美国三号仓"), ("物流公司", "UPS"),
        ("物流跟踪号", "1Z9W67Y00392138641"), ("订单金额", f"{order['currency']} {order['amount']}"),
    ]
    row_html = "".join(f"<tr><td>{_safe(label)}</td><td>{_safe(value)}</td></tr>" for label, value in rows)
    events = [dict(row) for row in connection.execute("SELECT * FROM shipping_events WHERE order_id = ? ORDER BY event_time DESC LIMIT 2", (order["order_id"],)).fetchall()]
    event_html = "".join(f"<div>{_safe(event['event_time'][:10])} · {_safe(event['status'])} · {_safe(event['location'])}</div>" for event in events)
    st.markdown(
        f"<div class='rf-order-head'><span>{_safe(order['order_id'])}</span><span style='font-size:12px;color:#5d6b85'>{_safe(fulfillment)}</span></div>"
        f"<span class='rf-order-tag'>Shipped</span><span class='rf-order-tag'>FBM</span>"
        f"<table class='rf-order-table'>{row_html}</table>"
        f"<div class='rf-product-card'><div class='rf-product-name'>{_safe(order['product_name'])}</div><div class='rf-product-meta'>数量：1<br>SKU：{_safe(order['sku'])}<br>买家：{_safe(order['customer_name'])}</div></div>"
        f"<div class='rf-trace'><b>最新物流</b><br>{event_html or '暂无物流事件'}</div>",
        unsafe_allow_html=True,
    )


@st.dialog("模拟收到邮件", width="large")
def _render_new_demo_dialog(settings: AppSettings) -> None:
    connection = get_demo_connection(settings)
    st.caption("仅用于作品演示；不会连接真实 Amazon 或发送真实邮件。")
    orders = _list_orders(connection)
    order_ids = [""] + [item["order_id"] for item in orders]
    selected_order = st.selectbox(
        "关联订单（可选）",
        order_ids,
        key="console_order_select_v2",
        format_func=lambda value: "不关联订单" if not value else _order_label(_order_by_id(connection, value) or {"order_id": value, "product_name": "", "amount": "", "fulfillment_status": ""}),
    )
    chosen_order = _order_by_id(connection, selected_order)
    if chosen_order:
        _render_order_card(chosen_order, compact=True)
    with st.form("simulated_email_form_v2", clear_on_submit=False):
        subject = st.text_input("主题（可选）", key="console_subject_v2", placeholder="Where is my order?")
        body = st.text_area("正文（必填）", key="console_body_v2", height=120, placeholder="例如：My order has not arrived yet.")
        col_a, col_b = st.columns(2)
        with col_a:
            sender_name = st.text_input("模拟发件人", key="console_sender_name_v2", placeholder="Demo Buyer")
        with col_b:
            sender_email = st.text_input("模拟邮箱", key="console_sender_email_v2", placeholder="buyer@example.com")
        submitted = st.form_submit_button("模拟收到邮件", type="primary", use_container_width=True)
    if submitted:
        if not body.strip():
            st.error("正文不能为空。")
            return
        resolved_name = sender_name.strip() or (chosen_order or {}).get("customer_name", "Demo Buyer")
        resolved_email = sender_email.strip() or (chosen_order or {}).get("customer_email", "demo-buyer@example.com")
        agent_enabled = bool(st.session_state.get("agent_enabled_toggle", False))
        result = _receive_simulated_email(
            connection,
            settings,
            None,
            subject=subject,
            body=body,
            sender_name=resolved_name,
            sender_email=resolved_email,
            order_context_id=selected_order,
            receive_only=not agent_enabled,
        )
        st.session_state["selected_thread_id"] = result.get("thread_id")
        st.session_state["selected_email_id"] = result.get("email_id")
        st.session_state["flash_notice"] = result.get("notice") or ("邮件已接收；智能客服未开启。" if not agent_enabled else "AI 处理完成。")
        st.session_state["show_demo_console"] = False
        st.rerun()


def render_demo_console(connection: sqlite3.Connection, settings: AppSettings, mode: str | None = None) -> None:
    if st.button("✉ 模拟邮件台", key="open_demo_console", help="打开浮窗，创建一封虚构站内信"):
        st.session_state["show_demo_console"] = True
    if st.session_state.get("show_demo_console"):
        _render_new_demo_dialog(settings)


def render_detail(connection: sqlite3.Connection, settings: AppSettings, mode: str | None, thread_id: str | None, email_id: str | None) -> None:
    thread = ThreadRepository(connection).get(thread_id) if thread_id else None
    email = _email_for_thread(connection, thread_id) if thread_id else (EmailRepository(connection).get(email_id) if email_id else None)
    if not thread or not email:
        st.markdown("<div class='rf-panel-title'>邮件详情</div><div class='rf-panel-subtitle'>暂无邮件</div>", unsafe_allow_html=True)
        return
    st.markdown(
        f"<div class='rf-detail-head'><div><div class='rf-detail-subject'>{_safe(email['subject'])}</div><div class='rf-detail-meta'>{_safe(email['sender_name'])} · {_safe(email['sender_email'])} · 仅模拟数据</div></div></div>",
        unsafe_allow_html=True,
    )
    previous_enabled = bool(st.session_state.get("_agent_enabled_seen", False))
    agent_enabled = st.toggle("智能客服", key="agent_enabled_toggle", help="开启后，模拟邮件会调用 Coze Agent")
    st.markdown("<div class='rf-agent-row'><span class='rf-badge rf-ai'>AI Agent</span><span>开启后自动分析邮件并按风险级别处理；关闭时仅展示原邮件工作台。</span></div>", unsafe_allow_html=True)
    st.session_state["_agent_enabled_seen"] = agent_enabled
    if agent_enabled and not previous_enabled and thread.get("status") == "WAITING_ANALYSIS":
        result_data = _ensure_thread_with_coze(connection, settings, thread_id)
        st.session_state["flash_notice"] = result_data.get("notice") or ("AI 处理完成。" if not result_data.get("error_code") else "AI 处理失败。")
        st.rerun()
    st.markdown(f"<div class='rf-mail-bubble'><b>{_safe(email['sender_name'])}</b><br>{_safe(email['body'])}</div>", unsafe_allow_html=True)
    artifacts = _thread_artifacts(connection, thread_id)
    thread = artifacts.get("thread") or thread
    draft = artifacts.get("draft")
    if thread.get("status") == "FAILED":
        st.error(f"AI 处理失败：{thread.get('status')}。Coze 未返回可用结果，未生成回复。")
        if st.button(
            "重试 AI",
            key=f"retry_ai_v2_{thread_id}",
            type="primary",
            disabled=not agent_enabled,
            help="重新调用 Coze；不会切换到本地规则或重复写入邮件",
        ):
            result_data = _ensure_thread_with_coze(connection, settings, thread_id)
            st.session_state["flash_notice"] = result_data.get("notice") or ("AI 处理完成。" if not result_data.get("error_code") else "AI 处理失败。")
            st.rerun()
        if not agent_enabled:
            st.caption("请先打开智能客服，再重试 AI。")
    elif not agent_enabled and thread.get("status") == "WAITING_ANALYSIS":
        st.info("智能客服已关闭；当前邮件不会调用 AI，也不会自动回复。")
    if draft:
        level = thread.get("ai_level") or ""
        risk = thread.get("risk_level") or ""
        st.markdown(f"<div class='rf-compose-tools'>AI 生成回复　{_level_badges(thread)}</div>", unsafe_allow_html=True)
        draft_key = f"draft_body_v2_{thread_id}"
        st.session_state.setdefault(draft_key, draft.get("edited_content") or draft.get("agent_content") or "")
        if level == "L1" and thread.get("status") == "AI_REPLIED":
            outbox = artifacts.get("outbox") or {}
            st.markdown(f"<div class='rf-mail-bubble' style='background:#eef0ff'><b>客服 · AI自动回复 · { _safe(risk) }</b><br>{_safe(outbox.get('body') or draft.get('agent_content'))}</div>", unsafe_allow_html=True)
            st.success("L1 低风险：已通过风险网关并写入本地模拟发件箱。")
        else:
            reply_body = st.text_area("回复当前会话", key=draft_key, height=150, label_visibility="collapsed")
            if level == "L2":
                if st.button("AI回复并模拟发送", key=f"send_l2_v2_{thread_id}", type="primary", use_container_width=True):
                    ok, notice = _send_from_detail(connection, thread_id, email, artifacts, reply_body, {})
                    (st.success if ok else st.error)(notice)
                    if ok:
                        st.rerun()
            elif level == "L3":
                st.markdown("<div class='rf-risk-note high'>L3 高风险 · AI生成，需要人工核对后才能发送。</div>", unsafe_allow_html=True)
                checklist = {
                    "verify_facts": st.checkbox("我已核对订单与物流事实", key=f"check_facts_v2_{thread_id}"),
                    "review_customer_text": st.checkbox("我已检查回复中的事实和承诺", key=f"check_draft_v2_{thread_id}"),
                    "confirm_simulated_only": st.checkbox("我确认这里只写入本地模拟发件箱", key=f"check_sim_v2_{thread_id}"),
                }
                if st.button("完成核对并模拟发送", key=f"send_l3_v2_{thread_id}", type="primary", disabled=not can_send(ai_level="L3", checklist=checklist), use_container_width=True):
                    ok, notice = _send_from_detail(connection, thread_id, email, artifacts, reply_body, checklist)
                    (st.success if ok else st.error)(notice)
                    if ok:
                        st.rerun()
    else:
        st.markdown("<div class='rf-compose-tools'>回复当前会话</div>", unsafe_allow_html=True)
        st.text_area("回复当前会话", value="", height=120, disabled=True, label_visibility="collapsed", placeholder="智能客服关闭或尚未生成回复")
    st.markdown("<div class='rf-compose-tools'>文　翻译成英文　　♧ 上传附件　　模拟发送只写入本地 outbox</div>", unsafe_allow_html=True)
    _render_static_trace(artifacts)


def render_app() -> None:
    st.set_page_config(page_title="七星 OMS · 邮件消息", page_icon="✉", layout="wide", initial_sidebar_state="collapsed")
    settings = load_settings()
    connection = get_demo_connection(settings)
    _ensure_default_demo_thread(connection)
    st.session_state.setdefault("selected_thread_id", None)
    st.session_state.setdefault("selected_email_id", None)
    st.session_state.setdefault("show_demo_console", False)
    st.session_state.setdefault("agent_enabled_toggle", False)
    thread_id, email_id = _sync_selection(connection)
    _render_original_styles()
    _render_original_chrome()
    render_demo_console(connection, settings)
    folder_col, list_col, detail_col, order_col = st.columns([1.02, 1.48, 3.55, 1.32], gap="small")
    with folder_col:
        with st.container(border=True):
            _render_static_folder(connection)
    with list_col:
        with st.container(border=True):
            _render_static_threads(connection, thread_id)
    with detail_col:
        with st.container(border=True):
            render_detail(connection, settings, None, thread_id, email_id)
    with order_col:
        with st.container(border=True):
            _render_order_panel(connection, email_id)


if __name__ == "__main__":
    render_app()
