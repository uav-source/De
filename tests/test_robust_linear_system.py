import numpy as np

from minibench.update_strategies import build_robust_linear_system, huber_weights


def test_whitened_system_matches_direct_huber_normal_equation():
    rng = np.random.default_rng(1)
    J = rng.normal(size=(24, 6)); residual = rng.normal(scale=0.04, size=24)
    variance = np.linspace(0.0002, 0.0008, 24)
    system = build_robust_linear_system(J, residual, variance, 2.5)
    weights = huber_weights(residual, variance, 2.5) / variance
    assert np.allclose(system.H, J.T @ (J * weights[:, None]))
    assert np.allclose(system.b, J.T @ (residual * weights))
    assert np.allclose(system.H, system.whitened_jacobian.T @ system.whitened_jacobian)
    assert np.allclose(system.b, system.whitened_jacobian.T @ system.whitened_residual)

