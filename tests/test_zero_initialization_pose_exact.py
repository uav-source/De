import numpy as np

from zero_perturbation_test_support import development_snapshot


def test_zero_initialization_pose_is_exact_reference():
    snapshot = development_snapshot("IDEAL_MATCHED")
    expected = np.array([0.0, 0.0, 0.0, 1.5, 0.0, 0.0, 0.0, 1.0])
    assert np.array_equal(snapshot.reference_pose, expected)
