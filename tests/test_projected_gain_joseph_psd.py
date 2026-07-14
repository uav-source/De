import numpy as np

from minibench.update_strategies import apply_directional_mode_update, apply_global_gain_update, apply_projected_gain_update, solve_full_robust_gain
from stage2c_helpers import random_system


def test_all_gain_strategies_return_psd_joseph_covariance():
    system = random_system(12); prior = np.eye(6) * 0.02; direction = np.array([1., 2., 3.])
    for update in [solve_full_robust_gain(prior, system), apply_global_gain_update(prior, system, .25), apply_directional_mode_update(prior, system, direction, .25), apply_projected_gain_update(prior, system, direction, .25)]:
        assert update.joseph_min_eigenvalue >= -1.0e-10
        assert np.min(np.linalg.eigvalsh(update.posterior_covariance)) >= -1.0e-10

