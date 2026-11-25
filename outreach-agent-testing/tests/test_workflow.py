from app.workflow import run_workflow


def test_full_run_10_prospects(tmp_path):
    s = run_workflow("data/prospects.csv", results_dir=tmp_path)
    assert s["prospects"] == 10 and s["drafts"] == 10
    assert s["no_research"] == 1
    assert s["rejected"] == 1          # the "100% savings" draft
    assert s["sent"] == s["approved"] == 9
    assert s["blocked_at_send"] == 0
    assert (tmp_path / "run_summary.md").exists()