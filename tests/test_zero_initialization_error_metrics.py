import numpy as np

from zero_perturbation.metrics import zero_initialization_error


def test_zero_initialization_error_uses_reference_relative_vectors():
    reference = np.eye(4)
    estimate = np.eye(4)
    estimate[:3, 3] = [3.0, 4.0, 0.0]
    result = zero_initialization_error(reference, estimate)
    assert result["translation_error_m"] == 5.0
    assert result["rotation_error_rad"] == 0.0
