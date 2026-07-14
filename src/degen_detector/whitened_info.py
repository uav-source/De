"""Whitened pose information matrix utilities for Day 6."""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np


def compute_H_tilde(
    J: np.ndarray,
    R_diag: np.ndarray,
    s_theta: float,
    s_p: float,
    epsilon_mode: str = "relative_trace",
    epsilon_ratio: float = 1.0e-6,
) -> np.ndarray:
    """Compute H_tilde = (J D)^T R^-1 (J D) for the 6DoF pose block."""

    J = np.asarray(J, dtype=float)
    R_diag = np.asarray(R_diag, dtype=float)
    if J.ndim != 2 or J.shape[1] != 6:
        raise ValueError(f"J must have shape [N, 6], got {J.shape}")
    if R_diag.ndim != 1 or R_diag.shape[0] != J.shape[0]:
        raise ValueError(f"R_diag must have shape [{J.shape[0]}], got {R_diag.shape}")
    if np.any(R_diag <= 0):
        raise ValueError("R_diag must be strictly positive")

    D = np.diag([s_theta, s_theta, s_theta, s_p, s_p, s_p])
    JD = J @ D
    H = JD.T @ (JD / R_diag[:, None])
    H = 0.5 * (H + H.T)

    # Keep these parameters in the signature because the formula contract fixes
    # them at this interface; epsilon is consumed by downstream metrics.
    _ = epsilon_mode, epsilon_ratio
    return H


def eigen_decompose(H_tilde: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return eigenvalues/eigenvectors sorted descending by eigenvalue."""

    H = np.asarray(H_tilde, dtype=float)
    validate_H(H)
    eigvals, eigvecs = np.linalg.eigh(H)
    order = np.argsort(eigvals)[::-1]
    return eigvals[order], eigvecs[:, order]


def safe_condition_number(eigvals: np.ndarray, eps: float) -> float:
    values = np.asarray(eigvals, dtype=float)
    lam_max = float(np.max(values))
    lam_min = float(np.min(values))
    return lam_max / max(lam_min, eps)


def compute_AIS(H_tilde: np.ndarray, eps: float) -> float:
    eigvals = np.linalg.eigvalsh(np.asarray(H_tilde, dtype=float))
    safe = np.maximum(eigvals, 0.0) + eps
    return float(np.mean(np.log(safe)))


def compute_lambda_min(eigvals: np.ndarray) -> float:
    return float(np.min(np.asarray(eigvals, dtype=float)))


def validate_H(H_tilde: np.ndarray) -> Dict[str, float]:
    H = np.asarray(H_tilde, dtype=float)
    if H.shape not in {(6, 6), (3, 3)}:
        raise ValueError(f"Information matrix must be 6x6 or 3x3, got {H.shape}")
    if not np.all(np.isfinite(H)):
        raise ValueError("H_tilde contains NaN or Inf")
    symmetry_error = float(np.max(np.abs(H - H.T)))
    if symmetry_error > 1.0e-8:
        raise ValueError(f"H_tilde is not symmetric; max error={symmetry_error}")
    min_eig = float(np.min(np.linalg.eigvalsh(H)))
    if min_eig < -1.0e-7:
        raise ValueError(f"H_tilde is not PSD within tolerance; min eig={min_eig}")
    return {
        "symmetry_error": symmetry_error,
        "min_eig": min_eig,
    }


def compute_translation_schur_info(
    H_tilde: np.ndarray,
    damping_ratio: float = 1.0e-6,
) -> np.ndarray:
    """Marginalize rotation and return the 3x3 translation information."""

    H = np.asarray(H_tilde, dtype=float)
    if H.shape != (6, 6):
        raise ValueError(f"H_tilde must be 6x6, got {H.shape}")
    validate_H(H)
    if damping_ratio <= 0.0:
        raise ValueError("damping_ratio must be positive")
    H_theta = H[:3, :3]
    H_theta_p = H[:3, 3:]
    H_p_theta = H[3:, :3]
    H_p = H[3:, 3:]
    scale = max(float(np.max(np.diag(H_theta))), float(np.trace(H_theta)) / 3.0, 1.0)
    damping = float(damping_ratio) * scale
    marginalized = H_p - H_p_theta @ np.linalg.solve(H_theta + damping * np.eye(3), H_theta_p)
    marginalized = 0.5 * (marginalized + marginalized.T)
    eigvals, eigvecs = np.linalg.eigh(marginalized)
    tolerance = max(float(np.max(np.abs(eigvals))) * 1.0e-9, 1.0e-9)
    if float(np.min(eigvals)) < -tolerance:
        raise ValueError(f"Translation Schur information has a large negative eigenvalue: {np.min(eigvals)}")
    clipped = np.maximum(eigvals, 0.0)
    result = eigvecs @ np.diag(clipped) @ eigvecs.T
    return 0.5 * (result + result.T)


def compute_effective_sample_size(R_diag: np.ndarray) -> float:
    variances = np.asarray(R_diag, dtype=float)
    if variances.ndim != 1 or variances.size == 0:
        raise ValueError("R_diag must be a non-empty 1-D array")
    if np.any(variances <= 0.0) or not np.all(np.isfinite(variances)):
        raise ValueError("R_diag must contain finite positive values")
    weights = 1.0 / variances
    return float(np.sum(weights) ** 2 / np.sum(weights**2))


def normalize_information_matrix(H: np.ndarray, n_eff: float) -> np.ndarray:
    matrix = np.asarray(H, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("H must be square")
    if not np.isfinite(n_eff) or n_eff <= 0.0:
        raise ValueError("n_eff must be finite and positive")
    return 0.5 * ((matrix / float(n_eff)) + (matrix / float(n_eff)).T)


def compute_axis_information(H_trans: np.ndarray, axis: np.ndarray) -> float:
    """Return directional translation information a^T H_trans a."""

    matrix = np.asarray(H_trans, dtype=float)
    direction = np.asarray(axis, dtype=float)
    if matrix.shape != (3, 3):
        raise ValueError(f"H_trans must be 3x3, got {matrix.shape}")
    if direction.shape != (3,):
        raise ValueError(f"axis must have shape [3], got {direction.shape}")
    norm = float(np.linalg.norm(direction))
    if norm < 1.0e-12:
        raise ValueError("axis must be non-zero")
    unit = direction / norm
    return float(unit @ matrix @ unit)


def compute_axis_information_ratio(
    H_trans: np.ndarray,
    axis: np.ndarray,
    epsilon: float = 1.0e-12,
) -> float:
    """Normalize directional information by one third of total information."""

    matrix = np.asarray(H_trans, dtype=float)
    if epsilon <= 0.0:
        raise ValueError("epsilon must be positive")
    denominator = float(np.trace(matrix)) / 3.0 + float(epsilon)
    return compute_axis_information(matrix, axis) / denominator


def compute_epsilon(eigvals: np.ndarray, mode: str, ratio: float) -> float:
    values = np.asarray(eigvals, dtype=float)
    if mode == "relative_trace":
        scale = float(np.trace(np.diag(values))) / max(values.size, 1)
        return max(scale * ratio, ratio)
    if mode == "absolute":
        return float(ratio)
    raise ValueError(f"Unsupported epsilon_mode: {mode}")
