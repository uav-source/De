import numpy as np

from minibench.update_strategies import apply_projected_gain_update, make_translation_direction_6d
from stage2c_helpers import random_system


def test_projected_weak_correction_is_monotone_in_alpha():
    system = random_system(11); prior = np.eye(6) * 0.02; direction = np.array([1., 0., 0.])
    lifted = make_translation_direction_6d(direction)
    values = [abs(float(lifted @ apply_projected_gain_update(prior, system, direction, alpha).delta)) for alpha in [0., .25, .5, .75, .9, 1.]]
    assert all(left <= right + 1.0e-12 for left, right in zip(values, values[1:]))

