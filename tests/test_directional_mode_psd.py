import numpy as np

from minibench.update_strategies import apply_directional_mode_update
from stage2c_helpers import random_system


def test_directional_mode_joseph_covariance_is_psd():
    update = apply_directional_mode_update(np.eye(6) * .02, random_system(17), np.array([1., 1., 0.]), .25)
    assert np.min(np.linalg.eigvalsh(update.posterior_covariance)) >= -1.0e-10
