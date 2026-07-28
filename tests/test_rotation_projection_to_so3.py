import numpy as np

from zero_perturbation.rotation_metrics import project_to_so3


def test_nearest_so3_projection_is_orthogonal_and_positive_determinant():
    raw = np.array(
        [[1.0, 2.0e-7, 0.0], [-1.0e-7, 0.9999999, 3.0e-7], [0.0, -2.0e-7, 1.0]]
    )
    projected, _ = project_to_so3(raw)
    assert np.allclose(projected.T @ projected, np.eye(3), atol=1.0e-14)
    assert np.linalg.det(projected) > 0.0
