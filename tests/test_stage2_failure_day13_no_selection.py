from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_has_no_statistic_or_threshold_selection_api():
    source = (ROOT / "scripts/38_run_stage2_failure_day13.py").read_text()
    for forbidden in ("--select-statistic", "--select-threshold", "--retune", "--final-decision", "--stage3"):
        assert forbidden not in source
