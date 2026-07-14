import numpy as np

from minibench.update_strategies import execute_gain_strategy
from stage2c_helpers import random_system


def test_nonactionable_projected_gain_is_full_gain():
    system = random_system(14); prior = np.eye(6) * 0.03
    full = execute_gain_strategy("huber_full", prior, system, .25, False, False)
    selected = execute_gain_strategy("huber_projected_gain", prior, system, .25, False, False, np.array([1., 0., 0.]))
    assert np.array_equal(selected.kalman_gain_whitened, full.kalman_gain_whitened)
    assert np.array_equal(selected.delta, full.delta)
    assert np.array_equal(selected.posterior_covariance, full.posterior_covariance)

