import numpy as np
import pytest

from minibench.map_lio import propagate_covariance
from stage2b_helpers import simple_pose


def test_covariance_propagation_is_symmetric_psd_and_additive():
    P = np.eye(6) * 1.0e-6
    Qt = np.diag([1.0e-4, 2.0e-5, 3.0e-5])
    Qr = np.diag([1.0e-7, 2.0e-7, 3.0e-7])
    result = propagate_covariance(P, simple_pose(), Qt, Qr)
    assert np.allclose(result, result.T)
    assert np.min(np.linalg.eigvalsh(result)) >= 0.0
    assert np.allclose(result[:3, :3], P[:3, :3] + Qr)


def test_covariance_rejects_clear_negative_eigenvalue():
    P = np.eye(6)
    P[0, 0] = -1.0e-3
    with pytest.raises(ValueError, match="PSD"):
        propagate_covariance(P, simple_pose(), np.eye(3), np.eye(3))
