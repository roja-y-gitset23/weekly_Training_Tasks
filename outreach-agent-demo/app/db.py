import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path("demo.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY, created_at TEXT, status TEXT,
    total INTEGER DEFAULT 0, done INTEGER DEFAULT 0,
    tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0,
    cost REAL DEFAULT 0, note TEXT
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT,
    prospect_name TEXT, email TEXT, company TEXT, industry TEXT,
    research TEXT, subject TEXT, body TEXT, risk TEXT, status TEXT,
    reviewer TEXT, reason TEXT, edited INTEGER DEFAULT 0, created_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, timestamp TEXT,
    step TEXT, thought TEXT, action TEXT, action_input TEXT,
    observation TEXT, tokens INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS crm_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT, draft_id INTEGER UNIQUE,
    run_id TEXT, prospect_email TEXT, email_subject TEXT, body TEXT, sent_at TEXT
);
"""


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)


def query(sql, params=()):
    with db() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def execute(sql, params=()):
    with db() as c:
        return c.execute(sql, params).lastrowid