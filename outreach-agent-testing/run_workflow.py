from app.workflow import run_workflow

if __name__ == "__main__":
    s = run_workflow("data/prospects.csv")
    print("| Metric | Value |\n|---|---|")
    for k, v in s.items():
        print(f"| {k} | {v} |")