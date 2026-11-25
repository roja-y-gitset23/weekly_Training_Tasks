# Bonus Challenge: A/B subject lines. Run: python bonustask.py (run research_step.py first)
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, ValidationError, model_validator

RUN_ID = "run_2026_001"
DB_PATH = "research.db"
PROVIDER = os.getenv("LLM_PROVIDER", "mock")          # "mock" or "gemini"
AB_MODE = True   # Bonus task: always generate two subject lines (A/B)
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
    subject: str = Field(min_length=5, max_length=100)                  # Subject A
    subject_b: Optional[str] = Field(default=None, min_length=5, max_length=100)  # Subject B (A/B mode)
    body: str = Field(min_length=50)
    personalisation_points: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def subjects_must_differ(self):
        if self.subject_b and self.subject_b.strip().lower() == self.subject.strip().lower():
            raise ValueError("subject_b must be different from subject")
        return self


# ---------- DB helpers ----------
def now():
    return datetime.now(timezone.utc).isoformat()


def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
            ts TEXT NOT NULL, step TEXT NOT NULL, prospect_id INTEGER, message TEXT);
        DROP TABLE IF EXISTS emails_ab;
        CREATE TABLE emails_ab (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
            prospect_id INTEGER NOT NULL, company TEXT NOT NULL,
            contact_name TEXT NOT NULL, status TEXT NOT NULL,
            subject TEXT, subject_b TEXT, assigned_variant TEXT,
            body TEXT, personalisation_points TEXT,
            created_at TEXT NOT NULL);
    """)
    conn.commit()


def audit(conn, step, message, prospect_id=None):
    conn.execute(
        "INSERT INTO audit_log (run_id, ts, step, prospect_id, message) VALUES (?,?,?,?,?)",
        (RUN_ID, now(), step, prospect_id, message))
    conn.commit()


# ---------- Prompt ----------
def build_prompt(company, contact, industry, notes, feedback=""):
    if AB_MODE:
        subject_rule = ("subject = Version A: benefit-led, states the value. "
                        "subject_b = Version B: curiosity-led, phrased as a question. "
                        "The two subject lines must be clearly different.")
        keys = "subject, subject_b, body, personalisation_points (list of strings)"
    else:
        subject_rule = "subject = one clear subject line."
        keys = "subject, body, personalisation_points (list of strings)"
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
4. {subject_rule} Subject lines must also use only facts from the notes.
5. Return ONLY JSON with keys: {keys}.
{('Fix these problems from your last attempt: ' + feedback) if feedback else ''}"""


# ---------- LLM (mock or Gemini) ----------
def mock_llm(company, contact, industry, notes):
    first = contact.split()[0]
    facts = [f.strip().rstrip(".") for f in notes.split(";")]
    fact = facts[-1][0].lower() + facts[-1][1:]
    body = (f"Hi {first},\n\n"
            f"I came across {company} while researching the {industry.lower()} space "
            f"and noticed this: {fact}.\n\n"
            f"{PITCH}\n\n"
            f"Would a short call next week be useful?\n\n"
            f"Best regards,\n{SENDER}")
    data = {
        "subject": f"A quick idea for {company}",
        "body": body,
        "personalisation_points": facts,
    }
    if AB_MODE:
        data["subject_b"] = f"Is {company} ready for smarter outreach?"
    return json.dumps(data)


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
    text = draft.subject + "\n" + (draft.subject_b or "") + "\n" + draft.body  # both subjects checked

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
            if AB_MODE and not draft.subject_b:
                raise ValueError("subject_b is required in A/B mode")
        except (ValidationError, ValueError) as exc:
            feedback = f"Invalid JSON/schema: {exc}"
            audit(conn, "validation_failed", feedback[:200], pid)
            continue
        problems = check_claims(draft, company, contact, industry, notes)
        if problems:
            feedback = "; ".join(problems)
            audit(conn, "guardrail_failed", feedback[:300], pid)
            continue
        # A/B: alternate the subject line assigned to each recipient (odd id -> A, even id -> B)
        variant = ("A" if pid % 2 else "B") if AB_MODE else None
        conn.execute(
            "INSERT INTO emails_ab (run_id, prospect_id, company, contact_name, status, "
            "subject, subject_b, assigned_variant, body, personalisation_points, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (RUN_ID, pid, company, contact, "DRAFT", draft.subject, draft.subject_b, variant,
             draft.body, json.dumps(draft.personalisation_points), now()))
        conn.commit()
        audit(conn, "draft_saved",
              f"Draft saved with status DRAFT for {company}"
              + (f" (A/B subjects, assigned variant {variant})" if AB_MODE else ""), pid)
        return True
    conn.execute(
        "INSERT INTO emails_ab (run_id, prospect_id, company, contact_name, status, created_at) "
        "VALUES (?,?,?,?,?,?)", (RUN_ID, pid, company, contact, "BLOCKED", now()))
    conn.commit()
    audit(conn, "draft_blocked", f"Guardrail blocked {company} after {MAX_ATTEMPTS} attempts", pid)
    return False


# ---------- Submission files ----------
def write_submission_files(conn):
    rows = conn.execute(
        "SELECT company, contact_name, subject, subject_b, assigned_variant, body, "
        "personalisation_points FROM emails_ab WHERE run_id=? AND status='DRAFT' "
        "ORDER BY prospect_id", (RUN_ID,)).fetchall()

    with open("bonus_sample_drafts.md", "w", encoding="utf-8") as f:
        f.write("# Sample Drafts (3)\n\n")
        for i, (co, contact, subj, subj_b, variant, body, pts) in enumerate(rows[:3], 1):
            f.write(f"## Draft {i}: {co} (to {contact}) - status DRAFT\n\n")
            if AB_MODE:
                f.write(f"**Subject A:** {subj}\n\n**Subject B:** {subj_b}\n\n")
                f.write(f"**Assigned variant:** {variant}\n\n")
            else:
                f.write(f"**Subject:** {subj}\n\n")
            f.write(f"{body}\n\n")
            f.write(f"**Personalisation points:** {', '.join(json.loads(pts))}\n\n---\n\n")

    with open("bonus_rating_table.md", "w", encoding="utf-8") as f:
        f.write("# Rating Table (scale 1-5)\n\n")
        if AB_MODE:
            f.write("| # | Company | Relevance | Tone | Accuracy | Better subject (A/B) | Comment |\n"
                    "|---|---|---|---|---|---|---|\n")
            for i, r in enumerate(rows[:5], 1):
                f.write(f"| {i} | {r[0]} |  |  |  |  |  |\n")
        else:
            f.write("| # | Company | Relevance | Tone | Accuracy | Comment |\n|---|---|---|---|---|---|\n")
            for i, r in enumerate(rows[:5], 1):
                f.write(f"| {i} | {r[0]} |  |  |  |  |\n")
        f.write("\nRubric: Relevance = uses the company's situation; Tone = professional and warm; "
                "Accuracy = every claim is in the research notes (5 = no unsupported claims).\n")


def main():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    audit(conn, "email_step_started",
          f"Drafting emails for {RUN_ID} using provider '{PROVIDER}', A/B mode: {AB_MODE}")

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
    ab_note = "A/B subject lines, " if AB_MODE else ""
    print(f"Drafted {drafted} emails with status DRAFT ({ab_note}{skipped} skipped, no research)")
    print(f"Run id: {RUN_ID}")


if __name__ == "__main__":
    main()