from datetime import datetime, timezone
from database import get_db


class ApprovalError(Exception):
    """Raised when someone tries to send a draft that is not APPROVED."""


def send_email(draft_id):
    """The ONLY function that sends an email (mock sender: writes to sent_emails).

    Rules inside this function:
      1. Draft must exist and be APPROVED, otherwise ApprovalError.
      2. If it is already SENT, do nothing (no duplicate).
      3. Claim the draft (APPROVED -> SENT) and record the email in ONE transaction.
    Returns 'sent' or 'already_sent'.
    """
    with get_db() as con:
        row = con.execute("SELECT status, run_id, subject, body FROM drafts WHERE id=?",
                          (draft_id,)).fetchone()
        if row is None:
            raise ApprovalError(f"Draft {draft_id} does not exist")
        if row["status"] == "SENT":
            return "already_sent"
        if row["status"] != "APPROVED":
            raise ApprovalError(f"Draft {draft_id} is {row['status']}, not APPROVED")

        claimed = con.execute(
            "UPDATE drafts SET status='SENT' WHERE id=? AND status='APPROVED'", (draft_id,))
        if claimed.rowcount != 1:
            return "already_sent"

        con.execute(
            "INSERT INTO sent_emails(draft_id, run_id, subject, body, sent_at) VALUES (?,?,?,?,?)",
            (draft_id, row["run_id"], row["subject"], row["body"],
             datetime.now(timezone.utc).isoformat(timespec="seconds")))
    return "sent"