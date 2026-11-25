import sqlite3

import pytest

import crm
from agent import SimulatedCrash, run_agent
from database import count_rows, get_db
from drafts import approve_draft, create_draft, get_draft, reject_draft
from sender import ApprovalError, send_email
from service import send_and_log

RUN = "run_2026_001"


def new_draft(company="Acme", approved=False):
    draft_id = create_draft(RUN, company, f"Idea for {company}", f"Hi, a note for {company}.")
    if approved:
        assert approve_draft(draft_id, "reviewer1")
    return draft_id


# ===================== A. Sender cannot send a non-approved draft =====================

@pytest.mark.parametrize("final_status", ["DRAFT", "REJECTED"])
def test_A1_sender_refuses_non_approved_draft(final_status):
    draft_id = new_draft()
    if final_status == "REJECTED":
        reject_draft(draft_id, "reviewer1", "Not relevant")
    with pytest.raises(ApprovalError):
        send_email(draft_id)
    assert count_rows("sent_emails") == 0
    assert get_draft(draft_id)["status"] == final_status


def test_A2_sender_refuses_unknown_draft():
    with pytest.raises(ApprovalError):
        send_email(9999)
    assert count_rows("sent_emails") == 0


def test_A3_sender_sends_approved_draft():
    draft_id = new_draft(approved=True)
    assert send_email(draft_id) == "sent"
    assert get_draft(draft_id)["status"] == "SENT"
    assert count_rows("sent_emails") == 1


def test_A4_database_blocks_marking_sent_without_approval():
    """Even raw SQL cannot bypass approval (database trigger)."""
    draft_id = new_draft()
    with pytest.raises(sqlite3.DatabaseError, match="Cannot mark SENT"):
        with get_db() as con:
            con.execute("UPDATE drafts SET status='SENT' WHERE id=?", (draft_id,))
    assert get_draft(draft_id)["status"] == "DRAFT"


def test_A5_sending_twice_creates_one_email():
    draft_id = new_draft(approved=True)
    assert send_email(draft_id) == "sent"
    assert send_email(draft_id) == "already_sent"
    assert count_rows("sent_emails") == 1


def test_A6_rejected_draft_cannot_be_approved_or_sent():
    draft_id = new_draft()
    reject_draft(draft_id, "reviewer1", "Wrong contact")
    assert approve_draft(draft_id, "reviewer2") is False
    with pytest.raises(ApprovalError):
        send_email(draft_id)
    assert count_rows("sent_emails") == 0


# ===================== B. API bypass attempts =====================

def test_B1_api_send_without_approval_returns_403(client):
    draft_id = new_draft()                       # status DRAFT, never approved
    r = client.post(f"/drafts/{draft_id}/send")
    assert r.status_code == 403
    assert count_rows("sent_emails") == 0
    assert get_draft(draft_id)["status"] == "DRAFT"


def test_B2_api_send_rejected_draft_returns_403(client):
    draft_id = new_draft()
    r = client.post(f"/drafts/{draft_id}/reject", json={"reviewer": "priya", "reason": "Bad fit"})
    assert r.status_code == 200
    r = client.post(f"/drafts/{draft_id}/send")
    assert r.status_code == 403
    assert count_rows("sent_emails") == 0


def test_B3_api_approved_draft_sends_once(client):
    draft_id = new_draft()
    assert client.post(f"/drafts/{draft_id}/approve", json={"reviewer": "priya"}).status_code == 200
    first = client.post(f"/drafts/{draft_id}/send")
    second = client.post(f"/drafts/{draft_id}/send")
    assert first.status_code == 200 and first.json()["email"] == "sent"
    assert second.status_code == 200 and second.json()["email"] == "already_sent"
    assert count_rows("sent_emails") == 1


def test_B4_api_send_unknown_draft_returns_404(client):
    assert client.post("/drafts/9999/send").status_code == 404


def test_B5_api_approve_requires_reviewer_name(client):
    draft_id = new_draft()
    assert client.post(f"/drafts/{draft_id}/approve", json={}).status_code == 422
    assert get_draft(draft_id)["status"] == "DRAFT"


def test_B6_api_reject_requires_reason(client):
    draft_id = new_draft()
    r = client.post(f"/drafts/{draft_id}/reject", json={"reviewer": "priya", "reason": ""})
    assert r.status_code == 422
    assert get_draft(draft_id)["status"] == "DRAFT"


# ===================== C. Restart safety =====================

def test_C1_restart_after_crash_resumes_without_duplicate_emails():
    ids = [new_draft(f"Company{i}", approved=True) for i in range(1, 5)]

    with pytest.raises(SimulatedCrash):          # agent dies after the 2nd email
        run_agent(RUN, crash_after_sends=2)
    assert count_rows("sent_emails") == 2
    assert count_rows("drafts", "status='APPROVED'") == 2
    assert count_rows("crm_activities") == 1     # 2nd email sent, crash before its CRM log

    stats = run_agent(RUN)                       # restart
    assert stats["sent"] == 2                    # only the 2 unsent drafts
    assert count_rows("sent_emails") == 4
    assert count_rows("crm_activities") == 4

    with get_db() as con:
        emailed = [r["draft_id"] for r in con.execute("SELECT draft_id FROM sent_emails")]
    assert sorted(emailed) == sorted(ids)        # every draft emailed exactly once


def test_C2_running_again_after_finish_sends_nothing_new():
    for i in range(1, 4):
        new_draft(f"Company{i}", approved=True)
    assert run_agent(RUN)["sent"] == 3
    assert run_agent(RUN)["sent"] == 0
    assert count_rows("sent_emails") == 3
    assert count_rows("crm_activities") == 3


# ===================== D. Mock CRM failure =====================

def test_D1_crm_down_email_is_not_marked_as_logged(monkeypatch):
    monkeypatch.setattr(crm, "CRM_DOWN", True)
    draft_id = new_draft(approved=True)
    assert send_and_log(draft_id) == {"email": "sent", "crm": "failed"}

    d = get_draft(draft_id)
    assert d["status"] == "SENT"                 # email went out once
    assert d["crm_logged"] == 0                  # NOT marked as logged
    assert "down" in d["crm_error"].lower()
    assert count_rows("crm_activities") == 0


def test_D2_after_crm_recovers_it_is_logged_once_without_resending(monkeypatch):
    monkeypatch.setattr(crm, "CRM_DOWN", True)
    draft_id = new_draft(approved=True)
    send_and_log(draft_id)

    monkeypatch.setattr(crm, "CRM_DOWN", False)  # CRM is back
    run_agent(RUN)
    run_agent(RUN)                               # run twice on purpose
    assert get_draft(draft_id)["crm_logged"] == 1
    assert count_rows("crm_activities") == 1
    assert count_rows("sent_emails") == 1


def test_D3_api_send_with_crm_down_reports_failed_logging(client, monkeypatch):
    monkeypatch.setattr(crm, "CRM_DOWN", True)
    draft_id = new_draft(approved=True)
    r = client.post(f"/drafts/{draft_id}/send")
    assert r.status_code == 200
    assert r.json() == {"email": "sent", "crm": "failed"}
    assert get_draft(draft_id)["crm_logged"] == 0
    assert count_rows("crm_activities") == 0