import sqlite3
from config import DB


def db():
    return sqlite3.connect(DB)


def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS audit_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL, timestamp TEXT NOT NULL, step INTEGER NOT NULL,
        thought TEXT, action TEXT, action_input TEXT, observation TEXT, tokens INTEGER);
    CREATE TABLE IF NOT EXISTS runs(
        seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, user_id TEXT, status TEXT);
    CREATE TABLE IF NOT EXISTS run_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, ts REAL);
    CREATE TABLE IF NOT EXISTS research(run_id TEXT, company TEXT, notes TEXT, status TEXT);
    CREATE TABLE IF NOT EXISTS drafts(run_id TEXT, company TEXT, subject TEXT, body TEXT, status TEXT);
    """)
    con.commit()
    con.close()


def set_status(run_id, status):
    con = db()
    con.execute("UPDATE runs SET status=? WHERE run_id=?", (status, run_id))
    con.commit()
    con.close()


def status_of(run_id):
    con = db()
    row = con.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()
    con.close()
    return row[0] if row else None