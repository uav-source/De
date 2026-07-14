import csv
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import eval.metric_redesign_stage1 as stage1  # noqa: E402


def test_quick_pipeline_preserves_independent_sample_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(stage1, "git_commit", lambda _: "test-commit")
    manifest = stage1.run_stage1(
        tmp_path,
        "quick",
        ROOT / "configs/redesign/stage1_st_sweep.yaml",
        ROOT / "configs/detector/odi_redesign_stage1.yaml",
        ROOT / "configs/toy_lio/motion_surrogate_stage1.yaml",
    )
    assert manifest["status"] == "OK"
    assert manifest["sequence_count"] == 5
    assert manifest["sensor_run_count"] == 5
    assert manifest["process_trial_count"] == 10
    summary = tmp_path / "results/metric_redesign_stage1/tables/sensor_run_summary.csv"
    with summary.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 5
    assert all(int(row["process_trial_count"]) == 2 for row in rows)

