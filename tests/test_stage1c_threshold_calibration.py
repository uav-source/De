from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.metric_redesign_stage1c import resolve_phase_threshold  # noqa: E402


def test_threshold_is_fixed_five_percent_development_oc_quantile(tmp_path):
    oc_values = np.arange(1.0, 101.0)
    non_oc_values = np.full(100, -999.0)
    for name, values in [("oc.csv", oc_values), ("geometry.csv", non_oc_values)]:
        (tmp_path / name).write_text(
            "axis_information_normalized\n" + "\n".join(str(value) for value in values) + "\n",
            encoding="utf-8",
        )
    rows = [
        {"scene_family": "OC", "metrics_path": "oc.csv"},
        {"scene_family": "ST", "metrics_path": "geometry.csv"},
    ]
    common = {"analysis": {"low_information_quantile": 0.05}}
    resolved = resolve_phase_threshold(tmp_path, "development", tmp_path, rows, common, None, tmp_path)
    assert np.isclose(resolved["low_axis_information_threshold"], np.quantile(oc_values, 0.05))
    assert resolved["calibration_source"] == "development_open_control_only"
