import re
from enum import Enum


class Risk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RiskPolicyError(Exception):
    pass


INJECTION = [r"ignore (all )?(previous|prior) instructions", r"system prompt"]
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
UNSUPPORTED = ["guarantee", "100%", "risk-free", "best in the world"]
MEDIUM_WORDS = ["discount", "pricing", "$"]


def assess_risk(subject, body):
    text = f"{subject}\n{body}"
    low = text.lower()
    if (any(re.search(p, low) for p in INJECTION) or SSN.search(text)
            or PHONE.search(text) or any(w in low for w in UNSUPPORTED)):
        return Risk.HIGH
    if len(body.split()) > 150 or any(w in low for w in MEDIUM_WORDS):
        return Risk.MEDIUM
    return Risk.LOW


def enforce_risk(risk, state, reviewer):
    """Raise RiskPolicyError unless this draft may be sent."""
    if risk == Risk.HIGH:
        raise RiskPolicyError("HIGH risk drafts are blocked")
    if state != "APPROVED":
        raise RiskPolicyError(f"Draft is {state}, not APPROVED")
    if risk == Risk.MEDIUM and not reviewer:
        raise RiskPolicyError("MEDIUM risk needs a named reviewer")