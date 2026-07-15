import json
from pathlib import Path

from eval import stage2_failure_day11a as day11a


ROOT = Path(__file__).resolve().parents[1]


def test_complete_day11a_pipeline_never_calls_runtime_components(tmp_path, monkeypatch):
    def forbidden_call(*args, **kwargs):
        raise AssertionError("Day 11A attempted to execute a forbidden runtime")

    for name in (
        "run_map_lio",
        "Stage2FailureOnlineLogger",
        "evaluate_stage2_failure_gt",
        "compute_window_records",
        "run_stage2c",
    ):
        monkeypatch.setattr(day11a, name, forbidden_call, raising=False)
    monkeypatch.setattr(day11a, "git_status_clean", lambda root: True)
    manifest = day11a.run_stage2_failure_day11a(
        ROOT,
        "no_replay",
        tmp_path,
    )
    assert manifest["DAY11A_CASE_LOCK_PASS"] is True
    assert manifest["replay_performed"] is False
    assert manifest["estimator_imported"] is False
    assert manifest["gt_evaluator_imported"] is False
    assert manifest["window_statistics_imported"] is False
    output = tmp_path / "no_replay"
    forbidden_outputs = {
        "cases",
        "frame_diagnostics_online.csv",
        "frame_diagnostics_gt.csv",
        "frame_window_statistics.csv",
        "trajectory_metrics.json",
        "figures",
        "thresholds",
        "roc",
        "alerts",
    }
    assert not ({path.name for path in output.iterdir()} & forbidden_outputs)
    lock = json.loads(
        (output / "deterministic_diagnostic_case_lock.json").read_text()
    )
    assert lock["gross_outlier_control_replayed"] is False
    assert lock["stress_name_alias_used"] is False
    assert lock["legacy_stage2b_stress_name_used"] is False
