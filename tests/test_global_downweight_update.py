import numpy as np

from minibench.update_strategies import NormalEquation, attenuate_normal_equation


def test_global_downweight_scales_H_and_b_only_when_triggered():
    normal = NormalEquation(np.eye(6), np.ones(6), np.ones(1))
    H, b = attenuate_normal_equation(normal, "huber_global", 0.25, True, False)
    assert np.allclose(H, 0.25 * normal.H) and np.allclose(b, 0.25 * normal.b)
    H0, b0 = attenuate_normal_equation(normal, "huber_global", 0.25, False, False)
    assert np.array_equal(H0, normal.H) and np.array_equal(b0, normal.b)
