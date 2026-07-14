import numpy as np

from minibench.update_strategies import apply_projected_gain_update, solve_full_robust_gain
from stage2c_helpers import random_system


def test_projected_gain_preserves_rotation_correction():
    system = random_system(10); prior = np.eye(6) * 0.05
    full = solve_full_robust_gain(prior, system)
    selected = apply_projected_gain_update(prior, system, np.array([1., 1., 0.]), 0.0)
    assert np.allclose(selected.delta[:3], full.delta[:3], atol=1.0e-10, rtol=0.0)

