from pathlib import Path
import pytest
from eval import stage2_failure_day12 as day12

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2"


def test_verify_mode_writes_lock_but_no_figures(tmp_path, monkeypatch):
    monkeypatch.setattr(day12, "git_status_clean", lambda root: True)
    result = day12.verify_day12_input(ROOT, RUN, "verify", tmp_path)
    output = tmp_path / "verify"
    assert result["DAY12_INPUT_AUDIT_PASS"] is True
    assert not (output / "figures").exists()
    assert (output / "day12_input_lock.json").is_file()


def test_dirty_worktree_stops_before_output(tmp_path, monkeypatch):
    monkeypatch.setattr(day12, "git_status_clean", lambda root: False)
    with pytest.raises(RuntimeError, match="clean worktree"):
        day12.verify_day12_input(ROOT, RUN, "dirty", tmp_path)
    assert not (tmp_path / "dirty").exists()


def test_output_inside_day11b_tree_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(day12, "git_status_clean", lambda root: True)
    with pytest.raises(ValueError, match="may not modify"):
        day12.verify_day12_input(ROOT, RUN, "child", RUN)


def test_non_descendant_head_stops_before_output(tmp_path, monkeypatch):
    monkeypatch.setattr(day12, "git_status_clean", lambda root: True)
    monkeypatch.setattr(day12, "_git_ancestor", lambda root, first, second: False)
    with pytest.raises(RuntimeError, match="does not descend"):
        day12.verify_day12_input(ROOT, RUN, "wrong-head", tmp_path)
    assert not (tmp_path / "wrong-head").exists()
