# Outreach Agent – Demo (Task 2)

A small web app that shows the full outreach workflow from start to finish:

**upload CSV → research → draft → risk check → human review → send → CRM entry → audit trail**

Safety is built into every step. Invalid files, prompt injection, risky claims and runaway costs are all blocked automatically, and a human must approve every email.

> **Important:** research, the LLM and the email sender are **mocked** in this demo. No real web search, no real model calls and no real emails are involved. Token counts are estimates (about 4 characters per token).

---

## 1. What the demo shows

| # | Demo step | Where to see it |
|---|-----------|-----------------|
| 1 | Upload a CSV | Upload box at the top of the page |
| 2 | Watch research and drafting happen live | Run box (counters) and the **Audit trail** tab |
| 3 | Review drafts in the UI | **Review drafts** tab |
| 4 | Approve (or edit and approve) | Green path: email becomes `SENT` |
| 5 | See the CRM entry | **CRM entries** tab |
| 6 | See the audit trail | **Audit trail** tab |
| 7 | Rejected draft | Falcon Retail: approval is refused, then rejected with a reason |
| 8 | Blocked injection | Harbor Tech: card shows `BLOCKED`, red row in the audit trail |

---

## 2. Architecture

```
 CSV upload
     │
     ▼
 Input guard ──── invalid file? ──► rejected (HTTP 400), nothing is processed
     │
     ▼
 Limits check ─── too many prospects / too many runs? ──► rejected (HTTP 429)
     │
     ▼   (background thread, one prospect at a time)
 Research (mock web search)
     │
     ▼
 Injection guard ─ attack text found? ──► draft marked BLOCKED, logged, never sent
     │
     ▼
 Draft (mock LLM) ── token budget exceeded? ──► run stopped, logged
     │
     ▼
 Risk score: LOW / MEDIUM / HIGH
     │
     ▼
 Draft stored with status DRAFT
     │
     ▼
 Human review in the UI
   ├─ Approve / Edit and Approve ──► risk re-checked ──► state machine ──► mock send ──► CRM row
   └─ Reject (reason required) ───► REJECTED, no email, no CRM row

 Every step above writes a row to the audit trail.
```

### Components

| File | Responsibility |
|------|----------------|
| `app/csv_validation.py` | Input guard: required columns, no blank fields, valid emails, no duplicates, valid text file |
| `app/risk.py` | Scores a draft LOW / MEDIUM / HIGH and enforces the send rules |
| `app/state_machine.py` | Allowed status changes and the mock sender (`send_draft`) |
| `app/pipeline.py` | Research, injection guard, drafting, token budget, run limits |
| `app/db.py` | SQLite schema and small database helpers |
| `app/audit.py` | Writes one audit row per step |
| `app/main.py` | FastAPI app: upload, approve, reject, CRM and audit endpoints |
| `static/index.html` | The review UI (plain HTML and JavaScript, no build step) |
| `reset_demo.py` | Deletes the demo database so you can start clean |
| `data/prospects.csv` | 10 sample prospects |
| `data/bad.csv` | An invalid CSV used to show the input guard |

`csv_validation.py`, `risk.py` and `state_machine.py` are the same safety modules that were tested in Task 1 (36 tests, 100% coverage on these three files).

---

## 3. Folder structure

```
outreach-agent-demo/
├── app/
│   ├── __init__.py
│   ├── csv_validation.py
│   ├── risk.py
│   ├── state_machine.py
│   ├── db.py
│   ├── audit.py
│   ├── pipeline.py
│   └── main.py
├── static/
│   └── index.html
├── data/
│   ├── prospects.csv
│   └── bad.csv
├── reset_demo.py
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 4. Setup and run

**Requirements:** Python 3 and PowerShell (Windows).

```powershell
cd C:\Week6_Training_Tasks\outreach-agent-demo
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`requirements.txt`:

```
fastapi
uvicorn
python-multipart
```

Start a clean demo:

```powershell
python reset_demo.py
python -m uvicorn app.main:app --port 8000
```

Open **http://127.0.0.1:8000** in your browser.

The SQLite database file `demo.db` is created automatically in the project folder.

---

## 5. How to use the UI

