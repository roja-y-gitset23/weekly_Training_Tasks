from database import get_db


def create_draft(run_id, company, subject, body):
    with get_db() as con:
        cur = con.execute(
            "INSERT INTO drafts(run_id, company, subject, body) VALUES (?,?,?,?)",
            (run_id, company, subject, body))
        return cur.lastrowid


def get_draft(draft_id):
    with get_db() as con:
        row = con.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
        return dict(row) if row else None


def list_drafts():
    with get_db() as con:
        return [dict(r) for r in con.execute("SELECT * FROM drafts ORDER BY id")]


def approve_draft(draft_id, reviewer):
    """Only a DRAFT can be approved. Returns True if it worked."""
    with get_db() as con:
        cur = con.execute(
            "UPDATE drafts SET status='APPROVED', reviewer=? WHERE id=? AND status='DRAFT'",
            (reviewer, draft_id))
        return cur.rowcount == 1


def reject_draft(draft_id, reviewer, reason):
    """Only a DRAFT can be rejected, and a reason is required."""
    if not reason or not reason.strip():
        raise ValueError("A rejection reason is required")
    with get_db() as con:
        cur = con.execute(
            "UPDATE drafts SET status='REJECTED', reviewer=?, reject_reason=? "
            "WHERE id=? AND status='DRAFT'",
            (reviewer, reason, draft_id))
        return cur.rowcount == 1