import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from eval.frame_contract import sign_invariant_angle_deg, transform_axis


@pytest.mark.parametrize(
    "axis,degrees,expected",
    [
        ([1, 0, 0], [0, 0, 0], [1, 0, 0]),
        ([0, 1, 0], [90, 0, 0], [0, 0, 1]),
        ([0, 0, 1], [0, 90, 0], [1, 0, 0]),
        ([1, 0, 0], [0, 0, 90], [0, 1, 0]),
    ],
)
def test_identity_and_axis_90_degree_world_transforms(axis, degrees, expected):
    rotation = Rotation.from_euler("xyz", degrees, degrees=True).as_matrix()
    np.testing.assert_allclose(transform_axis(rotation, axis), expected, atol=1e-12)


def test_axis_transform_normalizes_units_without_changing_direction():
    rotation = Rotation.from_euler("z", 90.0, degrees=True).as_matrix()
    np.testing.assert_allclose(
        transform_axis(rotation, [4.0, 0.0, 0.0]),
        [0.0, 1.0, 0.0],
        atol=1e-12,
    )


def test_random_so3_preserves_sign_invariant_axis_angle():
    rng = np.random.default_rng(20260726)
    for _ in range(100):
        rotation = Rotation.random(random_state=rng).as_matrix()
        weak = rng.normal(size=3)
        reference = rng.normal(size=3)
        before = sign_invariant_angle_deg(weak, reference)
        after = sign_invariant_angle_deg(
            transform_axis(rotation, weak), transform_axis(rotation, reference)
        )
        assert after == pytest.approx(before, abs=1e-12)
