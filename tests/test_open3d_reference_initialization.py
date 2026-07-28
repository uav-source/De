import numpy as np

from zero_perturbation.metrics import pose_matrix
from zero_perturbation.open3d_backend import run_open3d_full
from zero_perturbation_test_support import development_protocol


def test_open3d_exact_matched_plane_preserves_reference_initialization():
    xy = np.linspace(-1.0, 1.0, 8)
    x, y = np.meshgrid(xy, xy)
    points = np.column_stack([x.ravel(), y.ravel(), np.zeros(x.size)])
    initial = np.eye(4)
    result = run_open3d_full(
        points,
        points,
        initial,
        development_protocol().section("open3d_registration"),
        1,
        "toy-checksum",
    )
    assert np.allclose(pose_matrix(result.final_pose), initial, atol=1.0e-10)
    assert result.finite_result
