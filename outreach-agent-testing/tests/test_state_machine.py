import pytest
from app.risk import Risk, RiskPolicyError
from app.state_machine import Draft, InvalidTransition, State, send_draft


def make(risk=Risk.LOW):
    return Draft("a@x.com", "X", "Subj", "Body", risk)


def test_happy_path():
    d, box = make(), []
    d.transition(State.APPROVED, reviewer="r1")
    send_draft(d, outbox=box)
    assert d.state == State.SENT and len(box) == 1
    assert [h[1] for h in d.history] == ["APPROVED", "SENT"]


def test_default_outbox_used():
    d = make()
    d.transition(State.APPROVED, reviewer="r1")
    send_draft(d)
    assert d.state == State.SENT


@pytest.mark.parametrize("start,new", [
    (State.DRAFT, State.SENT),
    (State.REJECTED, State.APPROVED),
    (State.SENT, State.DRAFT),
    (State.SENT, State.REJECTED),
])
def test_invalid_transitions(start, new):
    d = make()
    d.state = start
    with pytest.raises(InvalidTransition):
        d.transition(new, reviewer="r", reason="x")


def test_reject_needs_reason():
    with pytest.raises(InvalidTransition):
        make().transition(State.REJECTED)


def test_reject_with_reason():
    d = make()
    d.transition(State.REJECTED, reviewer="r1", reason="bad fit")
    assert d.state == State.REJECTED and d.reason == "bad fit"


def test_approve_needs_reviewer():
    with pytest.raises(InvalidTransition):
        make().transition(State.APPROVED)


def test_cannot_send_draft():
    with pytest.raises(RiskPolicyError):
        send_draft(make(), outbox=[])


def test_cannot_send_rejected():
    d = make()
    d.transition(State.REJECTED, reason="no")
    with pytest.raises(RiskPolicyError):
        send_draft(d, outbox=[])


def test_high_risk_approved_still_blocked():
    d, box = make(Risk.HIGH), []
    d.transition(State.APPROVED, reviewer="r1")
    with pytest.raises((RiskPolicyError, InvalidTransition)):
        send_draft(d, outbox=box)
    assert box == [] and d.state == State.APPROVED


def test_cannot_send_twice():
    d, box = make(), []
    d.transition(State.APPROVED, reviewer="r1")
    send_draft(d, outbox=box)
    with pytest.raises((RiskPolicyError, InvalidTransition)):
        send_draft(d, outbox=box)
    assert len(box) == 1