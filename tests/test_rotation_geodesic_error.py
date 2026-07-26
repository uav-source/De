import math

import numpy as np
import pytest

from capture_range.recovery_metrics import rotation_geodesic_error_rad
from minibench.motion_simulator import rotvec_to_quat
from minibench.observation_simulator import quat_to_rot


def test_quaternion_geodesic_error_is_sign_invariant():
    identity = np.array([0.0, 0.0, 0.0, 1.0])
    assert rotation_geodesic_error_rad(identity, -identity) == 0.0


def test_quaternion_geodesic_error_matches_known_angle():
    rotated = rotvec_to_quat([0.0, 0.0, math.pi / 4])
    assert rotation_geodesic_error_rad(rotated, [0.0, 0.0, 0.0, 1.0]) == pytest.approx(
        math.pi / 4
    )


def test_matrix_geodesic_error_matches_known_angle():
    reference = np.eye(4)
    final = np.eye(4)
    final[:3, :3] = quat_to_rot(rotvec_to_quat([0.0, math.pi / 3, 0.0]))
    assert rotation_geodesic_error_rad(final, reference) == pytest.approx(math.pi / 3)
