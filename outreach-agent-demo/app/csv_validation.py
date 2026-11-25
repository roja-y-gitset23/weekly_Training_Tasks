import csv
import re
from pathlib import Path

REQUIRED = ["name", "email", "company", "industry"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CSVValidationError(Exception):
    pass


def validate_csv(path):
    p = Path(path)
    if not p.exists():
        raise CSVValidationError(f"File not found: {p}")
    if p.suffix.lower() != ".csv":
        raise CSVValidationError("Input must be a .csv file")

    rows, seen = [], set()
    try:
        with open(p, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            missing = [c for c in REQUIRED if c not in headers]
            if missing:
                raise CSVValidationError(f"Missing columns: {missing}")
            for line_no, row in enumerate(reader, start=2):
                clean = {c: (row.get(c) or "").strip() for c in REQUIRED}
                for c, v in clean.items():
                    if not v:
                        raise CSVValidationError(f"Line {line_no}: '{c}' is empty")
                if not EMAIL_RE.match(clean["email"]):
                    raise CSVValidationError(f"Line {line_no}: invalid email")
                key = clean["email"].lower()
                if key in seen:
                    raise CSVValidationError(f"Line {line_no}: duplicate email")
                seen.add(key)
                rows.append(clean)
    except UnicodeDecodeError:
        raise CSVValidationError("File is not valid UTF-8 text")

    if not rows:
        raise CSVValidationError("CSV has no data rows")
    return rows