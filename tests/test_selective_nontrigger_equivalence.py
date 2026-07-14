import numpy as np

from minibench.update_strategies import NormalEquation, execute_update_strategy


def test_nonactionable_selective_is_exactly_huber_full():
    normal = NormalEquation(np.eye(6), np.arange(6.0), np.ones(1))
    full = execute_update_strategy("huber_full", np.eye(6), normal, 1.0, False, False)
    selective = execute_update_strategy("huber_selective", np.eye(6), normal, 0.0, False, False, np.array([1., 0., 0.]))
    assert np.array_equal(full.effective_H, selective.effective_H)
    assert np.array_equal(full.effective_b, selective.effective_b)
    assert np.array_equal(full.delta, selective.delta)
    assert np.array_equal(full.posterior_covariance, selective.posterior_covariance)
