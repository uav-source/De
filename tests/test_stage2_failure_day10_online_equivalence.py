from pathlib import Path

import numpy as np
import pytest

from eval.stage2_failure_day8 import build_day8_unit_fixture
from eval.stage2_failure_no_gt_audit import (
    compare_array_field,
    compare_record_sequences,
    execute_online_variant,
)
from eval.stage2_failure_schema import ONLINE_FIELDS
from eval.synthetic_pipeline_common import load_yaml


ROOT = Path(__file__).resolve().parents[1]


def _online_record():
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
            "run_id": "record_comparison",
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
    return dict(runs["huber_full"]["records"][0])


@pytest.mark.parametrize(
    ("field", "candidate"),
    [
        ("poses", np.array([[0.0, 1.0e-11], [0.0, 0.0]])),
        ("covariances", np.array([[0.0, 0.0], [0.0, 1.0e-11]])),
        ("poses", np.zeros((3, 2))),
        ("poses", np.zeros((2, 2), dtype=np.float32)),
        ("poses", np.array([[0.0, np.nan], [0.0, 0.0]])),
        ("poses", np.array([[0.0, np.inf], [0.0, 0.0]])),
        ("poses", np.array([[0.0, 1.0e-13], [0.0, 0.0]])),
    ],
)
def test_continuous_comparator_detects_value_shape_dtype_nonfinite_and_checksum(
    field,
    candidate,
):
    result = compare_array_field(
        "variant",
        "huber_full",
        field,
        "continuous",
        np.zeros((2, 2), dtype=np.float64),
        candidate,
        1.0e-12,
    )
    assert result["pass"] is False


def test_discrete_comparator_detects_flag_flip():
    result = compare_array_field(
        "variant",
        "huber_full",
        "detector_triggered",
        "discrete",
        np.array([False, True]),
        np.array([True, True]),
        1.0e-12,
    )
    assert result["pass"] is False
    assert result["exact_array_equal"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_field",
        "extra_field",
        "frame_key",
        "nan_vs_zero",
        "numeric_field",
        "bool_field",
    ],
)
def test_online_record_comparator_detects_schema_key_nan_numeric_and_bool_changes(
    mutation,
):
    control = _online_record()
    candidate = dict(control)
    if mutation == "missing_field":
        candidate.pop("mean_huber_weight")
    elif mutation == "extra_field":
        candidate["unexpected"] = 1
    elif mutation == "frame_key":
        candidate["frame_index"] += 1
    elif mutation == "nan_vs_zero":
        control["weak_innovation_z_raw"] = float("nan")
        candidate["weak_innovation_z_raw"] = 0.0
    elif mutation == "numeric_field":
        candidate["mean_huber_weight"] += 1.0e-8
    elif mutation == "bool_field":
        candidate["actionable_direction"] = not candidate["actionable_direction"]
    result = compare_record_sequences([control], [candidate], ONLINE_FIELDS)
    assert result["pass"] is False
