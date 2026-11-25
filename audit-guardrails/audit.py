import csv
import json
from datetime import datetime, timezone
from database import db


class Audit:
    """Writes one row per step with the full schema:
    run_id, timestamp, step, thought, action, action_input, observation, tokens."""

    def __init__(self, run_id, quiet=False):
        self.run_id = run_id
        self.step = 0
        self.quiet = quiet

    def log(self, thought, action, action_input, observation, tokens=None):
        self.step += 1
        ai = action_input if isinstance(action_input, str) else json.dumps(action_input, ensure_ascii=False)
        obs = str(observation)
        if tokens is None:
            # Rough estimate: 4 characters ~ 1 token. Pass real LLM usage here if you have it.
            tokens = max(1, len(thought + action + ai + obs) // 4)
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

        con = db()
        con.execute(
            "INSERT INTO audit_log(run_id,timestamp,step,thought,action,action_input,observation,tokens) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (self.run_id, ts, self.step, thought, action, ai, obs, tokens),
        )
        con.commit()
        con.close()

        if not self.quiet:
            print(f"[{self.run_id}] step {self.step:02d} {action:<16} {obs[:95]}")
        return self.step


def export_audit(run_id, path):
    con = db()
    rows = con.execute(
        "SELECT run_id,timestamp,step,thought,action,action_input,observation,tokens "
        "FROM audit_log WHERE run_id=? ORDER BY step",
        (run_id,),
    ).fetchall()
    con.close()
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["run_id", "timestamp", "step", "thought", "action",
                    "action_input", "observation", "tokens"])
        w.writerows([tuple(r) for r in rows])
    return len(rows)