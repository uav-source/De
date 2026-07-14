import numpy as np

from minibench.update_strategies import make_translation_direction_6d
from stage2c_helpers import random_system


def test_rank_one_measurement_mode_has_requested_directional_information_ratio():
    system = random_system(16); direction = np.array([1., -2., .5]); alpha = .25
    lifted = make_translation_direction_6d(direction); response = system.whitened_jacobian @ lifted
    mode = response / np.linalg.norm(response); coefficient = 1.0 - np.sqrt(alpha)
    modified = system.whitened_jacobian - coefficient * np.outer(mode, mode @ system.whitened_jacobian)
    before = float(lifted @ system.H @ lifted); after = float(lifted @ modified.T @ modified @ lifted)
    assert np.isclose(after, alpha * before, atol=1.0e-10, rtol=1.0e-9)

