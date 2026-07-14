"""Weak-direction extraction from the 6DoF whitened information spectrum."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np


@dataclass(frozen=True)
class PrimaryDirectionEstimate:
    direction: np.ndarray
    lambda_min_ratio: float
    eigengap_ratio: float
    direction_stable: bool


@dataclass(frozen=True)
class WeakSubspaceEstimate:
    projector: Optional[np.ndarray]
    dimension: int
    triggered: bool


def estimate_primary_direction(
    eigvals: np.ndarray,
    eigvecs: np.ndarray,
    min_eigengap_ratio: float,
) -> PrimaryDirectionEstimate:
    """Always return the minimum-eigenvalue direction for a valid spectrum."""

    values, vectors = _validate_eigensystem(eigvals, eigvecs)
    if float(min_eigengap_ratio) < 0.0:
        raise ValueError("min_eigengap_ratio must be non-negative")
    order = np.argsort(values)
    ordered = np.maximum(values[order], 0.0)
    lambda_max = max(float(ordered[-1]), 1.0e-12)
    lambda_min = float(ordered[0])
    lambda_next = float(ordered[1]) if ordered.size > 1 else lambda_min
    direction = np.asarray(vectors[:, int(order[0])], dtype=float)
    norm = float(np.linalg.norm(direction))
    if norm < 1.0e-12:
        raise ValueError("Primary eigenvector has zero norm")
    direction = _canonical_sign(direction / norm)
    eigengap_ratio = (lambda_next - lambda_min) / lambda_max
    return PrimaryDirectionEstimate(
        direction=direction,
        lambda_min_ratio=lambda_min / lambda_max,
        eigengap_ratio=float(eigengap_ratio),
        direction_stable=bool(eigengap_ratio >= float(min_eigengap_ratio)),
    )


def estimate_weak_subspace(
    eigvals: np.ndarray,
    eigvecs: np.ndarray,
    tau_w: float,
) -> WeakSubspaceEstimate:
    """Return an explicit empty estimate when the legacy ratio does not trigger."""

    weak = extract_weak_subspace(eigvals, eigvecs, tau_w)
    dimension = int(weak.shape[1])
    if dimension == 0:
        return WeakSubspaceEstimate(projector=None, dimension=0, triggered=False)
    return WeakSubspaceEstimate(projector=weak @ weak.T, dimension=dimension, triggered=True)


def extract_weak_subspace(eigvals: np.ndarray, eigvecs: np.ndarray, tau_w: float) -> np.ndarray:
    """Return weak eigenvectors V_W = {v_i | lambda_i / lambda_1 < tau_w}."""

    values, vectors = _validate_eigensystem(eigvals, eigvecs)
    if float(tau_w) <= 0.0:
        raise ValueError("tau_w must be positive")
    clamped = np.maximum(values, 0.0)
    lambda_max = float(np.max(clamped))
    if lambda_max <= 1.0e-12:
        return np.zeros((vectors.shape[0], 0), dtype=float)
    weak_mask = (clamped / lambda_max) < float(tau_w)
    return vectors[:, weak_mask]


def get_primary_weak_direction(eigvals: np.ndarray, eigvecs: np.ndarray) -> np.ndarray:
    """Deprecated compatibility wrapper for the primary direction."""

    return estimate_primary_direction(eigvals, eigvecs, 0.0).direction


def translation_component(v: np.ndarray) -> np.ndarray:
    """Return normalized translation component v_p = normalize(v[3:6])."""

    vector = np.asarray(v, dtype=float)
    if vector.shape != (6,):
        raise ValueError(f"Weak direction must have shape [6], got {vector.shape}")
    if not np.all(np.isfinite(vector)):
        return np.full(3, np.nan, dtype=float)
    trans = vector[3:6]
    norm = float(np.linalg.norm(trans))
    if norm < 1.0e-12:
        return np.full(3, np.nan, dtype=float)
    return trans / norm


def compute_axis_alignment(weak_dir_translation: np.ndarray, axis: np.ndarray) -> float:
    """Compute sign-invariant alignment |v_p^T a|."""

    weak = _normalize_or_nan(weak_dir_translation)
    axis_unit = _normalize_or_nan(axis)
    if np.any(~np.isfinite(weak)) or np.any(~np.isfinite(axis_unit)):
        return float("nan")
    return float(np.clip(abs(float(weak @ axis_unit)), 0.0, 1.0))


def compute_drift_alignment(weak_dir_translation: np.ndarray, drift_vector: np.ndarray) -> float:
    """Compute sign-invariant alignment |v_p^T d| with an observed drift vector."""

    weak = _normalize_or_nan(weak_dir_translation)
    drift = _normalize_or_nan(drift_vector)
    if np.any(~np.isfinite(weak)) or np.any(~np.isfinite(drift)):
        return float("nan")
    return float(np.clip(abs(float(weak @ drift)), 0.0, 1.0))


def is_direction_reliable(
    eigvals: np.ndarray,
    eigvecs: np.ndarray,
    min_gap_ratio: float,
    min_translation_norm: float,
) -> bool:
    """Check whether the primary weak direction is spectrally and physically usable.

    The same ratio threshold is used to require an actual near-null direction
    and a non-isotropic separation from the next-smallest eigenvalue.
    """

    values, vectors = _validate_eigensystem(eigvals, eigvecs)
    if min_gap_ratio <= 0.0:
        raise ValueError("min_gap_ratio must be positive")
    if min_translation_norm < 0.0:
        raise ValueError("min_translation_norm must be non-negative")

    clamped = np.maximum(values, 0.0)
    lambda_max = float(np.max(clamped))
    if lambda_max <= 1.0e-12:
        return False

    min_index = int(np.argmin(values))
    trans_slice = vectors[:, min_index] if values.size == 3 else vectors[3:6, min_index]
    trans_norm = float(np.linalg.norm(trans_slice))
    if trans_norm < float(min_translation_norm):
        return False

    ordered = np.sort(clamped)
    lambda_min = float(ordered[0])
    lambda_next = float(ordered[1]) if ordered.size > 1 else lambda_min
    min_ratio = lambda_min / lambda_max
    gap_ratio = (lambda_next - lambda_min) / lambda_max
    return bool(min_ratio <= float(min_gap_ratio) and gap_ratio >= float(min_gap_ratio))


def _validate_eigensystem(eigvals: np.ndarray, eigvecs: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    values = np.asarray(eigvals, dtype=float)
    vectors = np.asarray(eigvecs, dtype=float)
    if values.ndim != 1:
        raise ValueError("eigvals must be a 1-D array")
    if vectors.shape != (values.size, values.size):
        raise ValueError(f"eigvecs must have shape [{values.size}, {values.size}], got {vectors.shape}")
    if values.size not in {3, 6}:
        raise ValueError(f"Expected 3 translation or 6 pose eigenvalues, got {values.size}")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(vectors)):
        raise ValueError("Eigensystem contains NaN or Inf")
    return values, vectors


def compute_weak_projector(
    eigvals: np.ndarray,
    eigvecs: np.ndarray,
    tau_w: float,
) -> Optional[np.ndarray]:
    """Deprecated compatibility wrapper; an empty subspace returns ``None``."""

    return estimate_weak_subspace(eigvals, eigvecs, tau_w).projector


def compute_subspace_axis_alignment(projector: Optional[np.ndarray], axis: np.ndarray) -> float:
    if projector is None:
        return float("nan")
    matrix = np.asarray(projector, dtype=float)
    direction = np.asarray(axis, dtype=float)
    if matrix.shape != (direction.size, direction.size):
        raise ValueError("projector shape must match axis dimension")
    if float(np.trace(matrix)) <= 1.0e-12:
        return float("nan")
    unit = _normalize_or_nan(direction) if direction.size == 3 else direction / np.linalg.norm(direction)
    if not np.all(np.isfinite(unit)):
        return float("nan")
    value = float(unit.T @ matrix @ unit)
    return float(np.sqrt(np.clip(value, 0.0, 1.0)))


def _normalize_or_nan(values: np.ndarray) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        return np.full(3, np.nan, dtype=float)
    norm = float(np.linalg.norm(vector))
    if norm < 1.0e-12:
        return np.full(3, np.nan, dtype=float)
    return vector / norm


def _canonical_sign(vector: np.ndarray) -> np.ndarray:
    index = int(np.argmax(np.abs(vector)))
    if vector[index] < 0.0:
        return -vector
    return vector
