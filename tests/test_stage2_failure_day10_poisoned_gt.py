from pathlib import Path

import numpy as np
import pytest

from eval.stage2_failure_day8 import build_day8_unit_fixture
from eval.stage2_failure_no_gt_audit import (
    compare_online_runs,
    execute_online_variant,
    poison_gt_observations,
)
from eval.synthetic_pipeline_common import load_yaml


ROOT = Path(__file__).resolve().parents[1]


def _run(observations):
    _, motion = build_day8_unit_fixture(8)
    day8 = load_yaml(ROOT / "configs/stage2_failure/day8_quick.yaml")
    return execute_online_variant(
        observations,
        motion,
        load_yaml(ROOT / "configs/detector/odi_stage2a.yaml"),
        load_yaml(ROOT / "configs/update/stage2c_common.yaml"),
        ["huber_full"],
        day8["online_odi_threshold"],
        day8["attenuation_alpha"],
        {
            "run_id": "poison_gt",
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


@pytest.mark.parametrize("poison_value", [float("nan"), 1.0e30])
def test_nan_and_large_poisoned_gt_do_not_change_online_outputs(poison_value):
    observations, _ = build_day8_unit_fixture(8)
    control = _run(observations)
    poisoned = poison_gt_observations(observations, poison_value)
    candidate = _run(poisoned)
    rows = compare_online_runs("gt_poisoned", control, candidate, 1.0e-12)
    assert all(row["pass"] for row in rows)


def test_nonunit_axis_poison_does_not_change_online_outputs():
    observations, _ = build_day8_unit_fixture(8)
    poisoned = dict(observations)
    poisoned["axis_per_frame"] = np.tile(np.array([9.0, -4.0, 2.0]), (8, 1))
    control = _run(observations)
    candidate = _run(poisoned)
    rows = compare_online_runs("gt_poisoned", control, candidate, 1.0e-12)
    assert all(row["pass"] for row in rows)
