import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from eval.frame_contract import transform_axis


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
