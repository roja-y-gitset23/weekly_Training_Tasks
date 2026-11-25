import csv
import io
import os
import re
import time

from config import (MAX_ROWS, PITCH, RATE_LIMIT_RUNS, RATE_LIMIT_WINDOW, REQUIRED_COLS)
from database import db

EMAIL_OK = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")
EMAIL_FIND = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


# ---------------------------------------------------------------- rate limit
def rate_limit_check(user_id):
    """Returns (allowed, count). Per-user, sliding window."""
    con = db()
    since = time.time() - RATE_LIMIT_WINDOW
    n = con.execute("SELECT COUNT(*) FROM run_requests WHERE user_id=? AND ts>?",
                    (user_id, since)).fetchone()[0]
    if n >= RATE_LIMIT_RUNS:
        con.close()
        return False, n
    con.execute("INSERT INTO run_requests(user_id, ts) VALUES (?,?)", (user_id, time.time()))
    con.commit()
    con.close()
    return True, n + 1


# --------------------------------------------------------------- input guard
def input_guard(path):
    """Valid CSV only. Returns (True, rows) or (False, reason)."""
    if not path.lower().endswith(".csv"):
        return False, "not a .csv file"
    if not os.path.isfile(path):
        return False, "file not found"
    if os.path.getsize(path) > 1_000_000:
        return False, "file too large (>1 MB)"
    with open(path, "rb") as f:
        raw = f.read()
    if b"\x00" in raw:
        return False, "binary content, not a text CSV"
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False, "not valid UTF-8 text"
    try:
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []
        rows = list(reader)
    except csv.Error as e:
        return False, f"CSV parse error: {e}"

    missing = [c for c in REQUIRED_COLS if c not in headers]
    if missing:
        return False, f"missing required columns: {missing}"
    if not rows:
        return False, "no data rows"
    if len(rows) > MAX_ROWS:
        return False, f"too many rows (max {MAX_ROWS})"
    for i, r in enumerate(rows, start=2):
        if any(not (r.get(c) or "").strip() for c in REQUIRED_COLS):
            return False, f"row {i}: empty required field"
        if not EMAIL_OK.match(r["email"].strip()):
            return False, f"row {i}: invalid email '{r['email']}'"
    return True, rows


# ---------------------------------------------------------- injection guard
INJECTION_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts?)",
    r"disregard (all |any )?(the )?(previous|prior|above|your)",
    r"(reveal|print|show|leak) (your |the )?(system )?(prompt|instructions|api key|secret)",
    r"you are now",
    r"new instructions",
    r"system\s*:",
    r"(send|email|forward) .{0,60}(database|customer data|credentials|api key|password)",
]


def injection_guard(text):
    """Research text is untrusted DATA. Returns the matched attack phrase, or None."""
    for p in INJECTION_PATTERNS:
        m = re.search(p, text, re.I)
        if m:
            return m.group(0)
    return None


# -------------------------------------------------------------- output guard
PII_PATTERNS = {
    "phone number": r"\+?\d[\d\s().-]{8,}\d",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "street address": r"\b\d{1,5}\s+\w+(\s\w+)?\s(street|st|road|rd|avenue|ave|lane|ln|drive|dr)\b",
}
PERSONAL_DOMAINS = ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "proton.me")
BANNED_CLAIMS = ["guarantee", "#1", "number one", "best in the world", "100%", "risk-free", "proven to"]


def output_guard(text, row, notes):
    """No PII beyond name + business email, and no claims unsupported by the research notes.
    Returns a list of problems (empty list = passed)."""
    problems = []
    for name, pat in PII_PATTERNS.items():
        if re.search(pat, text, re.I):
            problems.append(f"PII: {name}")
    for e in EMAIL_FIND.findall(text):
        if e.lower() != row["email"].lower():
            problems.append(f"PII: extra email {e}")
        if e.lower().endswith(PERSONAL_DOMAINS):
            problems.append(f"PII: personal email {e}")
    low = text.lower()
    for phrase in BANNED_CLAIMS:
        if phrase in low:
            problems.append(f"unsupported claim: '{phrase}'")
    support = notes + " " + PITCH
    bad_nums = sorted({n for n in re.findall(r"\d+(?:[.,]\d+)?%?", text) if n not in support})
    if bad_nums:
        problems.append(f"unsupported numbers not in research: {bad_nums}")
    return problems