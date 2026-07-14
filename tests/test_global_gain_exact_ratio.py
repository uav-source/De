import numpy as np

from minibench.update_strategies import apply_global_gain_update, solve_full_robust_gain
from stage2c_helpers import random_system


def test_global_gain_scales_all_correction_components_exactly():
    system = random_system(15); prior = np.eye(6) * 0.04; alpha = 0.25
    full = solve_full_robust_gain(prior, system); global_update = apply_global_gain_update(prior, system, alpha)
    assert np.allclose(global_update.delta, alpha * full.delta, atol=1.0e-10, rtol=0.0)

