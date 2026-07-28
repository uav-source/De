import numpy as np
import pytest

from zero_perturbation.metrics import full_frozen_pose_difference


def test_full_frozen_difference_is_inverse_frozen_times_full():
    frozen = np.eye(4)
    frozen[0, 3] = 2.0
    full = np.eye(4)
    full[0, 3] = 5.0
    result = full_frozen_pose_difference(full, frozen)
    assert result["full_frozen_translation_difference_m"] == pytest.approx(3.0)
    assert result["full_frozen_rotation_difference_rad"] == pytest.approx(0.0)
