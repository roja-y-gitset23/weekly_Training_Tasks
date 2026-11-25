# Task 1: Approval UI

A simple web UI where a human reviewer approves, edits or rejects AI-drafted outreach emails before anything can be sent.

## Features

- Lists drafts with status `DRAFT` (company, research summary, subject, body)
- Three actions: **Approve**, **Edit and Approve**, **Reject** (reason required)
- Every decision is saved with reviewer, time and reason
- No email can move to `SENT` unless its status is `APPROVED`, enforced in the API and by a database trigger
- Tabs to view Drafts, Approved, Rejected and Sent

## Tech stack

Python, FastAPI, SQLite, plain HTML and JavaScript (no build step)

## Project structure

```
approval-ui/
├── db.py              # tables and the SENT-only-if-APPROVED trigger
├── seed.py            # 4 sample DRAFT emails (run_2026_001)
├── main.py            # FastAPI app and endpoints
├── requirements.txt
├── static/
│   └── index.html     # the review UI
└── screenshots/       # list, edit view, rejected with reason
```

## Setup and run (Windows PowerShell)

```powershell
cd approval-ui
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python seed.py
uvicorn main:app --reload
```

Open http://127.0.0.1:8000

If activation is blocked, run `Set-ExecutionPolicy -Scope Process Bypass` first.

## How to use

1. Enter your name in the **Reviewer** box (required).
2. On the **Drafts** tab, choose an action for each draft:
   - **Approve** approves it as written.
   - **Edit and Approve** lets you change the subject and body, then approves.
   - **Reject** asks for a reason, then rejects.
3. Use the **Approved** and **Rejected** tabs to see the outcome, reviewer, time and reason.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/drafts?status=DRAFT` | List drafts by status |
| POST | `/drafts/{id}/approve` | Approve (body: `reviewer`) |
| POST | `/drafts/{id}/edit-approve` | Edit and approve (`reviewer`, `subject`, `body`) |
| POST | `/drafts/{id}/reject` | Reject (`reviewer`, `reason`) |
| POST | `/drafts/{id}/send` | Mock send, only if `APPROVED` (else 409) |
| GET | `/decisions` | Full decision history |

Interactive docs: http://127.0.0.1:8000/docs

## Database

- `drafts`: id, run_id, company, research_summary, subject, body, status (`DRAFT`, `APPROVED`, `REJECTED`, `SENT`)
- `draft_decisions`: draft_id, decision, reviewer, reason, decided_at, original and final subject and body

**Rule:** a trigger blocks any update to `SENT` unless the previous status was `APPROVED`. A draft can also only be decided once (a second decision returns 409).

## Screenshots

See the `screenshots/` folder:

1. List of drafts
2. Edit view
3. Rejected draft with reason