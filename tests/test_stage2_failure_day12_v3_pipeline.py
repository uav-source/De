from pathlib import Path

import pytest

from eval import stage2_failure_day12 as day12


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2"
V2 = ROOT / "results/stage2_failure_analysis/day12_figures/stage2_failure_day12_figures_v2"


def test_v3_pipeline_generates_only_hardened_figures_from_frozen_input(tmp_path, monkeypatch):
    monkeypatch.setattr(day12, "git_status_clean", lambda root: True)
    manifest = day12.generate_day12_figures(ROOT, RUN, "v3", tmp_path)
    output = tmp_path / "v3"
    assert manifest["DAY12_DIAGNOSTIC_FIGURES_PASS"] is True
    assert manifest["DAY12_V3_AXIS_CONTRACT_PASS"] is True
    assert manifest["DAY12_V3_INPUT_LOCK_PASS"] is True
    assert manifest["v2_v3_plot_data_byte_identical"] is True
    assert (output / "axis_contract_audit.json").is_file()
    assert (output / "day12_v2_v3_data_equivalence.json").is_file()
    assert (output / "day12_v2_v3_figure_change_audit.json").is_file()
    assert (output / "day12_v3_summary.json").is_file()


def test_dirty_worktree_stops_v3_before_output(tmp_path, monkeypatch):
    monkeypatch.setattr(day12, "git_status_clean", lambda root: False)
    with pytest.raises(RuntimeError, match="clean worktree"):
        day12.generate_day12_figures(ROOT, RUN, "dirty-v3", tmp_path)
    assert not (tmp_path / "dirty-v3").exists()


def test_v3_cannot_overwrite_v2_and_has_no_estimator_call(tmp_path, monkeypatch):
    monkeypatch.setattr(day12, "git_status_clean", lambda root: True)
    with pytest.raises(ValueError, match="Day 12 v2"):
        day12.verify_day12_input(ROOT, RUN, V2.name, V2.parent)
    source = (ROOT / "src/eval/stage2_failure_day12.py").read_text(encoding="utf-8")
    assert "run_map_lio" not in source
