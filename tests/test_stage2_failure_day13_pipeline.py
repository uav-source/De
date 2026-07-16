from pathlib import Path

import pytest

from eval import stage2_failure_day13 as day13


def test_design_entrypoint_never_invokes_estimator(tmp_path, monkeypatch):
    monkeypatch.setattr(day13, "_validate_day12_precondition", lambda root: True)
    monkeypatch.setattr(day13, "create_design_lock", lambda *args, **kwargs: {"estimator_run": False})
    monkeypatch.setattr(day13, "run_map_lio", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("estimator called")))
    assert day13.lock_day13_design(tmp_path, "design", tmp_path)["estimator_run"] is False


def test_dirty_calibration_refuses_before_work(tmp_path, monkeypatch):
    monkeypatch.setattr(day13, "git_status_clean", lambda root: False)
    with pytest.raises(RuntimeError, match="clean worktree"):
        day13.run_day13_calibration(tmp_path, tmp_path / "lock.json", "run", tmp_path)


def test_calibration_lock_refuses_existing_evaluation_directory(tmp_path, monkeypatch):
    run = tmp_path / "run"
    (run / "evaluation").mkdir(parents=True)
    monkeypatch.setattr(day13, "git_status_clean", lambda root: True)
    monkeypatch.setattr(day13, "validate_design_lock", lambda root, path: {})
    monkeypatch.setattr(day13, "git_path_commit", lambda root, path: "a" * 40)
    with pytest.raises(RuntimeError, match="evaluation directory"):
        day13.lock_day13_calibration(tmp_path, tmp_path / "design.json", "run", tmp_path)


def test_evaluation_before_calibration_lock_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(day13, "git_status_clean", lambda root: True)
    monkeypatch.setattr(day13, "_validate_day12_precondition", lambda root: True)
    monkeypatch.setattr(day13, "validate_design_lock", lambda root, path: {})
    with pytest.raises(FileNotFoundError):
        day13.run_day13_evaluation(tmp_path, tmp_path / "design.json", tmp_path / "missing.json", "run", tmp_path)
