import numpy as np
import pytest

from fastlio2_adapter.day6_eigenspace_stability import (
    sign_invariant_angle_deg,
    weak_subspace_principal_angles_deg,
)


def test_large_v1_rotation_can_leave_two_dimensional_subspace_stable():
    left = np.eye(3)[:, :2]
    angle = np.deg2rad(80.0)
    right = np.column_stack(
        (
            [np.cos(angle), np.sin(angle), 0.0],
            [-np.sin(angle), np.cos(angle), 0.0],
        )
    )
    assert sign_invariant_angle_deg(left[:, 0], right[:, 0]) == pytest.approx(
        80.0
    )
    assert weak_subspace_principal_angles_deg(left, right) == pytest.approx(
        (0.0, 0.0), abs=1.0e-6
    )


def test_whole_subspace_change_is_visible():
    left = np.eye(3)[:, :2]
    right = np.column_stack(([1.0, 0.0, 0.0], [0.0, 0.0, 1.0]))
    minimum, maximum = weak_subspace_principal_angles_deg(left, right)
    assert minimum == pytest.approx(0.0)
    assert maximum == pytest.approx(90.0)
