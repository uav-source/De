from pathlib import Path

import pytest

from eval import stage2_failure_day11b as day11b


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / (
    "results/stage2_failure_analysis/day11a_case_lock/"
    "stage2_failure_day11a_case_lock_v1/deterministic_diagnostic_case_lock.json"
)


def test_verify_v2_regenerates_byte_identical_plan_without_estimator(tmp_path, monkeypatch):
    monkeypatch.setattr(day11b, "git_status_clean", lambda root: True)
    monkeypatch.setattr(
        day11b, "run_map_lio",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("estimator called")),
    )
    result = day11b.verify_lock_and_write_plan(
        ROOT, LOCK, "stage2_failure_day11b_replay_v2", tmp_path
    )
    assert result["v1_v2_replay_plan_byte_identical"] is True
    assert result["estimator_run"] is False


def test_v2_output_path_pointing_at_frozen_v1_is_rejected(monkeypatch):
    monkeypatch.setattr(day11b, "git_status_clean", lambda root: True)
    output_root = ROOT / "results/stage2_failure_analysis/day11b_replay"
    with pytest.raises(ValueError, match="frozen v1"):
        day11b.verify_lock_and_write_plan(
            ROOT, LOCK, "stage2_failure_day11b_replay_v1", output_root, overwrite=True
        )


def test_dirty_worktree_stops_before_v2_output_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(day11b, "git_status_clean", lambda root: False)
    with pytest.raises(RuntimeError, match="clean worktree"):
        day11b.verify_lock_and_write_plan(ROOT, LOCK, "dirty_v2", tmp_path)
    assert not (tmp_path / "dirty_v2").exists()
