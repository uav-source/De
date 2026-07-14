import csv
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import eval.metric_redesign_stage1b as stage1b  # noqa: E402
from stage1b_helpers import stage1b_paths  # noqa: E402


def test_stage1b_quick_pipeline_has_nine_sensor_runs_and_twenty_seven_trials(tmp_path, monkeypatch):
    monkeypatch.setattr(stage1b, "git_commit", lambda _root: "test-commit")
    paths = stage1b_paths()
    manifest = stage1b.run_stage1b(
        tmp_path,
        "quick",
        paths["common"],
        paths["geometry"],
        paths["observation"],
        paths["detector"],
        paths["motion"],
        run_id="quick_test",
        workers=2,
    )
    assert manifest["status"] == "OK"
    assert manifest["sensor_run_count"] == 9
    assert manifest["process_trial_count"] == 27
    summary = tmp_path / "results/metric_redesign_stage1b/quick/quick_test/tables/sensor_run_summary.csv"
    with summary.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 9
    assert all(int(row["process_trial_count"]) == 3 for row in rows)
