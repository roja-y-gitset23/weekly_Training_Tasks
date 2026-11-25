import json
import os
import re
import sqlite3
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ValidationError

RUN_ID = "run_2026_001"
DB_PATH = "research.db"
PROVIDER = os.getenv("LLM_PROVIDER", "mock")   # "mock" or "gemini"
MAX_ATTEMPTS = 3
SENDER = "Alex"

# Fixed company pitch (used in every email)
PITCH = ("Northwind Insights helps B2B sales teams turn customer data into "
         "personalised outreach, with every email reviewed by a human before sending.")

# Contact name and industry for each prospect
CONTACTS = {
    "Acme Corp": ("Rita Sharma", "Manufacturing"),
    "Globex Ltd": ("Dan Miller", "Logistics"),
    "Initech": ("Priya Nair", "Enterprise Software"),
    "Umbrella Systems": ("Tom Becker", "Healthcare IT"),
    "Ghost Industries": ("Sam Lee", "Unknown"),
    "Hooli": ("Anita Rao", "Consumer Technology"),
    "Stark Solutions": ("Carlos Diaz", "Clean Energy"),
    "Wayne Enterprises": ("Meera Iyer", "Conglomerate"),
    "Wonka Foods": ("John Doe", "Food and Beverage"),
    "Cyberdyne Tech": ("Lena Fischer", "Robotics"),
}


# ---------- Pydantic structured output ----------
class EmailDraft(BaseModel):
    subject: str = Field(min_length=5, max_length=100)
    body: str = Field(min_length=50)
    personalisation_points: list[str] = Field(min_length=1)


# ---------- DB helpers ----------
def now():
    return datetime.now(timezone.utc).isoformat()


def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
            ts TEXT NOT NULL, step TEXT NOT NULL, prospect_id INTEGER, message TEXT);
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
            prospect_id INTEGER NOT NULL, company TEXT NOT NULL,
            contact_name TEXT NOT NULL, status TEXT NOT NULL,
            subject TEXT, body TEXT, personalisation_points TEXT,
            created_at TEXT NOT NULL);
    """)
    conn.execute("DELETE FROM emails WHERE run_id = ?", (RUN_ID,))  # re-runnable
    conn.commit()


def audit(conn, step, message, prospect_id=None):
    conn.execute(
        "INSERT INTO audit_log (run_id, ts, step, prospect_id, message) VALUES (?,?,?,?,?)",
        (RUN_ID, now(), step, prospect_id, message))
    conn.commit()


# ---------- Prompt ----------
def build_prompt(company, contact, industry, notes, feedback=""):
    return f"""You are a sales assistant writing a short, friendly outreach email.

Contact name: {contact}
Company: {company}
Industry: {industry}
Research notes (the ONLY facts you may use about the company):
\"\"\"{notes}\"\"\"
Our fixed company pitch: \"\"\"{PITCH}\"\"\"
Sender: {SENDER}

