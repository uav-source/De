import numpy as np
import pytest

from minibench.map_lio import linearize_point_to_plane
from stage2c_helpers import simple_pose


def test_point_to_plane_is_relinearized_at_prior_pose():
    points = np.array([[1.0, 2.0, 0.0], [0.0, 1.0, 2.0]])
    normals = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    anchors = points.copy()
    J0, r0 = linearize_point_to_plane(simple_pose(), points, normals, anchors, np.zeros(2))
    moved = simple_pose(0.3)
    J1, r1 = linearize_point_to_plane(moved, points, normals, anchors, np.zeros(2))
    assert np.array_equal(J0, J1)
    assert not np.array_equal(r0, r1)
    assert r1[0] == pytest.approx(0.3)
