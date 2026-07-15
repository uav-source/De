import math

import numpy as np

from eval.stage2_failure_day11b_stress_trace import compute_stress_trace


def _key():
    return {
        "run_id": "run", "sequence_id": "sequence", "sweep": "geometry",
        "level": "L4", "stress": "coherent_subhuber_slip", "geometry_seed": 1,
        "sensor_seed": 2, "process_seed": 3, "method": "huber_full",
        "frame_index": 1, "timestamp": 0.1,
    }


def _observations(contaminated=True):
    shape = (2, 2)
    return {
        "points_lidar": np.zeros((2, 2, 3)),
        "normals_world": np.tile(np.array([1.0, 0.0, 0.0]), (2, 2, 1)),
        "plane_points_world": np.zeros((2, 2, 3)),
        "r_list": np.array([[0.0, 0.0], [1.0, 3.0]]),
        "R_diag_list": np.ones(shape),
        "contamination_mask": np.array([[False, False], [contaminated, False]]),
        "contamination_offset_m": np.array([[0.0, 0.0], [0.1 if contaminated else 0.0, 0.0]]),
    }


def test_subhuber_ratio_uses_frozen_normalized_residual_and_delta():
    priors = np.zeros((2, 8))
    priors[:, 7] = 1.0
    rows = compute_stress_trace([_key()], priors, _observations(), 2.5)
    assert rows[0]["contaminated_measurement_count"] == 1
    assert rows[0]["contaminated_subhuber_ratio"] == 1.0
    assert rows[0]["contaminated_huber_downweighted_ratio"] == 0.0


def test_uncontaminated_trace_uses_nan_not_fake_zero():
    priors = np.zeros((2, 8))
    priors[:, 7] = 1.0
    row = compute_stress_trace([_key()], priors, _observations(False), 2.5)[0]
    assert row["contaminated_measurement_count"] == 0
    assert math.isnan(row["contaminated_subhuber_ratio"])