1. **Upload:** choose `data/prospects.csv` and click **Upload and run**. Use `data/bad.csv` first to see the input guard reject a bad file.
2. **Watch:** the run box shows status, how many prospects are processed, tokens and cost. Drafts appear one by one (about 12 seconds for 10 prospects).
3. **Review:** each draft card shows the company, a risk badge, the research notes, and an editable subject and body.
4. **Approve:** click **Approve (or Edit and Approve)**. If you changed the text, the risk is checked again on the new text.
5. **Reject:** click **Reject** and type a reason. The reason is required.
6. **CRM entries tab:** shows every email that was sent and logged.
7. **Audit trail tab:** shows every step. Blocked and refused actions are highlighted in red.

The **Reviewer** field (top right of the upload box) is the name stored with every decision.

---

## 6. What happens with the sample data

`data/prospects.csv` has 10 prospects. The mock research data is set up so that each safety feature has something to show:

| Prospect | What happens | Why |
|----------|--------------|-----|
| Most companies | Draft created, risk **LOW** | Normal research note |
| Cedar Finance | Draft created, risk **MEDIUM** | Research mentions a "discount" |
| Falcon Retail | Draft created, risk **HIGH** | Research says "guarantees 100% savings" (an unsupported claim) |
| Harbor Tech | Status **BLOCKED**, no draft | Research text contains "IGNORE PREVIOUS INSTRUCTIONS" |
| Zeta Textiles | Draft created with "no research" | No research result found; the draft makes no claims |

---

## 7. Status and state rules

Allowed status changes (the state machine):

```
DRAFT ──approve──► APPROVED ──send──► SENT
  │                    │
  └────reject───►  REJECTED  ◄──reject──┘
```

- `SENT` and `REJECTED` are final. No further changes are allowed.
- Approval needs a reviewer name. Rejection needs a reason.
- `BLOCKED` is set by the pipeline when an injection is found. It is outside the normal flow and is final: a blocked draft cannot be approved or rejected.

---

## 8. Safety rules

1. **Input guard:** a CSV with missing columns, blank fields, bad or duplicate emails, no rows, or non-text content is rejected before any processing.
2. **Injection guard:** research text that contains attack instructions (for example "ignore previous instructions") is blocked. No draft is created and the event is logged.
3. **Risk scoring:**
   - **HIGH:** unsupported claims (guarantee, 100%, risk-free), phone numbers or SSN-like numbers, injection phrases.
   - **MEDIUM:** discount, pricing or `$` mentioned, or a very long body.
   - **LOW:** everything else.
4. **HIGH risk can never be approved or sent.** The reviewer must edit the text (the risk is re-checked) or reject it.
5. **Only `APPROVED` drafts can be sent.** The mock sender refuses anything else.
6. **CRM logging is idempotent:** one row per draft (`UNIQUE(draft_id)`), so approving twice cannot create two rows.
7. **Everything is logged** in the audit trail with the run id.

---

## 9. Cost and runaway protection

| Guard | Default | What happens when it is hit |
|-------|---------|-----------------------------|
| `MAX_PROSPECTS` | 25 per run | The upload is rejected (HTTP 400/429 message) |
| `MAX_TOKENS_PER_RUN` | 5000 | The run stops; status `stopped_budget`; audit row "BUDGET EXCEEDED" |
| `MAX_RUNS_PER_HOUR` | 10 | New uploads are refused with HTTP 429 |
| `DEMO_DELAY` | 0.6 seconds | Only slows the demo so people can watch; not a safety limit |

Change a limit by setting an environment variable before starting the server. Example for a live budget demo:

```powershell
$env:MAX_TOKENS_PER_RUN = "300"
python -m uvicorn app.main:app --port 8000
```

Remove it afterwards:

```powershell
Remove-Item Env:MAX_TOKENS_PER_RUN
```

Other cost controls: the pipeline is a single pass with no retry loops, and tokens and cost are tracked per run and shown in the UI. Prices in `app/pipeline.py` (`PRICE_IN`, `PRICE_OUT`) are placeholders; change them to your model's real pricing.

---

## 10. Database tables

| Table | Purpose |
|-------|---------|
| `runs` | One row per upload: status, progress, tokens, cost |
| `drafts` | One row per prospect: research, subject, body, risk, status, reviewer, reason, edited flag |
| `audit_log` | `run_id`, `timestamp`, `step`, `thought`, `action`, `action_input`, `observation`, `tokens` |
| `crm_activities` | `draft_id` (unique), `run_id`, `prospect_email`, `email_subject`, `body`, `sent_at` |

The `run_id` links drafts, audit rows and CRM rows together.

---

