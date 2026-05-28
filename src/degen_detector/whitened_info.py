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
    if H.shape != (6, 6):
        raise ValueError(f"H_tilde must be 6x6, got {H.shape}")
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


def compute_epsilon(eigvals: np.ndarray, mode: str, ratio: float) -> float:
    values = np.asarray(eigvals, dtype=float)
    if mode == "relative_trace":
        scale = float(np.trace(np.diag(values))) / max(values.size, 1)
        return max(scale * ratio, ratio)
    if mode == "absolute":
        return float(ratio)
    raise ValueError(f"Unsupported epsilon_mode: {mode}")

