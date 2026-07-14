import numpy as np

from minibench.update_strategies import build_normal_equation, huber_weights


def test_huber_weights_and_normal_equation_follow_standardized_residual_formula():
    residual = np.array([0.01, 0.10])
    variance = np.array([0.0004, 0.0004])
    weights = huber_weights(residual, variance, 2.5)
    assert np.allclose(weights, [1.0, 0.5])
    J = np.zeros((2, 6)); J[:, 3] = 1.0
    normal = build_normal_equation(J, residual, variance, 2.5)
    assert normal.H[3, 3] == (1.0 + 0.5) / 0.0004
    assert normal.b[3] == (0.01 + 0.5 * 0.10) / 0.0004
