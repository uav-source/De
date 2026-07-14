import numpy as np

from minibench.update_strategies import apply_projected_gain_update, make_translation_direction_6d, solve_full_robust_gain
from stage2c_helpers import random_system


def test_projected_gain_has_exact_weak_correction_ratio():
    system = random_system(8); prior = np.eye(6) * 0.03; direction = np.array([1., 2., -1.])
    full = solve_full_robust_gain(prior, system); lifted = make_translation_direction_6d(direction)
    for alpha in [0.0, 0.25, 0.5, 0.75, 0.9, 1.0]:
        selected = apply_projected_gain_update(prior, system, direction, alpha)
        assert abs(float(lifted @ selected.delta) - alpha * float(lifted @ full.delta)) <= 1.0e-10

