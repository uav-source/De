from pathlib import Path

import math

import pytest

from eval.stage2_failure_day8 import build_day8_unit_fixture
from eval.stage2_failure_day9 import compute_window_records, window_config_from_mapping
from eval.stage2_failure_no_gt_audit import compare_window_runs, execute_online_variant
from eval.synthetic_pipeline_common import load_yaml


ROOT = Path(__file__).resolve().parents[1]


def _window_records():
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
            "run_id": "window_comparison",
            "sequence_id": "fixture",
            "sweep": "quick",
            "level": "unit",
            "stress": "no_gt",
            "geometry_seed": 1,
            "sensor_seed": 2,
            "process_seed": 3,
        },
        day8["directional_information_epsilon"],
    )
    config = window_config_from_mapping(
        load_yaml(ROOT / "configs/stage2_failure/day9_quick.yaml")
    )
    return compute_window_records(runs["huber_full"]["records"], config)


@pytest.mark.parametrize(
    "field",
    [
        "raw_cusum_positive",
        "raw_current_same_sign_run_length",
        "raw_lag1_autocorrelation",
        "huber_skewness",
    ],
)
def test_window_comparator_detects_cusum_run_autocorrelation_and_skewness(field):
    control = _window_records()
    candidate = [dict(row) for row in control]
    value = float(candidate[-1][field])
    candidate[-1][field] = 0.125 if math.isnan(value) else value + 0.125
    result = compare_window_runs(
        "variant", "huber_full", control, candidate
    )
    assert result["pass"] is False
    assert result["records_equal"] is False


def test_window_comparator_detects_output_row_count_change():
    control = _window_records()
    result = compare_window_runs(
        "variant", "huber_full", control, control[:-1]
    )
    assert result["pass"] is False
    assert result["control_row_count"] == result["variant_row_count"] + 1
