import os
import sqlite3


def get_db_path():
    return os.environ.get("APPROVAL_DB", "approval.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    prospect_id INTEGER,
    company TEXT NOT NULL,
    research_summary TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT'
        CHECK (status IN ('DRAFT','APPROVED','REJECTED','SENT')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS draft_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id INTEGER NOT NULL REFERENCES drafts(id),
    decision TEXT NOT NULL
        CHECK (decision IN ('APPROVED','EDITED_APPROVED','REJECTED')),
    reviewer TEXT NOT NULL,
    reason TEXT,
    decided_at TEXT NOT NULL,
    original_subject TEXT,
    original_body TEXT,
    final_subject TEXT,
    final_body TEXT
);

-- Mock CRM table. UNIQUE(prospect_id, run_id) makes logging idempotent.
CREATE TABLE IF NOT EXISTS crm_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL,
    email_subject TEXT NOT NULL,
    body TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    run_id TEXT NOT NULL,
    UNIQUE (prospect_id, run_id)
);

-- Audit trail, linked to CRM rows through run_id
CREATE TABLE IF NOT EXISTS audit_trail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step TEXT NOT NULL,
    prospect_id INTEGER,
    actor TEXT,
    detail TEXT,
    created_at TEXT NOT NULL
);

-- Database-level guard: a row can only become SENT from APPROVED
CREATE TRIGGER IF NOT EXISTS block_send_unless_approved
BEFORE UPDATE OF status ON drafts
WHEN NEW.status = 'SENT' AND OLD.status != 'APPROVED'
BEGIN
    SELECT RAISE(ABORT, 'Cannot send: draft status is not APPROVED');
END;

CREATE TRIGGER IF NOT EXISTS block_insert_as_sent
BEFORE INSERT ON drafts
WHEN NEW.status = 'SENT'
BEGIN
    SELECT RAISE(ABORT, 'Cannot create a draft directly as SENT');
END;
"""


def get_conn():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    # Upgrade an older Task 1 database that has no prospect_id column
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(drafts)")]
    if "prospect_id" not in cols:
        conn.execute("ALTER TABLE drafts ADD COLUMN prospect_id INTEGER")
    conn.execute("UPDATE drafts SET prospect_id = id WHERE prospect_id IS NULL")
    conn.commit()
    conn.close()
    