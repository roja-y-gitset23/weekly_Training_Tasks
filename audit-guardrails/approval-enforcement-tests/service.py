import crm
from database import get_db
from sender import send_email


def log_crm_safely(draft_id):
    """Try to log in the CRM. If the CRM is down, remember the failure (crm_logged stays 0)."""
    try:
        crm.log_activity(draft_id)
        return True
    except crm.CRMDownError as e:
        with get_db() as con:
            con.execute("UPDATE drafts SET crm_logged=0, crm_error=? WHERE id=?",
                        (str(e), draft_id))
        return False


def send_and_log(draft_id):
    email_result = send_email(draft_id)      # raises ApprovalError if not approved
    logged = log_crm_safely(draft_id)
    return {"email": email_result, "crm": "logged" if logged else "failed"}