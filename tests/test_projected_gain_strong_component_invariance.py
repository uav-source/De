import numpy as np

from minibench.update_strategies import apply_projected_gain_update, make_translation_direction_6d, solve_full_robust_gain
from stage2c_helpers import random_system


def test_projected_gain_preserves_orthogonal_correction_components():
    system = random_system(9); prior = np.eye(6) * 0.04; direction = np.array([2., -1., 0.5])
    full = solve_full_robust_gain(prior, system); selected = apply_projected_gain_update(prior, system, direction, 0.25)
    lifted = make_translation_direction_6d(direction); orthogonal = np.eye(6) - np.outer(lifted, lifted)
    assert np.linalg.norm(orthogonal @ (selected.delta - full.delta)) <= 1.0e-10

