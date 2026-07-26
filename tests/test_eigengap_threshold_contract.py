import numpy as np

from degen_detector.weak_direction import estimate_primary_direction


def test_eigengap_ratio_uses_ascending_minimum_pair_and_greater_equal_threshold():
    at_threshold = estimate_primary_direction(
        np.asarray([1.0, 0.02, 0.0]), np.eye(3), min_eigengap_ratio=0.02
    )
    below = estimate_primary_direction(
        np.asarray([1.0, 0.019, 0.0]), np.eye(3), min_eigengap_ratio=0.02
    )
    assert at_threshold.eigengap_ratio == 0.02
    assert at_threshold.direction_stable is True
    assert below.direction_stable is False
