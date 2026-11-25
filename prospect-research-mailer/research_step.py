import asyncio
import random
import sqlite3
from datetime import datetime, timezone

RUN_ID = "run_2026_001"
DB_PATH = "research.db"
CONCURRENCY = 3

# 10 prospects; "Ghost Industries" has no search result
PROSPECTS = [
    (1, "Acme Corp"),
    (2, "Globex Ltd"),
    (3, "Initech"),
    (4, "Umbrella Systems"),
    (5, "Ghost Industries"),   # -> no result
    (6, "Hooli"),
    (7, "Stark Solutions"),
    (8, "Wayne Enterprises"),
    (9, "Wonka Foods"),
    (10, "Cyberdyne Tech"),
]

MOCK_SEARCH_DB = {
    "Acme Corp": "Manufacturer of industrial tools; expanding into Asia.",
    "Globex Ltd": "Global logistics firm; recently raised Series C.",
    "Initech": "Enterprise software vendor; new CTO hired in 2026.",
    "Umbrella Systems": "Healthcare IT provider; launched a cloud platform.",
    "Hooli": "Consumer tech company; investing in AI products.",
    "Stark Solutions": "Clean-energy hardware; announced a new factory.",
    "Wayne Enterprises": "Diversified conglomerate; focus on security tech.",
    "Wonka Foods": "Confectionery maker; entering the e-commerce market.",
    "Cyberdyne Tech": "Robotics company; hiring across engineering roles.",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS research (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            prospect_id INTEGER NOT NULL,
            company TEXT NOT NULL,
            status TEXT NOT NULL,          -- 'researched' or 'no research'
            notes TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            step TEXT NOT NULL,
            prospect_id INTEGER,
            message TEXT
        );
    """)
    # Make the script re-runnable: clear old data for this run_id
    conn.execute("DELETE FROM research WHERE run_id = ?", (RUN_ID,))
    conn.execute("DELETE FROM audit_log WHERE run_id = ?", (RUN_ID,))
    conn.commit()


def audit(conn, step, message, prospect_id=None):
    conn.execute(
        "INSERT INTO audit_log (run_id, ts, step, prospect_id, message) VALUES (?,?,?,?,?)",
        (RUN_ID, now(), step, prospect_id, message),
    )
    conn.commit()


async def mock_web_search(company):
    """Mock web search: returns notes or None when nothing is found."""
    await asyncio.sleep(random.uniform(0.1, 0.4))
    return MOCK_SEARCH_DB.get(company)


async def research_prospect(conn, sem, prospect):
    pid, company = prospect
    async with sem:  # concurrency limit of 3
        audit(conn, "research_started", f"Researching {company}", pid)
        try:
            audit(conn, "search_called", f"Mock web search for '{company}'", pid)
            notes = await mock_web_search(company)

            if notes:
                conn.execute(
                    "INSERT INTO research (run_id, prospect_id, company, status, notes, created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (RUN_ID, pid, company, "researched", notes, now()),
                )
                conn.commit()
                audit(conn, "research_saved", f"Saved research for {company}", pid)
                return True
            else:
                conn.execute(
                    "INSERT INTO research (run_id, prospect_id, company, status, notes, created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (RUN_ID, pid, company, "no research", None, now()),
                )
                conn.commit()
                audit(conn, "no_research", f"No search result for {company}; continuing", pid)
                return False
        except Exception as exc:  # never stop the whole run for one prospect
            conn.execute(
                "INSERT INTO research (run_id, prospect_id, company, status, notes, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (RUN_ID, pid, company, "no research", None, now()),
            )
            conn.commit()
            audit(conn, "research_error", f"{company}: {exc}", pid)
            return False


async def main():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    audit(conn, "run_started", f"Run {RUN_ID} started with {len(PROSPECTS)} prospects")

    sem = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(
        *(research_prospect(conn, sem, p) for p in PROSPECTS)
    )

    done = sum(1 for r in results if r)
    total = len(PROSPECTS)
    missing = total - done
    audit(conn, "run_completed", f"Researched {done}/{total} ({missing} no result)")
    conn.close()

    print(f"Researched {done}/{total} prospects ({missing} no result)")
    print(f"Run id: {RUN_ID}")


if __name__ == "__main__":
    asyncio.run(main())