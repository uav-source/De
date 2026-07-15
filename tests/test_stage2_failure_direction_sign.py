import math

import numpy as np
import pytest

from eval.stage2_failure_logging import (
    Stage2FailureOnlineLogger,
    orient_direction_for_logging,
)
from minibench.update_strategies import build_robust_linear_system


def _context():
    return {
        "run_id": "sign_test",
        "sequence_id": "fixture",
        "sweep": "quick",
        "level": "unit",
        "stress": "clean",
        "geometry_seed": 1,
        "sensor_seed": 2,
        "process_seed": 3,
        "method": "huber_full",
    }


def _log(logger, direction, stable):
    J = np.eye(6)
    residual = np.full(6, 0.01)
    variance = np.full(6, 0.0004)
    system = build_robust_linear_system(J, residual, variance, 2.5)
    return logger.log_frame(
        frame_index=len(logger.records) + 1,
        timestamp=0.1 * (len(logger.records) + 1),
        jacobian=J,
        residual=residual,
        variance=variance,
        robust_system=system,
        detected_direction_world=direction,
        direction_reliable=stable,
        detector_metrics={
            "ODI_trans": 0.5,
            "primary_eigengap_ratio": 0.2,
            "primary_direction_stable": stable,
            "degeneracy_triggered": True,
            "actionable_direction": stable,
        },
        full_delta=np.arange(6, dtype=float) * 0.01,
        full_solver_condition_number=2.0,
        full_posterior_covariance_trace=0.1,
        applied_delta=np.arange(6, dtype=float) * 0.01,
        applied_strategy="huber_full",
        solver_failure=False,
    )


def test_sign_continuity_removes_eigenvector_sign_jumps():
    previous = None
    logged = []
    flips = []
    for current in [
        np.array([1.0, 0.0, 0.0]),
        np.array([-1.0, 0.0, 0.0]),
        np.array([-0.99, 0.01, 0.0]),
    ]:
        oriented, flipped = orient_direction_for_logging(current, previous)
        logged.append(oriented)
        flips.append(flipped)
        previous = oriented
    assert flips == [False, True, True]
    assert all(float(left @ right) > 0.99 for left, right in zip(logged, logged[1:]))


@pytest.mark.parametrize(
    "direction,stable",
    [
        (np.array([np.nan, 0.0, 0.0]), True),
        (np.zeros(3), True),
        (np.array([1.0, 0.0, 0.0]), False),
        (np.array([1.0e-14, 0.0, 0.0]), True),
    ],
)
def test_invalid_or_unreliable_directions_write_nan(direction, stable):
    record = _log(Stage2FailureOnlineLogger(_context()), direction, stable)
    assert not record["weak_direction_valid"]
    assert not record["weak_innovation_valid"]
    for name in [
        "weak_direction_logged_world_x",
        "weak_score_gradient_raw",
        "weak_innovation_z_huber",
        "full_update_weak_signed_m",
        "applied_update_strong_norm_m",
    ]:
        assert math.isnan(record[name])
