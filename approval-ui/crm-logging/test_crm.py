import os

# Use a separate test database and log file
for f in ("test_crm.db", "test_sent.log"):
    if os.path.exists(f):
        os.remove(f)
os.environ["APPROVAL_DB"] = "test_crm.db"
os.environ["SENT_LOG"] = "test_sent.log"

from fastapi.testclient import TestClient  # noqa: E402

from db import get_conn  # noqa: E402
from main import app  # noqa: E402

RUN_ID = "run_2026_001"
EDITED_SUBJECT = "Edited subject for Company 5"
EDITED_BODY = "Hi Team,\n\nThis is the EDITED body written by the reviewer.\n\nBest,\nSam"

# --- Seed 5 drafts (prospects 1 to 5) ---
conn = get_conn()
with conn:
    for i in range(1, 6):
        conn.execute(
            """INSERT INTO drafts (run_id, prospect_id, company, research_summary, subject, body)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (RUN_ID, i, f"Company {i}", f"Research notes {i}", f"Subject {i}", f"Original body {i}"),
        )
conn.close()

client = TestClient(app)
who = {"reviewer": "Tester"}

# --- 3 approved ---
for i in (1, 2, 3):
    assert client.post(f"/drafts/{i}/approve", json=who).status_code == 200

# --- idempotency: approve / send draft 1 again -> must NOT create a second row ---
assert client.post("/drafts/1/approve", json=who).status_code == 200
assert client.post("/drafts/1/send").status_code == 200

# --- 1 rejected ---
r = client.post("/drafts/4/reject", json={"reviewer": "Tester", "reason": "Generic message, no personalisation"})
assert r.status_code == 200

# --- 1 edited and approved ---
r = client.post("/drafts/5/edit-approve",
                json={"reviewer": "Tester", "subject": EDITED_SUBJECT, "body": EDITED_BODY})
assert r.status_code == 200

# --- Verify ---
conn = get_conn()
rows = {r["prospect_id"]: dict(r) for r in conn.execute("SELECT * FROM crm_activities")}
total = conn.execute("SELECT COUNT(*) FROM crm_activities").fetchone()[0]
linked = conn.execute(
    """SELECT COUNT(DISTINCT c.prospect_id) FROM crm_activities c
       JOIN audit_trail a ON a.run_id = c.run_id AND a.prospect_id = c.prospect_id"""
).fetchone()[0]
conn.close()

approved = [rows[i] for i in (1, 2, 3) if i in rows]
assert len(approved) == 3, "3 approved emails must be logged"
assert all(r["sent_at"] and r["run_id"] == RUN_ID for r in approved)
assert 4 not in rows, "rejected email must have no CRM row"
assert rows[5]["body"] == EDITED_BODY and rows[5]["email_subject"] == EDITED_SUBJECT
assert total == 4, "approving twice must not create duplicate rows"
assert linked == 4, "every CRM row must link to the audit trail via run_id"
with open("test_sent.log", encoding="utf-8") as f:
    assert f.read().count("[MOCK SEND]") == 4, "exactly 4 emails should be sent"

print(f"Approved 3 -> sent + logged {len(approved)} rows")
print("Rejected 1 -> no CRM row")
print("Edited 1 -> logged with edited body")