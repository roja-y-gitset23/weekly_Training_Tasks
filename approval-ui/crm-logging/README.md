# Task 2: Mock CRM Logging

Builds on Task 1. After a draft is approved, it is "sent" with a mock sender and logged in a mock CRM table. Logging is idempotent and linked to the audit trail through `run_id`.

## Features

- `crm_activities` table: prospect_id, email_subject, body, sent_at, run_id
- Mock sender writes each email to a log file instead of really sending it
- Idempotent: approving or sending twice never creates a second CRM row
- CRM rows link to the `audit_trail` table through `run_id`
- Edited emails are logged with the edited body
- Rejected emails create no CRM row
- Bonus: daily limit of 20 emails per sender

## Tech stack

Python, FastAPI, SQLite, httpx (test client)

## Project structure

```
crm-logging/
├── db.py              # drafts, decisions, crm_activities, audit_trail, trigger
├── crm.py             # mock sender, idempotent logging, daily limit
├── main.py            # FastAPI app (approve now sends and logs)
├── test_crm.py        # 3 approved, 1 rejected, 1 edited scenario
├── test_limit.py      # daily limit scenario (bonus)
├── requirements.txt
└── static/
    └── index.html
```

## Setup and run (Windows PowerShell)

```powershell
cd approval-ui\crm-logging
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python test_crm.py
```

To run the app and UI:

```powershell
python ..\seed.py
uvicorn main:app --reload
```

## Expected output (`python test_crm.py`)

```
Approved 3 -> sent + logged 3 rows
Rejected 1 -> no CRM row
Edited 1 -> logged with edited body
```

The test uses its own `test_crm.db` and `test_sent.log`, so your real data is untouched.

## How each requirement is met

| Requirement | Implementation |
|---|---|
| `crm_activities` table | `db.py` |
| Mock send, then log after approval | `send_and_log()` in `crm.py`, called by approve and edit-approve |
| Idempotent logging | `UNIQUE(prospect_id, run_id)` with `INSERT OR IGNORE`, plus early return if already `SENT` |
| Link to audit trail | `crm_activities` and `audit_trail` share `run_id` |
| Test 3 approved, 1 rejected, 1 edited | `test_crm.py` |

## Bonus: daily limit per sender

- Default limit is 20 emails per sender per day (UTC), set with the `DAILY_LIMIT` environment variable
- When the limit is reached, the draft stays `APPROVED` (held), a `DAILY_LIMIT_REACHED` row is added to the audit trail and manual send returns 429
- `POST /send-approved` releases held emails when the day resets
- Run `python test_limit.py`. Expected output:

```
Sam: 25 approved -> 20 sent, 5 held (limit 20/day)
Amy: 1 approved -> 1 sent (own limit)
Next day: 5 held emails sent, 0 still held
```

## Extra endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/crm` | CRM rows |
| GET | `/audit?run_id=run_2026_001` | Audit trail for a run |
| GET | `/limits` | Sent today per sender |
| POST | `/send-approved` | Send held approved emails within limits |

## Notes

- The sender is mock only: emails are appended to `sent_emails.log`
- Data and test files (`*.db`, `*.log`) are git-ignored