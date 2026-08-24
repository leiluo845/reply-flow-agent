from __future__ import annotations

from dataclasses import dataclass, field


class InvalidStateTransition(ValueError):
    def __init__(self, current: str, target: str):
        super().__init__(f"Invalid ReplyFlow state transition: {current} -> {target}")
        self.current = current
        self.target = target


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "RECEIVING": {"RECEIVED", "FAILED"},
    "RECEIVED": {"WRITTEN_TO_INBOX", "FAILED"},
    "WRITTEN_TO_INBOX": {"CLASSIFYING_SOURCE", "FAILED"},
    "CLASSIFYING_SOURCE": {"AGGREGATED_AS_STATION_MESSAGE", "NOT_BUYER_MESSAGE", "FAILED"},
    "AGGREGATED_AS_STATION_MESSAGE": {"WAITING_ANALYSIS", "ANALYZING", "FAILED"},
    "WAITING_ANALYSIS": {"ANALYZING", "FAILED"},
    "ANALYZING": {"COLLECTING_FACTS", "WAITING_USER_INFO", "FAILED"},
    "WAITING_USER_INFO": {"RETRIEVING_REPLY_BASIS", "RISK_CHECKING", "FAILED"},
    "COLLECTING_FACTS": {"RETRIEVING_REPLY_BASIS", "RISK_CHECKING", "FAILED"},
    "RETRIEVING_REPLY_BASIS": {"DRAFTING", "RISK_CHECKING", "FAILED"},
    "DRAFTING": {"RISK_CHECKING", "FAILED"},
    "RISK_CHECKING": {"AUTO_REPLYING", "DRAFT_SAVED", "WAITING_USER_CONFIRMATION", "WAITING_HIGH_RISK_CHECK", "FAILED"},
    "AUTO_REPLYING": {"SIMULATED_SENT", "FAILED"},
    "DRAFT_SAVED": {"WAITING_USER_CONFIRMATION", "WAITING_HIGH_RISK_CHECK", "FAILED"},
    "WAITING_USER_CONFIRMATION": {"SIMULATED_SENT", "FAILED"},
    "WAITING_HIGH_RISK_CHECK": {"SIMULATED_SENT", "FAILED"},
    "SIMULATED_SENT": {"COMPLETED", "FAILED"},
    "NOT_BUYER_MESSAGE": {"COMPLETED"},
    "COMPLETED": set(),
    "FAILED": set(),
}


@dataclass
class StateMachine:
    current_state: str = "WAITING_ANALYSIS"
    history: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.current_state not in ALLOWED_TRANSITIONS:
            raise ValueError(f"Unknown ReplyFlow state: {self.current_state}")
        if not self.history:
            self.history.append(self.current_state)

    def can_transition_to(self, target: str) -> bool:
        return target in ALLOWED_TRANSITIONS[self.current_state]

    def transition_to(self, target: str) -> str:
        if not self.can_transition_to(target):
            raise InvalidStateTransition(self.current_state, target)
        self.current_state = target
        self.history.append(target)
        return target

    def fail(self) -> str:
        if self.current_state == "FAILED":
            return self.current_state
        return self.transition_to("FAILED")
