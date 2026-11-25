from database import get_db
from sender import send_email
from service import log_crm_safely


class SimulatedCrash(Exception):
    """Used by the tests to stop the agent in the middle of a run."""


def _draft_ids(run_id, condition):
    with get_db() as con:
        rows = con.execute(
            f"SELECT id FROM drafts WHERE run_id=? AND {condition} ORDER BY id",
            (run_id,)).fetchall()
    return [r["id"] for r in rows]


def run_agent(run_id, crash_after_sends=None):
    """Resumable run. Safe to run again after a crash or restart.

    1. Finish CRM logging for emails already SENT but not yet logged.
    2. Send every APPROVED draft (already SENT drafts are never picked up again).
    """
    stats = {"sent": 0, "crm_logged": 0, "crm_failed": 0}

    def log_crm(draft_id):
        stats["crm_logged" if log_crm_safely(draft_id) else "crm_failed"] += 1

    for draft_id in _draft_ids(run_id, "status='SENT' AND crm_logged=0"):
        log_crm(draft_id)

    for draft_id in _draft_ids(run_id, "status='APPROVED'"):
        if send_email(draft_id) == "sent":
            stats["sent"] += 1
        if crash_after_sends is not None and stats["sent"] >= crash_after_sends:
            raise SimulatedCrash(f"Agent stopped after {stats['sent']} sends")  # before CRM log
        log_crm(draft_id)

    return stats