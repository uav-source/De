import csv
import json
from pathlib import Path

import numpy as np
import pytest

from eval import stage2_failure_day8 as day8
from eval.stage2_failure_schema import FRAME_KEY_FIELDS


ROOT = Path(__file__).resolve().parents[1]


def test_day8_quick_writes_isolated_joinable_logs_and_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(day8, "git_status_clean", lambda root: True)
    manifest = day8.run_stage2_failure_day8(
        ROOT,
        "pytest_day8_quick",
        tmp_path,
    )
    output = tmp_path / "pytest_day8_quick"
    online_path = output / "frame_diagnostics_online.csv"
    gt_path = output / "frame_diagnostics_gt.csv"
    manifest_path = output / "run_manifest.json"
    summary_path = output / "day8_quick_summary.json"
    assert all(path.exists() for path in [online_path, gt_path, manifest_path, summary_path])

    with online_path.open(newline="", encoding="utf-8") as handle:
        online = list(csv.DictReader(handle))
    with gt_path.open(newline="", encoding="utf-8") as handle:
        gt = list(csv.DictReader(handle))
    keys_online = [tuple(row[name] for name in FRAME_KEY_FIELDS) for row in online]
    keys_gt = [tuple(row[name] for name in FRAME_KEY_FIELDS) for row in gt]
    assert len(online) == len(gt) == 14
    assert keys_online == keys_gt
    assert len(keys_online) == len(set(keys_online))
    assert all("gt" not in name.lower().split("_") for name in online[0])

    written = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert written == manifest
    assert manifest["DAY8_LOGGING_PASS"] is True
    assert manifest["STAGE2_GATE"] == "INCOMPLETE"
    assert manifest["reserved_test_run_performed"] is False
    assert manifest["formal_stage2c_rerun_performed"] is False
    assert manifest["gt_used_by_online_logger"] is False
    assert manifest["historical_artifacts_unchanged"] is True
    assert manifest["logging_trajectory_equivalent"] is True
    assert manifest["logging_enabled_nonfinite_violation_count"] == 0
    assert manifest["logging_disabled_nonfinite_violation_count"] == 0
    assert (
        manifest["logging_enabled_trajectory_checksum"]
        == manifest["logging_disabled_trajectory_checksum"]
    )
    assert manifest["logging_on_off_max_trajectory_difference"] <= 1.0e-12
    assert manifest["logging_on_off_max_covariance_difference"] <= 1.0e-12


def test_day8_gate_refuses_dirty_start(tmp_path, monkeypatch):
    monkeypatch.setattr(day8, "git_status_clean", lambda root: False)
    manifest = day8.run_stage2_failure_day8(
        ROOT,
        "pytest_day8_dirty",
        tmp_path,
    )
    assert manifest["git_status_clean_at_start"] is False
    assert manifest["DAY8_LOGGING_PASS"] is False


@pytest.mark.parametrize("corrupted_side", ["enabled", "disabled"])
def test_day8_gate_refuses_nonfinite_state_on_either_side(
    tmp_path,
    monkeypatch,
    corrupted_side,
):
    monkeypatch.setattr(day8, "git_status_clean", lambda root: True)
    original = day8.run_map_lio

    def run_with_nonfinite(*args, **kwargs):
        output = original(*args, **kwargs)
        side = "enabled" if kwargs.get("failure_logger") is not None else "disabled"
        if side == corrupted_side:
            output["full_deltas"] = output["full_deltas"].copy()
            output["full_deltas"][0, 0] = np.nan
        return output

    monkeypatch.setattr(day8, "run_map_lio", run_with_nonfinite)
    manifest = day8.run_stage2_failure_day8(
        ROOT,
        f"pytest_day8_nonfinite_{corrupted_side}",
        tmp_path,
    )
    assert manifest[f"logging_{corrupted_side}_nonfinite_violation_count"] > 0
    assert manifest["logging_trajectory_equivalent"] is False
    assert manifest["DAY8_LOGGING_PASS"] is False


def test_day8_gate_refuses_shape_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(day8, "git_status_clean", lambda root: True)
    original = day8.run_map_lio

    def run_with_shape_mismatch(*args, **kwargs):
        output = original(*args, **kwargs)
        if kwargs.get("failure_logger") is None:
            output["poses"] = output["poses"][:-1].copy()
        return output

    monkeypatch.setattr(day8, "run_map_lio", run_with_shape_mismatch)
    manifest = day8.run_stage2_failure_day8(
        ROOT,
        "pytest_day8_shape_mismatch",
        tmp_path,
    )
    assert manifest["logging_on_off_max_trajectory_difference"] == float("inf")
    assert manifest["logging_trajectory_equivalent"] is False
    assert manifest["DAY8_LOGGING_PASS"] is False
