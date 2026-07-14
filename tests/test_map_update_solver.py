import numpy as np

from minibench.update_strategies import solve_map_update


def test_map_solver_matches_direct_solution_and_returns_psd_covariance():
    P = np.eye(6) * 0.2
    H = np.diag(np.arange(1.0, 7.0))
    b = np.arange(6.0)
    delta, posterior = solve_map_update(P, H, b)
    expected = np.linalg.inv(np.linalg.inv(P) + H)
    assert np.allclose(posterior, expected)
    assert np.allclose(delta, -expected @ b)
    assert np.min(np.linalg.eigvalsh(posterior)) > 0.0
