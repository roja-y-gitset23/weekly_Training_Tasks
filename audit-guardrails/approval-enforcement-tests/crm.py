from database import get_db

CRM_DOWN = False   # tests switch this to True to simulate an outage


class CRMDownError(Exception):
    pass


def log_activity(draft_id):
    """Log a SENT email in the mock CRM. Idempotent: calling twice creates one row."""
    if CRM_DOWN:
        raise CRMDownError("Mock CRM is down")
    with get_db() as con:
        d = con.execute("SELECT company, subject, body, run_id, status FROM drafts WHERE id=?",
                        (draft_id,)).fetchone()
        if d is None or d["status"] != "SENT":
            raise ValueError("Only a SENT email can be logged in the CRM")
        sent = con.execute("SELECT sent_at FROM sent_emails WHERE draft_id=?",
                           (draft_id,)).fetchone()
        con.execute(
            "INSERT OR IGNORE INTO crm_activities"
            "(draft_id, prospect, email_subject, body, sent_at, run_id) VALUES (?,?,?,?,?,?)",
            (draft_id, d["company"], d["subject"], d["body"], sent["sent_at"], d["run_id"]))
        con.execute("UPDATE drafts SET crm_logged=1, crm_error=NULL WHERE id=?", (draft_id,))