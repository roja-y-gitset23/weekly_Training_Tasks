import json
import time
from datetime import datetime
from pathlib import Path

from .csv_validation import validate_csv
from .risk import Risk, RiskPolicyError, assess_risk
from .state_machine import Draft, State, send_draft

# Edit these to match your model's real pricing (USD per token)
PRICE_IN = 0.10 / 1_000_000
PRICE_OUT = 0.40 / 1_000_000

PITCH = "We help teams cut manual reporting time with an automated reporting assistant."

MOCK_RESEARCH = {
    "Acme Logistics": "Acme Logistics recently expanded to three new regional hubs.",
    "BrightPath Health": "BrightPath Health opened a telehealth service this year.",
    "Cedar Finance": "Cedar Finance is advertising a discount program for small firms.",
    "Delta Foods": "Delta Foods launched a new line of organic snacks.",
    "Evergreen Energy": "Evergreen Energy announced a solar partnership.",
    "Falcon Retail": "Falcon Retail guarantees 100% savings for its customers.",
    "Granite Builders": "Granite Builders won a municipal housing contract.",
    "Harbor Tech": "Harbor Tech is hiring data engineers.",
    "Ionic Media": "Ionic Media launched a podcast network.",
    # "Zeta Textiles" has no entry -> no research
}


def count_tokens(text):
    return max(1, len(text) // 4)


def make_draft(prospect):
    notes = MOCK_RESEARCH.get(prospect["company"])
    first = prospect["name"].split()[0]
    if notes:
        opener = f"I noticed that {notes}"
    else:
        opener = f"I would love to learn how {prospect['company']} works in {prospect['industry']}."
    subject = f"Idea for {prospect['company']}"
    body = f"Hi {first},\n\n{opener}\n\n{PITCH}\n\nBest regards,\nAlex"
    prompt = f"Research: {notes}\nContact: {prospect['name']}\nIndustry: {prospect['industry']}\nPitch: {PITCH}"
    tokens_in = count_tokens(prompt)
    tokens_out = count_tokens(subject + body)
    draft = Draft(prospect["email"], prospect["company"], subject, body,
                  assess_risk(subject, body))
    return draft, tokens_in, tokens_out, notes is None


def simulate_review(drafts):
    """Stands in for the human approval UI."""
    edited_done = False
    for d in drafts:
        if d.risk == Risk.HIGH:
            d.transition(State.REJECTED, reviewer="reviewer1",
                         reason="High risk: unsupported claim or sensitive content")
            continue
        if not edited_done:
            d.body += "\n\nP.S. Happy to share a short case study."
            d.edited = True
            d.risk = assess_risk(d.subject, d.body)
            edited_done = True
        d.transition(State.APPROVED, reviewer="reviewer1")


def run_workflow(csv_path, results_dir="results"):
    start = time.perf_counter()
    prospects = validate_csv(csv_path)
    drafts, t_in, t_out, no_research = [], 0, 0, 0
    for p in prospects:
        d, i, o, missing = make_draft(p)
        drafts.append(d)
        t_in += i
        t_out += o
        no_research += int(missing)

    simulate_review(drafts)

    sent, blocked = 0, 0
    for d in drafts:
        if d.state == State.APPROVED:
            try:
                send_draft(d)
                sent += 1
            except RiskPolicyError:
                blocked += 1

    rejected = sum(d.state == State.REJECTED for d in drafts)
    summary = {
        "run_id": f"run_{datetime.now():%Y%m%d_%H%M%S}",
        "prospects": len(prospects),
        "no_research": no_research,
        "drafts": len(drafts),
        "approved": len(drafts) - rejected,
        "edited": sum(d.edited for d in drafts),
        "rejected": rejected,
        "sent": sent,
        "blocked_at_send": blocked,
        "tokens_in": t_in,
        "tokens_out": t_out,
        "cost_usd": round(t_in * PRICE_IN + t_out * PRICE_OUT, 6),
        "time_seconds": round(time.perf_counter() - start, 3),
    }

    out = Path(results_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "run_summary.json").write_text(json.dumps(summary, indent=2))
    rows = "\n".join(f"| {k} | {v} |" for k, v in summary.items())
    (out / "run_summary.md").write_text(f"| Metric | Value |\n|---|---|\n{rows}\n")
    return summary