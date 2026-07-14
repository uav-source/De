import numpy as np

from minibench.update_strategies import NormalEquation, execute_update_strategy


def test_alpha_one_selective_equals_huber_full_to_tight_tolerance():
    rng = np.random.default_rng(5)
    raw = rng.normal(size=(6, 6)); normal = NormalEquation(raw.T @ raw, rng.normal(size=6), np.ones(3))
    full = execute_update_strategy("huber_full", np.eye(6), normal, 1.0, True, True)
    selective = execute_update_strategy("huber_selective", np.eye(6), normal, 1.0, True, True, np.array([1., 0., 0.]))
    for left, right in [(full.effective_H, selective.effective_H), (full.effective_b, selective.effective_b), (full.delta, selective.delta), (full.posterior_covariance, selective.posterior_covariance)]:
        assert np.allclose(left, right, atol=1.0e-10, rtol=0.0)
