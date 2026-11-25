import subprocess
import sys
from datetime import datetime

HEADER = """APPROVAL ENFORCEMENT TEST REPORT
Generated: {now}

Requirement                                          Tests
---------------------------------------------------  --------------------
Sender cannot send a non-approved draft              A1 - A6
API bypass (send without approval) returns 403       B1 - B6
Restart safety, no duplicate emails                  C1, C2
Mock CRM down -> email not marked as logged          D1 - D3

"""


def main():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "--tb=short", "-p", "no:cacheprovider"],
        capture_output=True, text=True, encoding="utf-8")
    report = HEADER.format(now=datetime.now().strftime("%Y-%m-%d %H:%M")) + proc.stdout + proc.stderr
    with open("test_report.txt", "w", encoding="utf-8") as f:
        f.write(report)
    sys.stdout.reconfigure(errors="replace")
    print(report)
    print("Report saved: test_report.txt")
    sys.exit(proc.returncode)


if __name__ == "__main__":
    main()