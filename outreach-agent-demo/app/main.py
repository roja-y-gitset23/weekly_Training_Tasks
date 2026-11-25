import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .audit import log, now
from .csv_validation import CSVValidationError, validate_csv
from .db import execute, init_db, query
from .pipeline import LimitError, check_limits, process_run
from .risk import Risk, RiskPolicyError, assess_risk
from .state_machine import Draft, InvalidTransition, State, send_draft

app = FastAPI(title="Outreach Agent Demo")
init_db()
STATIC = Path(__file__).resolve().parent.parent / "static"


class ApproveIn(BaseModel):
    reviewer: str = "reviewer1"
    subject: Optional[str] = None
    body: Optional[str] = None


class RejectIn(BaseModel):
    reviewer: str = "reviewer1"
    reason: str = ""


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.post("/upload")
async def upload(background: BackgroundTasks, file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are accepted")
    tmp = Path(tempfile.gettempdir()) / f"upload_{uuid.uuid4().hex}.csv"
    tmp.write_bytes(await file.read())
    try:
        rows = validate_csv(tmp)
        check_limits(len(rows))
    except CSVValidationError as e:
        raise HTTPException(400, f"Input guard blocked the file: {e}")
    except LimitError as e:
        raise HTTPException(429, str(e))
    finally:
        tmp.unlink(missing_ok=True)

    run_id = f"run_{uuid.uuid4().hex[:8]}"
    execute("INSERT INTO runs(run_id,created_at,status,total) VALUES(?,?,?,?)",
            (run_id, now(), "running", len(rows)))
    log(run_id, "upload", "Validate CSV", "validate_csv", file.filename,
        f"Valid CSV, {len(rows)} prospects")
    background.add_task(process_run, run_id, rows)
    return {"run_id": run_id}


def _run_payload(run_id):
    run = query("SELECT * FROM runs WHERE run_id=?", (run_id,))
    if not run:
        raise HTTPException(404, "Run not found")
    drafts = query("SELECT * FROM drafts WHERE run_id=? ORDER BY id", (run_id,))
    return {**run[0], "drafts": drafts}


@app.get("/runs/latest")
def latest_run():
    rows = query("SELECT run_id FROM runs ORDER BY created_at DESC, rowid DESC LIMIT 1")
    if not rows:
        raise HTTPException(404, "No runs yet")
    return _run_payload(rows[0]["run_id"])


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    return _run_payload(run_id)


def _get_draft(draft_id):
    rows = query("SELECT * FROM drafts WHERE id=?", (draft_id,))
    if not rows:
        raise HTTPException(404, "Draft not found")
    return rows[0]


@app.post("/drafts/{draft_id}/approve")
def approve(draft_id: int, data: ApproveIn):
    row = _get_draft(draft_id)
    run_id = row["run_id"]
    if row["status"] == "BLOCKED":
        log(run_id, "approval", "Approve attempt", "approve_blocked", draft_id,
            "Refused: draft was blocked by the injection guard")
        raise HTTPException(403, "Blocked draft cannot be approved")

    subject = data.subject if data.subject is not None else row["subject"]
    body = data.body if data.body is not None else row["body"]
    edited = (subject, body) != (row["subject"], row["body"])
    risk = assess_risk(subject, body)
    draft = Draft(row["email"], row["company"], subject, body, risk,
                  State(row["status"]), edited=edited)

    if risk == Risk.HIGH:
        log(run_id, "approval", "Approve attempt on HIGH risk draft", "approve_blocked",
            draft_id, "Refused: HIGH risk draft (unsupported claim / sensitive content)")
        raise HTTPException(403, "HIGH risk draft cannot be approved. Edit it or reject it.")
    try:
        draft.transition(State.APPROVED, reviewer=data.reviewer)
        send_draft(draft)  # mock sender: only APPROVED drafts pass
    except InvalidTransition as e:
        raise HTTPException(409, str(e))
    except RiskPolicyError as e:
        raise HTTPException(403, str(e))

    execute("UPDATE drafts SET subject=?, body=?, risk=?, status='SENT', reviewer=?, edited=? WHERE id=?",
            (subject, body, risk.value, data.reviewer, int(edited), draft_id))
    execute("INSERT OR IGNORE INTO crm_activities(draft_id,run_id,prospect_email,email_subject,body,sent_at)"
            " VALUES(?,?,?,?,?,?)", (draft_id, run_id, row["email"], subject, body, now()))
    log(run_id, "approval", f"{data.reviewer} approved{' (edited)' if edited else ''}",
        "approve_and_send", draft_id, f"Sent to {row['email']} and logged in CRM")
    return {"status": "SENT"}


@app.post("/drafts/{draft_id}/reject")
def reject(draft_id: int, data: RejectIn):
    row = _get_draft(draft_id)
    if not data.reason.strip():
        raise HTTPException(400, "A rejection reason is required")
    draft = Draft(row["email"], row["company"], row["subject"], row["body"],
                  Risk(row["risk"]), State(row["status"]) if row["status"] != "BLOCKED" else State.SENT)
    try:
        draft.transition(State.REJECTED, reviewer=data.reviewer, reason=data.reason)
    except InvalidTransition as e:
        raise HTTPException(409, str(e))
    execute("UPDATE drafts SET status='REJECTED', reviewer=?, reason=? WHERE id=?",
            (data.reviewer, data.reason, draft_id))
    log(row["run_id"], "approval", f"{data.reviewer} rejected", "reject", draft_id,
        f"Reason: {data.reason}. No email sent, no CRM row.")
    return {"status": "REJECTED"}


@app.get("/crm")
def crm():
    return query("SELECT * FROM crm_activities ORDER BY id")


@app.get("/audit/{run_id}")
def audit(run_id: str):
    return query("SELECT * FROM audit_log WHERE run_id=? ORDER BY id", (run_id,))