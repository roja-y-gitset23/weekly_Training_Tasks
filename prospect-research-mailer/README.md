# Prospect Outreach Pipeline

One project covering two tasks that share a single SQLite database (`research.db`) and a single run id (`run_2026_001`).

| Task | Script | What it does |
|---|---|---|
| Task 1: Research Step | `research_step.py` | Mock web search for each prospect, stores research notes |
| Task 2: Draft Personalised Emails | `draft_emails.py` | Drafts one email per researched prospect, stored as `DRAFT` |

## Folder structure

```
prospect_outreach/
├── README.md
├── requirements.txt
├── research_step.py       # Task 1
├── draft_emails.py        # Task 2
├── research.db            # created automatically
├── sample_drafts.md       # created by Task 2 (3 sample drafts)
└── rating_table.md        # created by Task 2 (fill in your ratings)
```

## Requirements

- Python 3.9 or newer
- Package: `pydantic>=2.0` (everything else is the Python standard library)
- Optional, only for a real LLM: `google-genai` and a Gemini API key

`requirements.txt`:

```
pydantic>=2.0
```

## Setup (Windows PowerShell)

```powershell
cd prospect_outreach
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## How to run

Run Task 1 first, because Task 2 reads its output.

```powershell
python research_step.py
python draft_emails.py
```

### Expected output

Task 1:

```
Researched 9/10 prospects (1 no result)
Run id: run_2026_001
```

Task 2:

```
Drafted 9 emails with status DRAFT (1 skipped, no research)
Run id: run_2026_001
```

Both scripts can be re-run safely. They clear the previous data for the same run id first.

## Task 1: Research Step

- Calls a mock web search for each of the 10 prospects.
- Processes prospects with a concurrency limit of 3 (`asyncio.Semaphore(3)`).
- A company with no search result (`Ghost Industries`) does not stop the run. It is saved with status `no research`.
- Research is saved in the `research` table, linked to `run_id`.
- Every step is written to the `audit_log` table.

## Task 2: Draft Personalised Emails

- The prompt uses the research notes, contact name, industry and a fixed company pitch.
- Output is structured as `subject`, `body`, `personalisation_points` and validated with Pydantic (`EmailDraft`).
- One email is drafted per researched prospect and saved in the `emails` table with status `DRAFT`. Nothing is ever sent.
- Guardrail: an email must not contain claims that are not in the research notes. The check verifies that:
  - every personalisation point appears in the notes
  - every number appears in the notes or the pitch
  - every name or brand term appears in the notes, pitch or contact details
- A draft that fails validation or the guardrail is retried up to 3 times. If it still fails, it is saved as `BLOCKED`, never as `DRAFT`.
- Prospects with no research are skipped and logged.

### LLM mode

| Mode | How to enable | Notes |
|---|---|---|
| Mock (default) | nothing to do | Runs offline with no API key |
| Gemini | see below | Real model with the same prompt, validation and guardrail |

```powershell
pip install google-genai
$env:LLM_PROVIDER="gemini"
$env:GEMINI_API_KEY="your_key_here"
python draft_emails.py
```

Never commit your API key. Keep it in an environment variable or a `.env` file listed in `.gitignore`.

## Database tables

| Table | Columns |
|---|---|
| `research` | id, run_id, prospect_id, company, status (`researched` / `no research`), notes, created_at |
| `emails` | id, run_id, prospect_id, company, contact_name, status (`DRAFT` / `BLOCKED`), subject, body, personalisation_points, created_at |
| `audit_log` | id, run_id, ts, step, prospect_id, message |

## Check the results

```powershell
python -c "import sqlite3; c=sqlite3.connect('research.db'); print(c.execute('SELECT company,status FROM research ORDER BY prospect_id').fetchall()); print(c.execute('SELECT company,status FROM emails ORDER BY prospect_id').fetchall())"
```

You should see 10 research rows (9 `researched`, 1 `no research`) and 9 email rows (all `DRAFT`).

## Submission checklist

- [ ] `sample_drafts.md`: 3 sample drafts
- [ ] `rating_table.md`: 5 drafts rated 1-5 for relevance, tone and accuracy (fill in the blank cells yourself)
- [ ] Code: `research_step.py`, `draft_emails.py`, `requirements.txt`, `README.md`

## Rating rubric (1-5)

| Score | Relevance | Tone | Accuracy |
|---|---|---|---|
| 5 | Clearly uses the company's own situation | Professional, warm, natural | Every claim is in the research notes |
| 3 | Generic with some personalisation | Acceptable but stiff or salesy | Minor stretching of a note |
| 1 | Could be sent to anyone | Inappropriate | Contains invented claims |