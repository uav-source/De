"""Post-estimation metrics for covariance-aware update experiments."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

import numpy as np


def compute_update_metrics(
    estimated_poses: np.ndarray,
    ground_truth_poses: np.ndarray,
    axes: np.ndarray,
    frame_diagnostics: Sequence[Mapping[str, Any]],
    covariances: np.ndarray | None = None,
) -> Dict[str, float]:
    estimate = np.asarray(estimated_poses, dtype=float)
    truth = np.asarray(ground_truth_poses, dtype=float)
    directions = _normalize_rows(np.asarray(axes, dtype=float))
    if estimate.shape != truth.shape or estimate.ndim != 2 or estimate.shape[1] != 8:
        raise ValueError("estimated and ground-truth poses must have shape [N,8]")
    translation_error = estimate[:, 1:4] - truth[:, 1:4]
    axis_signed = np.einsum("ij,ij->i", translation_error, directions)
    axis_abs = np.abs(axis_signed)
    strong_vectors = translation_error - axis_signed[:, None] * directions
    strong_norm = np.linalg.norm(strong_vectors, axis=1)
    trajectory_norm = np.linalg.norm(translation_error, axis=1)
    orientation = quaternion_geodesic_errors(estimate[:, 4:8], truth[:, 4:8])
    diagnostics = list(frame_diagnostics)
    values = {
        "axis_rmse": _rmse(axis_signed),
        "axis_mae": float(np.mean(axis_abs)),
        "final_axis_error_abs": float(axis_abs[-1]),
        "q95_axis_error_abs": float(np.quantile(axis_abs, 0.95)),
        "strong_translation_rmse": _rmse(strong_norm),
        "strong_translation_mae": float(np.mean(strong_norm)),
        "final_strong_translation_error": float(strong_norm[-1]),
        "trajectory_rmse_3d": _rmse(trajectory_norm),
        "final_translation_error_3d": float(trajectory_norm[-1]),
        "orientation_rmse_rad": _rmse(orientation),
        "orientation_mae_rad": float(np.mean(orientation)),
        "final_orientation_error_rad": float(orientation[-1]),
        "trigger_rate": _diagnostic_mean(diagnostics, "degeneracy_triggered"),
        "primary_direction_stable_rate": _diagnostic_mean(diagnostics, "primary_direction_stable"),
        "actionable_rate": _diagnostic_mean(diagnostics, "actionable_direction"),
        "mean_weak_update_component": _diagnostic_mean(diagnostics, "weak_update_component_abs"),
        "mean_strong_update_component": _diagnostic_mean(diagnostics, "strong_update_component_norm"),
        "mean_rotation_update_norm": _diagnostic_mean(diagnostics, "rotation_update_norm"),
        "q95_update_norm": _diagnostic_quantile(diagnostics, "update_norm", 0.95),
        "mean_solver_condition_number": _diagnostic_mean(diagnostics, "solver_condition_number"),
        "mean_posterior_covariance_trace": _diagnostic_mean(diagnostics, "posterior_covariance_trace"),
        "huber_outlier_ratio": _diagnostic_mean(diagnostics, "huber_outlier_ratio"),
        "contaminated_measurement_ratio": _diagnostic_mean(diagnostics, "contaminated_measurement_ratio"),
    }
    values["pose_nees_approx"] = approximate_pose_nees(translation_error, orientation, covariances)
    return values


def quaternion_geodesic_errors(estimate: np.ndarray, truth: np.ndarray) -> np.ndarray:
    left = _normalize_rows(np.asarray(estimate, dtype=float))
    right = _normalize_rows(np.asarray(truth, dtype=float))
    inner = np.clip(np.abs(np.einsum("ij,ij->i", left, right)), 0.0, 1.0)
    return 2.0 * np.arccos(inner)


def approximate_pose_nees(
    translation_error: np.ndarray,
    orientation_error: np.ndarray,
    covariances: np.ndarray | None,
) -> float:
    if covariances is None:
        return float("nan")
    values = []
    for index in range(1, len(translation_error)):
        error = np.concatenate([[orientation_error[index], 0.0, 0.0], translation_error[index]])
        covariance = np.asarray(covariances[index], dtype=float)
        try:
            values.append(float(error @ np.linalg.solve(covariance, error)))
        except np.linalg.LinAlgError:
            return float("nan")
    return float(np.mean(values)) if values else float("nan")


def _rmse(values: np.ndarray) -> float:
    array = np.asarray(values, dtype=float)
    return float(np.sqrt(np.mean(array**2)))


def _normalize_rows(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1)
    if np.any(norms <= 1.0e-12):
        raise ValueError("cannot normalize zero row")
    return values / norms[:, None]


def _diagnostic_mean(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    return float(np.mean([float(row[field]) for row in rows])) if rows else 0.0


def _diagnostic_quantile(rows: Sequence[Mapping[str, Any]], field: str, quantile: float) -> float:
    return float(np.quantile([float(row[field]) for row in rows], quantile)) if rows else 0.0
