from pathlib import Path

from eval import stage2_failure_day11b as day11b


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "results/stage2_failure_analysis/day11a_case_lock/stage2_failure_day11a_case_lock_v1/deterministic_diagnostic_case_lock.json"


def test_verify_only_pipeline_writes_plan_without_running_estimator(tmp_path, monkeypatch):
    monkeypatch.setattr(day11b, "git_status_clean", lambda root: True)
    monkeypatch.setattr(
        day11b, "run_map_lio",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("estimator called")),
    )
    result = day11b.verify_lock_and_write_plan(
        ROOT, LOCK, "verify_only", tmp_path
    )
    output = tmp_path / "verify_only"
    assert result["estimator_run"] is False
    assert result["replay_plan_row_count"] == 8
    assert (output / "case_lock_verification.json").is_file()
    assert (output / "replay_plan.csv").is_file()
    assert (output / "replay_plan.json").is_file()


def test_dirty_worktree_refuses_before_output_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(day11b, "git_status_clean", lambda root: False)
    try:
        day11b.verify_lock_and_write_plan(ROOT, LOCK, "dirty", tmp_path)
    except RuntimeError as error:
        assert "clean worktree" in str(error)
    else:
        raise AssertionError("dirty worktree was accepted")
    assert not (tmp_path / "dirty").exists()
