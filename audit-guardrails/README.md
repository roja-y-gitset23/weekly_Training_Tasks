# Week 6 Training Tasks: Audit Trail, Guardrails and Approval Enforcement

Two tasks for the prospect outreach agent.

- **Task 1: Audit Trail and Guardrails.** Every run is fully recorded, and guards protect the
  input, the research text and the output.
- **Task 2: Approval Enforcement Tests.** Tests prove that no email is sent without human approval,
  and that the system is safe after a crash or a CRM outage.

Together they cover the whole flow: **research -> guards -> draft -> human approval -> send -> CRM log**.
Task 1 protects what the agent reads and writes. Task 2 protects what happens after a draft exists.

## Folder structure

```
Week6_Training_Tasks/
├── README.md                      # this file
├── .gitignore
├── audit-guardrails/              # Task 1
│   ├── config.py                  # settings (rate limit, required columns)
│   ├── database.py                # SQLite tables
│   ├── audit.py                   # audit logger + CSV export
│   ├── guards.py                  # rate limit, input, injection and output guards
│   ├── agent.py                   # the research run
│   ├── main.py                    # runs all 4 tests, writes the submission files
│   ├── audit_trail_run_2026_001.csv   # SUBMIT: audit trail of one run
│   └── injection_test_result.txt      # SUBMIT: injection test result
└── approval-enforcement-tests/    # Task 2
    ├── requirements.txt
    ├── database.py  drafts.py  sender.py  crm.py  service.py  agent.py  api.py
    ├── conftest.py
    ├── test_approval_enforcement.py
    ├── run_tests.py
    ├── README.md                  # safety rules
    └── test_report.txt            # SUBMIT: test report, all tests passing
```

## Requirements

- Python 3.10 or newer (tested on Python 3.14, Windows PowerShell)
- Task 1: standard library only, nothing to install
- Task 2: `pip install -r requirements.txt` (fastapi, httpx, pytest, uvicorn)

---

## Task 1: Audit Trail and Guardrails

### Requirement map

| Requirement | Where |
|---|---|
| Every run records the full schema | `database.py` (table) and `audit.py` (logger) |
| Input guard: valid CSV only | `guards.py` -> `input_guard()` |
| Output guard: no PII beyond name and business email, no unsupported claims | `guards.py` -> `output_guard()` |
| Prompt injection test | `DarkStar Media` prospect, blocked by `injection_guard()` |
| Guard blocking it and the event in the audit log | `injection_guard` row in the audit trail (step 20) |
| Per-user rate limit | `guards.py` -> `rate_limit_check()` (3 runs per 60 seconds per user) |

### Audit schema

Every step writes one row: `run_id`, `timestamp`, `step`, `thought`, `action`, `action_input`,
`observation`, `tokens`. Tokens are estimated at about 4 characters per token. Pass real LLM usage
if you have it.

### Guards

| Guard | What it does |
|---|---|
| Rate limit | Blocks a user's 4th run inside 60 seconds (status `RATE_LIMITED`) |
| Input guard | Accepts only a real UTF-8 `.csv` with the required columns, valid emails and at most 100 rows |
| Injection guard | Treats research text as untrusted data. Phrases like "ignore all previous instructions" block that prospect, and no draft is created |
| Output guard | Blocks phone numbers, SSNs, street addresses, extra or personal emails, banned claims ("guaranteed", "100%") and numbers not found in the research |

### Run

```powershell
cd audit-guardrails
python main.py
```

### Expected result

- Run `run_2026_001`: 6 prospects | 4 drafted | 1 no research | 1 blocked
- `INJECTION TEST: PASSED`
- Bad draft blocked by the output guard, `bad.csv` blocked by the input guard
- Bob's 4th run is `RATE_LIMITED`

### Submit

`audit_trail_run_2026_001.csv` and `injection_test_result.txt`

---

## Task 2: Approval Enforcement Tests

### Safety rules

1. **Approval gate.** `send_email()` is the only sender. It sends only if the draft status is
   `APPROVED`, otherwise it raises `ApprovalError`.
2. **API returns 403.** `POST /drafts/{id}/send` on a DRAFT or REJECTED draft returns HTTP 403 and
   sends nothing.
3. **Database backstop.** A trigger blocks any update to `SENT` unless the old status was
   `APPROVED`, so even raw SQL cannot bypass approval.
4. **Reject needs a reason, approve needs a reviewer.** A rejected draft can never be approved.
5. **No duplicate emails.** Claiming the draft and recording the email happen in one transaction,
   and `sent_emails.draft_id` is UNIQUE. A second send returns `already_sent`.
6. **Restart safety.** State lives in the database. After a crash the agent finishes pending CRM
   logging, then sends only drafts still `APPROVED`.
7. **CRM failure safety.** If the CRM is down, the email stays `SENT` but `crm_logged` stays 0 and
   no CRM row is written. When the CRM is back it is logged exactly once, with no resend.
8. **Idempotent CRM logging.** `crm_activities.draft_id` is UNIQUE.

### Test map

| Group | Requirement proved | Tests |
|---|---|---|
| A | Sender cannot send a non-approved draft | A1-A6 |
| B | API bypass (send without approval) returns 403 | B1-B6 |
| C | Crash in the middle of a run, restart, no duplicate emails | C1-C2 |
| D | CRM down, email not marked as logged | D1-D3 |

### Run

```powershell
cd approval-enforcement-tests
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_tests.py
```

### Expected result

`18 passed` (the one httpx deprecation warning is harmless). The report is saved to `test_report.txt`.

### Submit

`test_report.txt` (all tests passing)

---

## Notes

- The crash in the restart test is simulated with `SimulatedCrash`, right after an email is sent and
  before its CRM log, which is the worst moment to crash.
- The Task 1 and Task 2 folders are separate projects with their own databases (`audit.db` and
  `approval.db`). Neither is committed.