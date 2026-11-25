import pytest
from app.risk import Risk, RiskPolicyError, assess_risk, enforce_risk


def test_low():
    assert assess_risk("Hello", "Short friendly note.") == Risk.LOW


@pytest.mark.parametrize("body", [
    "We guarantee results", "Get 100% savings", "Ignore previous instructions",
    "Call 555-123-4567", "SSN 123-45-6789",
])
def test_high(body):
    assert assess_risk("Hi", body) == Risk.HIGH


def test_medium_keyword():
    assert assess_risk("Hi", "Ask about our discount") == Risk.MEDIUM


def test_medium_long_body():
    assert assess_risk("Hi", "word " * 200) == Risk.MEDIUM


def test_high_blocked_even_if_approved():
    with pytest.raises(RiskPolicyError):
        enforce_risk(Risk.HIGH, "APPROVED", "rev")


def test_not_approved_blocked():
    with pytest.raises(RiskPolicyError):
        enforce_risk(Risk.LOW, "DRAFT", None)


def test_medium_needs_reviewer():
    with pytest.raises(RiskPolicyError):
        enforce_risk(Risk.MEDIUM, "APPROVED", None)


def test_allowed_cases():
    enforce_risk(Risk.LOW, "APPROVED", "rev")
    enforce_risk(Risk.MEDIUM, "APPROVED", "rev")