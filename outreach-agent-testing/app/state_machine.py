from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from .risk import Risk, enforce_risk


class State(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SENT = "SENT"


ALLOWED = {
    State.DRAFT: {State.APPROVED, State.REJECTED},
    State.APPROVED: {State.SENT, State.REJECTED},
    State.REJECTED: set(),
    State.SENT: set(),
}


class InvalidTransition(Exception):
    pass


@dataclass
class Draft:
    prospect_email: str
    company: str
    subject: str
    body: str
    risk: Risk
    state: State = State.DRAFT
    reviewer: Optional[str] = None
    reason: Optional[str] = None
    edited: bool = False
    history: list = field(default_factory=list)

    def transition(self, new, reviewer=None, reason=None):
        if new not in ALLOWED[self.state]:
            raise InvalidTransition(f"{self.state.value} -> {new.value} not allowed")
        if new == State.APPROVED and not reviewer:
            raise InvalidTransition("Approval needs a reviewer")
        if new == State.REJECTED and not reason:
            raise InvalidTransition("Rejection needs a reason")
        self.history.append(
            (self.state.value, new.value, datetime.now(timezone.utc).isoformat())
        )
        self.state = new
        if reviewer:
            self.reviewer = reviewer
        if reason:
            self.reason = reason


OUTBOX = []


def send_draft(draft, outbox=None):
    """Mock sender. Only APPROVED, non-HIGH-risk drafts get through."""
    enforce_risk(draft.risk, draft.state, draft.reviewer)
    draft.transition(State.SENT)
    target = OUTBOX if outbox is None else outbox
    target.append({"to": draft.prospect_email, "subject": draft.subject})