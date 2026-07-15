from pathlib import Path

import numpy as np

from eval.stage2_failure_day8 import (
    _maximum_array_difference,
    build_day8_unit_fixture,
)
from eval.stage2_failure_logging import Stage2FailureOnlineLogger
from eval.synthetic_pipeline_common import load_yaml
from minibench.map_lio import run_map_lio


ROOT = Path(__file__).resolve().parents[1]


def test_logging_is_read_only_and_estimator_equivalent_to_1e_minus_12():
    observations, motion = build_day8_unit_fixture()
    observations_before = {name: value.copy() for name, value in observations.items()}
    motion_before = {name: value.copy() for name, value in motion.items()}
    detector = load_yaml(ROOT / "configs/detector/odi_stage2a.yaml")
    update = load_yaml(ROOT / "configs/update/stage2c_common.yaml")
    context = {
        "run_id": "equivalence",
        "sequence_id": "day8_unit_fixture_v1",
        "sweep": "day8_quick",
        "level": "unit",
        "stress": "fixture",
        "geometry_seed": 80817,
        "sensor_seed": 80818,
        "process_seed": 80819,
        "method": "huber_projected_gain",
    }
    disabled = run_map_lio(
        observations,
        motion,
        detector,
        update,
        "huber_projected_gain",
        0.034680103235327255,
        0.9,
    )
    enabled = run_map_lio(
        observations,
        motion,
        detector,
        update,
        "huber_projected_gain",
        0.034680103235327255,
        0.9,
        failure_logger=Stage2FailureOnlineLogger(context),
    )

    for name in [
        "prior_poses",
        "poses",
        "applied_deltas",
        "full_deltas",
        "covariances",
    ]:
        assert np.max(np.abs(disabled[name] - enabled[name])) <= 1.0e-12
    np.testing.assert_array_equal(disabled["detector_triggered"], enabled["detector_triggered"])
    np.testing.assert_array_equal(disabled["actionable_direction"], enabled["actionable_direction"])
    for name, before in observations_before.items():
        np.testing.assert_array_equal(observations[name], before)
    for name, before in motion_before.items():
        np.testing.assert_array_equal(motion[name], before)


def test_maximum_array_difference_rejects_nonfinite_and_shape_mismatch():
    finite = np.array([1.0, 2.0])
    assert _maximum_array_difference(finite, finite.copy()) == 0.0
    assert _maximum_array_difference(finite, np.array([1.0, np.nan])) == float("inf")
    assert _maximum_array_difference(np.array([np.inf, 2.0]), finite) == float("inf")
    assert _maximum_array_difference(finite, np.array([[1.0, 2.0]])) == float("inf")
