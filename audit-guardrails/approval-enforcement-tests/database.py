import sqlite3
from contextlib import contextmanager

DB_PATH = "approval.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS drafts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    company TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT'
        CHECK(status IN ('DRAFT','APPROVED','REJECTED','SENT')),
    reviewer TEXT,
    reject_reason TEXT,
    crm_logged INTEGER NOT NULL DEFAULT 0,
    crm_error TEXT
);

-- one email per draft, enforced by the database (UNIQUE)
CREATE TABLE IF NOT EXISTS sent_emails(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id INTEGER NOT NULL UNIQUE REFERENCES drafts(id),
    run_id TEXT, subject TEXT, body TEXT, sent_at TEXT
);

-- one CRM row per draft, enforced by the database (UNIQUE)
CREATE TABLE IF NOT EXISTS crm_activities(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id INTEGER NOT NULL UNIQUE,
    prospect TEXT, email_subject TEXT, body TEXT, sent_at TEXT, run_id TEXT
);

-- last line of defence: even raw SQL cannot mark a draft SENT unless it was APPROVED
CREATE TRIGGER IF NOT EXISTS only_approved_can_be_sent
BEFORE UPDATE OF status ON drafts
WHEN NEW.status = 'SENT' AND OLD.status <> 'APPROVED'
BEGIN
    SELECT RAISE(ABORT, 'Cannot mark SENT unless APPROVED');
END;
"""


@contextmanager
def get_db():
    """Open, commit (or roll back) and always close, so no lock is ever left open."""
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    with get_db() as con:
        con.executescript(SCHEMA)


def count_rows(table, where="1=1"):
    assert table in ("drafts", "sent_emails", "crm_activities")
    with get_db() as con:
        return con.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]