from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.metric_redesign_stage1c import within_level_test_result  # noqa: E402


def test_test_residuals_use_development_level_medians():
    rows = []
    for seed in [606, 707]:
        for index, level in enumerate(["L1", "L2", "L3", "L4"]):
            rows.append({"sweep_type": "geometry", "level": level, "geometry_seed": seed, "sensor_seed": 33, "mean_inverse_axis_information": 100 + index + seed / 1000, "mean_final_axis_error_squared": 200 + index + seed / 1000})
    lock = {"development_level_medians": {"geometry": {level: {"mean_inverse_axis_information": 1000.0, "mean_final_axis_error_squared": 2000.0} for level in ["L1", "L2", "L3", "L4"]}}}
    common = {"analysis": {"bootstrap_repetitions": 20, "bootstrap_seed": 9173}}
    result = within_level_test_result(rows, "geometry", lock, common)
    assert result["centering_source"] == "development_level_medians_from_analysis_lock"
