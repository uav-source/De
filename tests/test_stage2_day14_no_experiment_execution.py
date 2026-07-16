from pathlib import Path

from eval import stage2_day14_decision as day14


ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_completes_with_all_experiment_entrypoints_forbidden(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Day 14 invoked a forbidden experiment entrypoint")

    for name in (
        "run_map_lio", "run_day13_calibration", "run_day13_evaluation",
        "run_stage2b", "run_stage2c",
    ):
        monkeypatch.setattr(day14, name, forbidden, raising=False)
    monkeypatch.setattr(day14, "_git_worktree_clean", lambda root: True)
    result = day14.finalize_stage2_day14(
        ROOT,
        ROOT / "configs/stage2/day14_decision.yaml",
        ROOT / "artifacts/current/stage2_day13_analysis_correction_v2",
        tmp_path / "artifact",
        report_path=tmp_path / "report.md",
    )
    assert result["manifest"]["estimator_invoked"] is False
    assert result["manifest"]["calibration_rerun"] is False
    assert result["manifest"]["evaluation_rerun"] is False


def test_script_exposes_only_decision_arguments():
    source = (ROOT / "scripts/40_finalize_stage2_day14.py").read_text()
    for allowed in ("--config", "--day13-v2-dir", "--output-dir", "--overwrite"):
        assert allowed in source
    for forbidden in (
        "--rerun", "--calibration", "--evaluation", "--reserved-test",
        "--retune", "--select-statistic", "--new-threshold", "--stage3",
    ):
        assert forbidden not in source

