from replyflow.ui_helpers import build_source_message_id, can_send, status_label


def test_source_message_id_is_stable_and_normalizes_sender() -> None:
    first = build_source_message_id(subject=" Hi ", body="Body", sender_email="Buyer@Example.com", order_context_id=None)
    second = build_source_message_id(subject="Hi", body="Body", sender_email="buyer@example.com", order_context_id="")

    assert first == second
    assert first.startswith("UI-DEMO-")


def test_status_label_has_fallback() -> None:
    assert status_label("WAITING_HIGH_RISK_CHECK") == "三级：待高风险核对"
    assert status_label("AI_REPLIED") == "已模拟回复"
    assert status_label("CUSTOM") == "CUSTOM"


def test_send_gate_requires_all_high_risk_checks() -> None:
    assert can_send(ai_level="L1") is True
    assert can_send(ai_level="L2") is True
    assert can_send(ai_level="L3", checklist={"facts": True, "draft": False}) is False
    assert can_send(ai_level="L3", checklist={"facts": True, "draft": True}) is True
    assert can_send(ai_level=None) is False
