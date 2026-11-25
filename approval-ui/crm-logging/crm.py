import os
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def audit(conn, run_id, step, prospect_id=None, actor=None, detail=None):
    conn.execute(
        """INSERT INTO audit_trail (run_id, step, prospect_id, actor, detail, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (run_id, step, prospect_id, actor, detail, now()),
    )


def mock_send(run_id, company, subject, body):
    """Mock sender: appends the email to a file instead of really sending it."""
    path = os.environ.get("SENT_LOG", "sent_emails.log")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[MOCK SEND] run_id={run_id} to={company}\n")
        f.write(f"Subject: {subject}\n\n{body}\n")
        f.write("-" * 40 + "\n")


def send_and_log(conn, draft_id, actor="system"):
    """Send an APPROVED draft and log it in the CRM. Safe to call many times."""
    d = conn.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
    if not d:
        raise ValueError("Draft not found")
    if d["status"] == "SENT":
        return "already_sent"  # idempotent: no second send, no second row
    if d["status"] != "APPROVED":
        raise PermissionError(f"Cannot send: status is {d['status']}, must be APPROVED")

    prospect_id = d["prospect_id"] or d["id"]
    mock_send(d["run_id"], d["company"], d["subject"], d["body"])
    t = now()
    conn.execute(
        """INSERT OR IGNORE INTO crm_activities
           (prospect_id, email_subject, body, sent_at, run_id)
           VALUES (?, ?, ?, ?, ?)""",
        (prospect_id, d["subject"], d["body"], t, d["run_id"]),
    )
    conn.execute("UPDATE drafts SET status='SENT', updated_at=? WHERE id=?", (t, draft_id))
    audit(conn, d["run_id"], "SENT_AND_LOGGED_TO_CRM", prospect_id, actor,
          f"Mock email sent and CRM row logged: {d['subject']}")
    return "sent"