## 11. API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | The UI |
| POST | `/upload` | Upload a CSV, validate it and start a run |
| GET | `/runs/latest` | The most recent run with its drafts |
| GET | `/runs/{run_id}` | A specific run with its drafts |
| POST | `/drafts/{id}/approve` | Approve (optionally with edited subject/body); sends and logs to CRM |
| POST | `/drafts/{id}/reject` | Reject with a reason |
| GET | `/crm` | All CRM activities |
| GET | `/audit/{run_id}` | Audit trail for a run |

Typical error codes: `400` invalid CSV or missing rejection reason, `403` blocked or HIGH-risk approval refused, `404` not found, `409` invalid status change, `429` run limit reached.

---

## 12. 7-minute demo script

| Time | Action | What to say |
|------|--------|-------------|
| 0:00 | Show this README's architecture diagram | "Upload, research, draft, risk check, human approval, send, CRM, audit trail." |
| 0:45 | Upload `bad.csv` | "The input guard rejects invalid files before any processing." |
| 1:05 | Upload `prospects.csv`; switch between the run box and the Audit trail tab | "Each prospect is researched then drafted. Tokens and cost are tracked live." |
| 2:15 | Open Review drafts; point to the risk badges | "Every draft is risk-scored. Nothing is sent automatically." |
| 2:45 | Edit a sentence in a LOW or MEDIUM draft and click Approve | "Edit and approve. It is sent with the edited text and the reviewer's name." |
| 3:30 | Open CRM entries | "One CRM row per sent email, linked to the run. Approving twice cannot duplicate it." |
| 4:00 | **Rejected draft:** on Falcon Retail click Approve (refused), then Reject with a reason | "HIGH-risk drafts cannot be approved. The reviewer rejects with a reason and no CRM row is created." |
| 5:00 | **Blocked injection:** show the Harbor Tech BLOCKED card and the red audit row | "The research text told the agent to ignore its instructions. The guard blocked it and logged it." |
| 5:45 | Audit trail tab | "Every step is logged: thought, action, input, observation, tokens." |
| 6:15 | Answer the two questions below | |
| 7:00 | End | |

---

## 13. Prepared answers

### "What if the agent sends the wrong email?"

- The agent cannot send on its own. Only a human-approved draft can pass the state machine.
- Prevention comes first: the risk check blocks unsupported claims, personal data and injected instructions, and HIGH-risk drafts cannot be approved at all.
- A person reviews the exact text before sending. The audit trail and CRM record who approved which email and when.
- A sent email cannot be unsent, so the remaining safeguards are small volumes, sender limits, a correction email using the CRM record, and reviewing the audit log to improve the rules.
- Honest limit: a reviewer can still approve a bad email, and this demo's sender is a mock that does not send real email.

### "How do you stop runaway costs?"

- Three built-in caps: `MAX_PROSPECTS`, `MAX_TOKENS_PER_RUN` and `MAX_RUNS_PER_HOUR`.
- When the token budget is hit, the run stops and the audit trail shows "BUDGET EXCEEDED".
- The pipeline is a single pass with no retry loops, so cost has a fixed upper bound.
- Tokens and cost are tracked per run and visible in the UI.
- In production, also set a spending limit and alerts with the model provider.

---

## 14. Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Activate the venv (`.\venv\Scripts\Activate.ps1`) and run `pip install -r requirements.txt` |
| `No module named app` | Run the server from the project folder: `python -m uvicorn app.main:app --port 8000` |
| Port 8000 already in use | Use another port, e.g. `--port 8001`, and open that port in the browser |
| Old data from a previous run | Stop the server, run `python reset_demo.py`, start the server again |
| Upload says "Only .csv files are accepted" | Choose a file ending in `.csv` |
| Cannot approve a HIGH-risk draft | Expected. Edit the risky text (risk is re-checked) or reject the draft |

---

## 15. Limitations

- Research, the LLM and the sender are mocked, so results are fixed and no real email leaves the system.
- Token counts are estimates and prices are placeholders.
- There is no login. The reviewer name is just a text field.
- The database is a single local SQLite file, which is fine for a demo but not for production use.

---

## 16. Git workflow

Work is done on a feature branch with one single-line commit per file, then merged with a Pull Request **after** the demo:

```powershell
git checkout -b feature/demo
# ... one commit per file ...
git push -u origin feature/demo
```

Open a Pull Request into `main` on GitHub, present the demo, then click **Merge pull request** and **Confirm merge**. Finally:

```powershell
git checkout main
git pull
```