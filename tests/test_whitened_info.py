from pathlib import Path

import numpy as np

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from degen_detector.whitened_info import (  # noqa: E402
    compute_AIS,
    compute_H_tilde,
    compute_lambda_min,
    eigen_decompose,
    safe_condition_number,
    validate_H,
)


def test_formula_contract_contains_whitened_pose_block():
    text = (ROOT / "docs/formula_contract.md").read_text(encoding="utf-8")

    assert "H_tilde = (J_p D)^T R_L^-1 (J_p D)" in text
    assert "delta x_p = [delta theta^T, delta p^T]^T in R^6" in text
    assert "Do not left-multiply LiDAR residuals" in text


def test_compute_H_tilde_is_symmetric_psd():
    J = np.eye(6)
    R_diag = np.ones(6)

    H = compute_H_tilde(J, R_diag, s_theta=0.1, s_p=0.5)
    eigvals, _ = eigen_decompose(H)

    assert np.allclose(H, H.T)
    assert np.min(eigvals) >= -1.0e-12
    validate_H(H)


def test_eigenvalues_nonnegative_up_to_numerical_tolerance_from_random_J():
    rng = np.random.default_rng(42)
    J = rng.normal(size=(80, 6))
    R_diag = np.full(80, 0.04)

    H = compute_H_tilde(J, R_diag, s_theta=0.05, s_p=0.5)
    eigvals, _ = eigen_decompose(H)

    assert np.min(eigvals) > -1.0e-8
    assert np.all(np.isfinite(eigvals))


def test_input_scale_changes_do_not_create_nan_or_inf():
    rng = np.random.default_rng(7)
    J = rng.normal(size=(40, 6))
    R_diag = np.full(40, 0.01)

    for scale in [1.0e-6, 1.0, 1.0e6]:
        H = compute_H_tilde(scale * J, R_diag, s_theta=0.05, s_p=0.5)
        eigvals, _ = eigen_decompose(H)
        cond = safe_condition_number(eigvals, 1.0e-9)
        ais = compute_AIS(H, 1.0e-9)
        lam_min = compute_lambda_min(eigvals)

        assert np.all(np.isfinite(H))
        assert np.isfinite(cond)
        assert np.isfinite(ais)
        assert np.isfinite(lam_min)


def test_condition_number_sensitive_to_small_lambda():
    eigvals = np.array([1.0, 0.1, 0.01, 0.001, 0.0001, 1.0e-12])

    cond = safe_condition_number(eigvals, 1.0e-12)

    assert cond > 1.0e11
