from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from drafts import approve_draft, get_draft, list_drafts, reject_draft
from sender import ApprovalError
from service import send_and_log

app = FastAPI(title="Approval Enforcement API")


class ApproveBody(BaseModel):
    reviewer: str = Field(min_length=1)


class RejectBody(BaseModel):
    reviewer: str = Field(min_length=1)
    reason: str = Field(min_length=1)


def _require_draft(draft_id):
    if get_draft(draft_id) is None:
        raise HTTPException(status_code=404, detail="Draft not found")


@app.get("/drafts")
def drafts():
    return list_drafts()


@app.post("/drafts/{draft_id}/approve")
def approve(draft_id: int, body: ApproveBody):
    _require_draft(draft_id)
    if not approve_draft(draft_id, body.reviewer):
        raise HTTPException(status_code=409, detail="Only a DRAFT can be approved")
    return {"id": draft_id, "status": "APPROVED"}


@app.post("/drafts/{draft_id}/reject")
def reject(draft_id: int, body: RejectBody):
    _require_draft(draft_id)
    if not reject_draft(draft_id, body.reviewer, body.reason):
        raise HTTPException(status_code=409, detail="Only a DRAFT can be rejected")
    return {"id": draft_id, "status": "REJECTED"}


@app.post("/drafts/{draft_id}/send")
def send(draft_id: int):
    _require_draft(draft_id)
    try:
        return send_and_log(draft_id)
    except ApprovalError as e:
        raise HTTPException(status_code=403, detail=str(e))