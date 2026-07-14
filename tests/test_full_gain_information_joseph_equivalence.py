import numpy as np

from minibench.update_strategies import solve_full_robust_gain
from stage2c_helpers import random_system


def test_information_and_joseph_covariances_are_equivalent():
    system = random_system()
    prior = np.diag(np.linspace(0.01, 0.06, 6))
    update = solve_full_robust_gain(prior, system)
    expected = np.linalg.inv(np.linalg.inv(prior) + system.H)
    assert np.allclose(update.posterior_covariance, expected, atol=1.0e-10, rtol=1.0e-7)
    assert np.allclose(update.delta, -expected @ system.b, atol=1.0e-10)

