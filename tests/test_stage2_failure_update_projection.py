import numpy as np

from eval.stage2_failure_logging import project_update


def test_full_update_projection_preserves_signed_weak_and_strong_vector():
    delta = np.array([0.1, -0.2, 0.3, 2.0, 3.0, 4.0])
    projection = project_update(delta, np.array([1.0, 0.0, 0.0]))

    assert projection.weak_signed == 2.0
    assert projection.weak_abs == 2.0
    np.testing.assert_array_equal(projection.strong_vector, [0.0, 3.0, 4.0])
    assert projection.strong_norm == 5.0
    assert projection.rotation_norm == np.linalg.norm(delta[:3])
