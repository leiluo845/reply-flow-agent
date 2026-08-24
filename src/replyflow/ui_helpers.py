from __future__ import annotations

import hashlib


STATUS_LABELS = {
    "WAITING_ANALYSIS": "待 AI 处理",
    "AI_ANALYZING": "AI 分析中",
    "COLLECTING_FACTS": "核验订单事实",
    "RETRIEVING_REPLY_BASIS": "检索回复依据",
    "DRAFTING": "生成回复草稿",
    "RISK_CHECKING": "风险复核中",
    "DRAFT_SAVED": "草稿待确认",
    "WAITING_USER_CONFIRMATION": "二级：待店管确认",
    "WAITING_HIGH_RISK_CHECK": "三级：待高风险核对",
    "AI_REPLIED": "已模拟回复",
    "SIMULATED_SENT": "已写入模拟发件箱",
    "NOT_BUYER_MESSAGE": "原始收件箱保留",
    "FAILED": "处理失败",
}


def build_source_message_id(*, subject: str, body: str, sender_email: str, order_context_id: str | None) -> str:
    """Make repeated clicks on the same demo input idempotent across reruns."""
    payload = "\x1f".join((subject.strip(), body.strip(), sender_email.strip().lower(), (order_context_id or "").strip()))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16].upper()
    return f"UI-DEMO-{digest}"


def status_label(status: str | None) -> str:
    return STATUS_LABELS.get(status or "", status or "未知状态")


def can_send(*, ai_level: str | None, checklist: dict[str, bool] | None = None) -> bool:
    """UI gate; Tool layer still requires confirmed=true and operation_id."""
    if ai_level == "L1":
        return True
    if ai_level == "L2":
        return True
    if ai_level == "L3":
        return bool(checklist) and all(checklist.values())
    return False
