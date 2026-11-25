from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from crm import audit, send_and_log
from db import get_conn, init_db

app = FastAPI(title="Draft Approval UI")
init_db()

VALID_STATUS = {"DRAFT", "APPROVED", "REJECTED", "SENT"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def db():
    conn = get_conn()
    try:
        with conn:  # commit on success, rollback on error
            yield conn
    finally:
        conn.close()


class ApproveIn(BaseModel):
    reviewer: str = Field(min_length=1)


class EditApproveIn(ApproveIn):
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)


class RejectIn(ApproveIn):
    reason: str = Field(min_length=3)


def get_draft_for_decision(conn, draft_id):
    row = conn.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Draft not found")
    if row["status"] != "DRAFT":
        raise HTTPException(409, f"Draft is already {row['status']}")
    return row


def clean(text, field):
    text = text.strip()
    if not text:
        raise HTTPException(422, f"{field} cannot be empty")
    return text


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/drafts")
def list_drafts(status: str = "DRAFT"):
    status = status.upper()
    if status not in VALID_STATUS:
        raise HTTPException(400, "Invalid status")
    with db() as conn:
        rows = conn.execute(
            """
            SELECT d.*,
              (SELECT reviewer   FROM draft_decisions x WHERE x.draft_id=d.id ORDER BY x.id DESC LIMIT 1) AS reviewer,
              (SELECT reason     FROM draft_decisions x WHERE x.draft_id=d.id ORDER BY x.id DESC LIMIT 1) AS reason,
              (SELECT decided_at FROM draft_decisions x WHERE x.draft_id=d.id ORDER BY x.id DESC LIMIT 1) AS decided_at
            FROM drafts d WHERE d.status=? ORDER BY d.id
            """,
            (status,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/drafts/{draft_id}/approve")
def approve(draft_id: int, data: ApproveIn):
    reviewer = clean(data.reviewer, "Reviewer")
    with db() as conn:
        existing = conn.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Draft not found")
        # Idempotent: approving twice does nothing the second time
        if existing["status"] in ("APPROVED", "SENT"):
            return {"id": draft_id, "status": existing["status"],
                    "note": "already approved - no duplicate send or CRM row"}
        d = get_draft_for_decision(conn, draft_id)  # 409 if REJECTED
        t = now()
        conn.execute("UPDATE drafts SET status='APPROVED', updated_at=? WHERE id=?", (t, draft_id))
        conn.execute(
            """INSERT INTO draft_decisions
               (draft_id, decision, reviewer, reason, decided_at,
                original_subject, original_body, final_subject, final_body)
               VALUES (?, 'APPROVED', ?, NULL, ?, ?, ?, ?, ?)""",
            (draft_id, reviewer, t, d["subject"], d["body"], d["subject"], d["body"]),
        )
        audit(conn, d["run_id"], "APPROVED", d["prospect_id"] or d["id"], reviewer, "approved as drafted")
        result = send_and_log(conn, draft_id, reviewer)
    return {"id": draft_id, "status": "SENT", "result": result}


@app.post("/drafts/{draft_id}/edit-approve")
def edit_and_approve(draft_id: int, data: EditApproveIn):
    reviewer = clean(data.reviewer, "Reviewer")
    subject = clean(data.subject, "Subject")
    body = clean(data.body, "Body")
    with db() as conn:
        d = get_draft_for_decision(conn, draft_id)
        t = now()
        conn.execute(
            "UPDATE drafts SET subject=?, body=?, status='APPROVED', updated_at=? WHERE id=?",
            (subject, body, t, draft_id),
        )
        conn.execute(
            """INSERT INTO draft_decisions
               (draft_id, decision, reviewer, reason, decided_at,
                original_subject, original_body, final_subject, final_body)
               VALUES (?, 'EDITED_APPROVED', ?, NULL, ?, ?, ?, ?, ?)""",
            (draft_id, reviewer, t, d["subject"], d["body"], subject, body),
        )
        audit(conn, d["run_id"], "EDITED_APPROVED", d["prospect_id"] or d["id"], reviewer, "body edited before approval")
        result = send_and_log(conn, draft_id, reviewer)
    return {"id": draft_id, "status": "SENT", "result": result}


@app.post("/drafts/{draft_id}/reject")
def reject(draft_id: int, data: RejectIn):
    reviewer = clean(data.reviewer, "Reviewer")
    reason = clean(data.reason, "Reason")
    with db() as conn:
        d = get_draft_for_decision(conn, draft_id)
        t = now()
        conn.execute("UPDATE drafts SET status='REJECTED', updated_at=? WHERE id=?", (t, draft_id))
        conn.execute(
            """INSERT INTO draft_decisions
               (draft_id, decision, reviewer, reason, decided_at,
                original_subject, original_body, final_subject, final_body)
               VALUES (?, 'REJECTED', ?, ?, ?, ?, ?, ?, ?)""",
            (draft_id, reviewer, reason, t, d["subject"], d["body"], d["subject"], d["body"]),
        )
        audit(conn, d["run_id"], "REJECTED", d["prospect_id"] or d["id"], reviewer, reason)
    return {"id": draft_id, "status": "REJECTED"}


@app.post("/drafts/{draft_id}/send")
def send(draft_id: int):
    """Manual send. Idempotent, and only works for APPROVED drafts."""
    with db() as conn:
        try:
            result = send_and_log(conn, draft_id)
        except ValueError as e:
            raise HTTPException(404, str(e))
        except PermissionError as e:
            raise HTTPException(409, str(e))
    return {"id": draft_id, "status": "SENT", "result": result}


@app.get("/decisions")
def decisions():
    with db() as conn:
        rows = conn.execute("SELECT * FROM draft_decisions ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.get("/crm")
def crm_rows():
    with db() as conn:
        rows = conn.execute("SELECT * FROM crm_activities ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.get("/audit")
def audit_rows(run_id: Optional[str] = None):
    with db() as conn:
        if run_id:
            rows = conn.execute("SELECT * FROM audit_trail WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM audit_trail ORDER BY id").fetchall()
    return [dict(r) for r in rows]