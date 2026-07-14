import numpy as np

from minibench.update_strategies import apply_projected_gain_update, solve_full_robust_gain
from stage2c_helpers import random_system


def test_projected_alpha_one_is_full_gain():
    system = random_system(13); prior = np.eye(6) * 0.03
    full = solve_full_robust_gain(prior, system); selected = apply_projected_gain_update(prior, system, np.array([1., 0., 0.]), 1.0)
    assert np.array_equal(selected.kalman_gain_whitened, full.kalman_gain_whitened)
    assert np.array_equal(selected.delta, full.delta)
    assert np.array_equal(selected.posterior_covariance, full.posterior_covariance)

