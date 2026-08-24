from __future__ import annotations

import pytest

from replyflow.state_machine import InvalidStateTransition, StateMachine


def test_state_machine_accepts_happy_path_and_records_history() -> None:
    machine = StateMachine()
    for state in (
        "ANALYZING",
        "COLLECTING_FACTS",
        "RETRIEVING_REPLY_BASIS",
        "DRAFTING",
        "RISK_CHECKING",
        "AUTO_REPLYING",
        "SIMULATED_SENT",
        "COMPLETED",
    ):
        machine.transition_to(state)

    assert machine.current_state == "COMPLETED"
    assert machine.history[0] == "WAITING_ANALYSIS"
    assert machine.history[-1] == "COMPLETED"
    assert machine.can_transition_to("COMPLETED") is False


def test_state_machine_requires_routing_state_before_send() -> None:
    machine = StateMachine(current_state="WAITING_HIGH_RISK_CHECK")

    # The state machine permits the legal post-check transition; the checklist
    # and second confirmation are enforced by the later write control.
    machine.transition_to("SIMULATED_SENT")
    assert machine.current_state == "SIMULATED_SENT"

    waiting = StateMachine()
    with pytest.raises(InvalidStateTransition):
        waiting.transition_to("SIMULATED_SENT")


def test_state_machine_rejects_unknown_state() -> None:
    with pytest.raises(ValueError):
        StateMachine(current_state="APPROVAL_QUEUE")
