from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from replyflow.config import load_settings


def render_mode_status() -> None:
    settings = load_settings()
    interactive_status = "已配置" if settings.interactive_mode_configured else "待阶段 11 配置"

    st.sidebar.caption("运行模式")
    st.sidebar.write("Demo Mode：阶段 10 实现，本地规则路由，无模型调用。")
    st.sidebar.write(f"Interactive Mode：{interactive_status}，后续调用 Coze Workflow。")
    st.sidebar.caption("所有数据均为虚构，所有发送均为本地模拟。")


def render_workspace_skeleton() -> None:
    st.set_page_config(page_title="ReplyFlow", layout="wide")
    render_mode_status()

    st.caption("个人独立研究作品 | 模拟数据 | 模拟发送")
    st.title("ReplyFlow 顶部聚合站内信工作台")
    st.info("阶段 3 工程骨架：当前仅验证页面、依赖和配置可以运行；邮件接入、Agent 处理和数据库将在后续阶段实现。")

    with st.expander("演示控制台（模拟邮件接入）", expanded=False):
        st.text_area(
            "邮件正文",
            value="Hi, where is order ORD-1001?",
            disabled=True,
            help="阶段 6 会启用模拟接入；阶段 3 只展示入口位置。",
        )
        st.caption("当前按钮未启用；不会连接真实 Amazon、邮箱或 Coze。")

    folder_col, thread_col, detail_col = st.columns([1.1, 1.5, 2.4], gap="medium")

    with folder_col:
        st.subheader("文件夹")
        st.metric("顶部聚合站内信", "0")
        st.metric("原始收件箱", "0")
        st.metric("本地模拟发件箱", "0")
        st.caption("完整 AI 能力后续只出现在顶部聚合站内信。")

    with thread_col:
        st.subheader("聚合会话")
        st.write("暂无会话。")
        st.caption("阶段 6 后，新邮件会写入收件箱并聚合到这里。")

    with detail_col:
        st.subheader("会话详情")
        st.write("请选择一条聚合站内信查看邮件、AI 草稿、订单事实和 Tool Trace。")
        st.divider()
        st.write("一级：自动处理候选，需通过本地风险网关。")
        st.write("二级：店管点击 AI 回复后确认。")
        st.write("三级：高风险核对后才能模拟发送。")


if __name__ == "__main__":
    render_workspace_skeleton()
