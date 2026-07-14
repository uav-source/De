import numpy as np

from minibench.update_strategies import NormalEquation, attenuate_normal_equation


def test_alpha_zero_removes_weak_direction_and_cross_information():
    rng = np.random.default_rng(3)
    raw = rng.normal(size=(6, 6)); H = raw.T @ raw
    normal = NormalEquation(H, np.ones(6), np.ones(1))
    effective, _ = attenuate_normal_equation(normal, "huber_selective", 0.0, True, True, np.array([1., 0., 0.]))
    lifted = np.zeros(6); lifted[3] = 1.0
    assert np.linalg.norm(effective @ lifted) < 1.0e-10
    assert abs(float(lifted @ effective @ lifted)) < 1.0e-10
