from datetime import datetime, timezone
from .db import execute


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(run_id, step, thought, action, action_input, observation, tokens=0):
    execute(
        "INSERT INTO audit_log(run_id,timestamp,step,thought,action,action_input,observation,tokens)"
        " VALUES(?,?,?,?,?,?,?,?)",
        (run_id, now(), step, thought, action, str(action_input)[:300],
         str(observation)[:300], tokens),
    )