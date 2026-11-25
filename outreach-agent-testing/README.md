# Outreach Agent – Testing

## Architecture
```
prospects.csv -> validate_csv -> research (mock) -> draft (mock LLM)
      -> assess_risk (LOW/MEDIUM/HIGH) -> human review (approve/edit/reject)
      -> state machine (DRAFT -> APPROVED -> SENT | REJECTED)
      -> send_draft (blocks non-approved and HIGH risk) -> run_summary
```
- `app/csv_validation.py` – input guard (columns, blanks, emails, duplicates, bad files)
- `app/risk.py` – risk scoring and send enforcement
- `app/state_machine.py` – allowed transitions, mock sender
- `app/workflow.py` – end-to-end run, tokens, cost, summary

## Setup
```
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the workflow
```
python run_workflow.py
```
Outputs `results/run_summary.md` and `results/run_summary.json`.

## Run tests and coverage
```
python -m pytest --cov=app --cov-config=.coveragerc --cov-report=term-missing --cov-report=html -v
```
Coverage target: 80% on the three safety modules.

## Safety rules
1. Invalid CSV is rejected before any processing.
2. Only APPROVED drafts can be sent.
3. HIGH risk drafts can never be sent.
4. MEDIUM risk drafts need a named reviewer.
5. Rejection needs a reason; no transition out of SENT or REJECTED.

## Issues found and fixed
| # | Issue | Fix | Re-run result |
|---|-------|-----|---------------|
| 1 | (fill in after your run) | | |

#	Issue	Fix	Re-run result
1	Coverage run used --cov=app, which ignored the .coveragerc include list and measured workflow.py too (CoverageWarning)	Changed the command to --cov --cov-config=.coveragerc	Warning gone, report covers only the 3 safety modules, 100%