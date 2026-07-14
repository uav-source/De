from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.metric_redesign_stage1c import resolve_phase_threshold  # noqa: E402


def test_test_threshold_reads_lock_and_refuses_missing_lock(tmp_path):
    lock = {
        "low_information_quantile": 0.05,
        "low_axis_information_threshold": 123.0,
        "calibration_frame_count": 400,
        "calibration_data_hash": "dev-only",
        "metric_definition_version": "stage1c_v1",
    }
    original = dict(lock)
    first = resolve_phase_threshold(tmp_path, "test", tmp_path, [], {}, lock, tmp_path)
    changed_test_rows = [{"scene_family": "OC", "axis_information_normalized": -1.0e9}]
    second = resolve_phase_threshold(tmp_path, "test", tmp_path, changed_test_rows, {}, lock, tmp_path)
    assert first["low_axis_information_threshold"] == second["low_axis_information_threshold"] == 123.0
    assert lock == original
    with pytest.raises(RuntimeError, match="locked low-information threshold"):
        resolve_phase_threshold(tmp_path, "test", tmp_path, [], {}, None, tmp_path)