Rules:
1. Use ONLY facts from the research notes. Do NOT invent numbers, awards, customers or events.
2. personalisation_points: copy the exact phrases from the notes you used.
3. Tone: professional and warm, under 120 words, end with a soft call to action.
4. Return ONLY JSON with keys: subject, body, personalisation_points (list of strings).
{('Fix these problems from your last attempt: ' + feedback) if feedback else ''}"""


# ---------- LLM (mock or Gemini) ----------
def mock_llm(company, contact, industry, notes):
    first = contact.split()[0]
    facts = [f.strip().rstrip(".") for f in notes.split(";")]
    fact = facts[-1][0].lower() + facts[-1][1:]
    body = (f"Hi {first},\n\n"
            f"I came across {company} while researching the {industry.lower()} space "
            f"and noticed that {fact}.\n\n"
            f"{PITCH}\n\n"
            f"Would a short call next week be useful?\n\n"
            f"Best regards,\n{SENDER}")
    return json.dumps({
        "subject": f"A quick idea for {company}",
        "body": body,
        "personalisation_points": facts,
    })


def gemini_llm(prompt):
    from google import genai   # pip install google-genai
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    r = client.models.generate_content(
        model="gemini-2.0-flash", contents=prompt,
        config={"response_mime_type": "application/json"})
    return r.text


def call_llm(company, contact, industry, notes, feedback=""):
    if PROVIDER == "gemini":
        return gemini_llm(build_prompt(company, contact, industry, notes, feedback))
    return mock_llm(company, contact, industry, notes)


# ---------- Guardrail: no claims outside the research notes ----------
def norm(text):
    return re.sub(r"[^a-z0-9 ]", "", text.lower())


def check_claims(draft, company, contact, industry, notes):
    problems = []
    source = " ".join([notes, PITCH, company, contact, industry, SENDER])
    source_words = set(re.findall(r"[a-z0-9]+", source.lower()))
    text = draft.subject + "\n" + draft.body

    # 1. every personalisation point must come from the notes
    for p in draft.personalisation_points:
        if norm(p) not in norm(notes):
            problems.append(f"personalisation point not in notes: '{p}'")

    # 2. every number must exist in the notes or pitch
    for n in re.findall(r"\d+(?:[.,]\d+)*", text):
        if n not in source:
            problems.append(f"unsupported number: {n}")

    # 3. capitalised words (names/brands) mid-sentence must exist in the sources
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        for w in re.findall(r"\b[A-Z][A-Za-z]+\b", " ".join(sentence.split()[1:])):
            if w.lower() not in source_words:
                problems.append(f"unsupported name/term: {w}")
    return problems


# ---------- Draft one prospect ----------
def draft_prospect(conn, pid, company, notes):
    contact, industry = CONTACTS.get(company, ("there", "your industry"))
    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        audit(conn, "draft_attempt", f"{company} attempt {attempt}", pid)
        try:
            raw = call_llm(company, contact, industry, notes, feedback)
            draft = EmailDraft.model_validate_json(raw)          # Pydantic validation
        except (ValidationError, ValueError) as exc:
            feedback = f"Invalid JSON/schema: {exc}"
            audit(conn, "validation_failed", feedback[:200], pid)
            continue
        problems = check_claims(draft, company, contact, industry, notes)
        if problems:
            feedback = "; ".join(problems)
            audit(conn, "guardrail_failed", feedback[:300], pid)
            continue
        conn.execute(
            "INSERT INTO emails (run_id, prospect_id, company, contact_name, status, "
            "subject, body, personalisation_points, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (RUN_ID, pid, company, contact, "DRAFT", draft.subject, draft.body,
             json.dumps(draft.personalisation_points), now()))
        conn.commit()
        audit(conn, "draft_saved", f"Draft saved with status DRAFT for {company}", pid)
        return True
    conn.execute(
        "INSERT INTO emails (run_id, prospect_id, company, contact_name, status, created_at) "
        "VALUES (?,?,?,?,?,?)", (RUN_ID, pid, company, contact, "BLOCKED", now()))
    conn.commit()
    audit(conn, "draft_blocked", f"Guardrail blocked {company} after {MAX_ATTEMPTS} attempts", pid)
    return False


# ---------- Submission files ----------
def write_submission_files(conn):
    rows = conn.execute(
        "SELECT company, contact_name, subject, body, personalisation_points "
        "FROM emails WHERE run_id=? AND status='DRAFT' ORDER BY prospect_id", (RUN_ID,)).fetchall()

    with open("sample_drafts.md", "w", encoding="utf-8") as f:
        f.write("# Sample Drafts (3)\n\n")
        for i, (co, contact, subj, body, pts) in enumerate(rows[:3], 1):
            f.write(f"## Draft {i}: {co} (to {contact}) - status DRAFT\n\n")
            f.write(f"**Subject:** {subj}\n\n{body}\n\n")
            f.write(f"**Personalisation points:** {', '.join(json.loads(pts))}\n\n---\n\n")

    with open("rating_table.md", "w", encoding="utf-8") as f:
        f.write("# Rating Table (scale 1-5)\n\n")
        f.write("| # | Company | Relevance | Tone | Accuracy | Comment |\n|---|---|---|---|---|---|\n")
        for i, r in enumerate(rows[:5], 1):
            f.write(f"| {i} | {r[0]} |  |  |  |  |\n")
        f.write("\nRubric: Relevance = uses the company's situation; Tone = professional and warm; "
                "Accuracy = every claim is in the research notes (5 = no unsupported claims).\n")


def main():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    audit(conn, "email_step_started", f"Drafting emails for {RUN_ID} using provider '{PROVIDER}'")

    rows = conn.execute(
        "SELECT prospect_id, company, status, notes FROM research WHERE run_id=? ORDER BY prospect_id",
        (RUN_ID,)).fetchall()
    if not rows:
        raise SystemExit("No research found. Run research_step.py first.")

    drafted = skipped = 0
    for pid, company, status, notes in rows:
        if status != "researched" or not notes:
            audit(conn, "draft_skipped", f"No research for {company}; no email drafted", pid)
            skipped += 1
            continue
        if draft_prospect(conn, pid, company, notes):
            drafted += 1

    audit(conn, "email_step_completed", f"Drafted {drafted}, skipped {skipped}")
    write_submission_files(conn)
    conn.close()
    print(f"Drafted {drafted} emails with status DRAFT ({skipped} skipped, no research)")
    print(f"Run id: {RUN_ID}")


if __name__ == "__main__":
    main()