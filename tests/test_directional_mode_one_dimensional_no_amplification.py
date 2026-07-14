import numpy as np

from minibench.update_strategies import apply_directional_mode_update, build_robust_linear_system, solve_full_robust_gain


def test_directional_mode_does_not_amplify_one_dimensional_correction():
    J = np.zeros((20, 6)); J[:, 3] = 1.0
    system = build_robust_linear_system(J, np.full(20, .01), np.full(20, .0004), 2.5)
    prior = np.eye(6) * .02; full = solve_full_robust_gain(prior, system)
    for alpha in [0., .25, .5, .75, .9, 1.]:
        mode = apply_directional_mode_update(prior, system, np.array([1., 0., 0.]), alpha)
        assert abs(mode.delta[3]) <= abs(full.delta[3]) + 1.0e-12

