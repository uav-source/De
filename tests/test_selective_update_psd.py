import numpy as np

from minibench.update_strategies import NormalEquation, attenuate_normal_equation


def test_selective_effective_information_remains_psd_for_all_alphas():
    rng = np.random.default_rng(4)
    raw = rng.normal(size=(6, 6)); normal = NormalEquation(raw.T @ raw, np.ones(6), np.ones(1))
    for alpha in [0.0, 0.1, 0.25, 0.5, 0.75, 1.0]:
        H, _ = attenuate_normal_equation(normal, "huber_selective", alpha, True, True, np.array([1., 2., 3.]))
        assert np.min(np.linalg.eigvalsh(H)) >= -1.0e-10
