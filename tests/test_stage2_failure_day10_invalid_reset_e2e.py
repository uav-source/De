import csv
import math
from pathlib import Path

from eval.stage2_failure_day8 import build_day8_unit_fixture
from eval.stage2_failure_no_gt_audit import (
    execute_online_variant,
    run_invalid_reset_end_to_end,
)
from eval.synthetic_pipeline_common import load_yaml


ROOT = Path(__file__).resolve().parents[1]


def _template_record():
    observations, motion = build_day8_unit_fixture(8)
    day8 = load_yaml(ROOT / "configs/stage2_failure/day8_quick.yaml")
    runs = execute_online_variant(
        observations,
        motion,
        load_yaml(ROOT / "configs/detector/odi_stage2a.yaml"),
        load_yaml(ROOT / "configs/update/stage2c_common.yaml"),
        ["huber_full"],
        day8["online_odi_threshold"],
        day8["attenuation_alpha"],
        {
            "run_id": "reset_template",
            "sequence_id": "fixture",
            "sweep": "quick",
            "level": "unit",
            "stress": "reset",
            "geometry_seed": 1,
            "sensor_seed": 2,
            "process_seed": 3,
        },
        day8["directional_information_epsilon"],
    )
    return runs["huber_full"]["records"][0]


def test_valid_invalid_valid_runs_through_complete_day9_file_flow(tmp_path):
    audit, output_path = run_invalid_reset_end_to_end(
        ROOT,
        tmp_path / "reset_e2e",
        _template_record(),
    )
    assert audit["fixture_row_count"] == 11
    assert audit["invalid_reset_count"] == 1
    assert audit["observed_window_counts"] == [1, 2, 3, 4, 5, 0, 1, 2, 3, 4, 5]
    assert audit["invalid_reset_expected_counts_match"] is True
    assert audit["invalid_reset_cusum_reset_match"] is True
    assert audit["invalid_reset_end_to_end_pass"] is True
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[5]["stat_reset_reason"] == "invalid_direction"
    assert math.isnan(float(rows[5]["raw_window_mean"]))
    assert float(rows[6]["raw_window_mean"]) == -1.0
    assert float(rows[6]["huber_window_mean"]) == -0.8
    assert float(rows[6]["raw_cusum_positive"]) == 0.0
    assert float(rows[6]["raw_cusum_negative"]) == 0.5
