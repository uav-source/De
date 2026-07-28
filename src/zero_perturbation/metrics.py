"""Pose-error, full/frozen, and traditional information metrics."""

from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np
from scipy.spatial.transform import Rotation

from capture_range.registration_core import pose_rotation_translation, registration_options
from degen_detector.odi_tracker import compute_ODI, compute_effective_rank
from degen_detector.whitened_info import compute_AIS, compute_epsilon


def pose_matrix(pose: np.ndarray) -> np.ndarray:
    value = np.asarray(pose, dtype=np.float64)
    if value.shape == (4, 4):
        return np.array(value, copy=True)
    if value.shape != (8,):
        raise ValueError("pose must be a TUM row or 4x4 matrix")
    rotation, translation = pose_rotation_translation(value)
    result = np.eye(4, dtype=np.float64)
    result[:3, :3] = rotation
    result[:3, 3] = translation
    return result


def matrix_to_tum(matrix: np.ndarray, timestamp: float = 0.0) -> np.ndarray:
    value = pose_matrix(matrix)
    quaternion = Rotation.from_matrix(value[:3, :3]).as_quat()
    return np.asarray([timestamp, *value[:3, 3], *quaternion], dtype=np.float64)


def rotation_vector(reference_pose: np.ndarray, estimated_pose: np.ndarray) -> np.ndarray:
    reference = pose_matrix(reference_pose)
    estimated = pose_matrix(estimated_pose)
    return Rotation.from_matrix(reference[:3, :3].T @ estimated[:3, :3]).as_rotvec()


def translation_vector(reference_pose: np.ndarray, estimated_pose: np.ndarray) -> np.ndarray:
    reference = pose_matrix(reference_pose)
    estimated = pose_matrix(estimated_pose)
    return estimated[:3, 3] - reference[:3, 3]


def zero_initialization_error(
    reference_pose: np.ndarray, estimated_pose: np.ndarray
) -> dict[str, float]:
    rho = translation_vector(reference_pose, estimated_pose)
    phi = rotation_vector(reference_pose, estimated_pose)
    return {
        "translation_x_m": float(rho[0]),
        "translation_y_m": float(rho[1]),
        "translation_z_m": float(rho[2]),
        "rotation_x_rad": float(phi[0]),
        "rotation_y_rad": float(phi[1]),
        "rotation_z_rad": float(phi[2]),
        "translation_error_m": float(np.linalg.norm(rho)),
        "rotation_error_rad": float(np.linalg.norm(phi)),
        "rotation_error_deg": float(math.degrees(np.linalg.norm(phi))),
    }


def full_frozen_pose_difference(
    full_pose: np.ndarray, frozen_pose: np.ndarray
) -> dict[str, float]:
    full = pose_matrix(full_pose)
    frozen = pose_matrix(frozen_pose)
    delta = np.linalg.inv(frozen) @ full
    return {
        "full_frozen_translation_difference_m": float(np.linalg.norm(delta[:3, 3])),
        "full_frozen_rotation_difference_rad": float(
            np.linalg.norm(Rotation.from_matrix(delta[:3, :3]).as_rotvec())
        ),
    }


def _huber_weighted_system(
    jacobian: np.ndarray, residual: np.ndarray, huber_delta_m: float
) -> tuple[np.ndarray, np.ndarray]:
    jacobian = np.asarray(jacobian, dtype=np.float64)
    residual = np.asarray(residual, dtype=np.float64)
    if jacobian.ndim != 2 or jacobian.shape[1] != 6:
        raise ValueError("jacobian must have shape [N,6]")
    if residual.shape != (jacobian.shape[0],):
        raise ValueError("residual must match jacobian rows")
    absolute = np.abs(residual)
    weights = np.ones_like(absolute)
    outside = absolute > float(huber_delta_m)
    weights[outside] = float(huber_delta_m) / absolute[outside]
    square_root = np.sqrt(weights)
    return jacobian * square_root[:, None], residual * square_root


def traditional_information_metrics(
    evaluation: Any,
    registration_config: Mapping[str, Any],
    *,
    rotation_scale: float = 0.05,
    translation_scale: float = 0.5,
    epsilon_ratio: float = 1.0e-6,
) -> dict[str, float]:
    """Compute unchanged ODI/AIS definitions on one robust weighted system."""

    options = registration_options(registration_config)
    weighted_jacobian, weighted_residual = _huber_weighted_system(
        evaluation.jacobian, evaluation.residual, options.huber_delta_m
    )
    scaling = np.diag(
        [rotation_scale, rotation_scale, rotation_scale, translation_scale, translation_scale, translation_scale]
    )
    whitened = weighted_jacobian @ scaling
    hessian = whitened.T @ whitened
    hessian = 0.5 * (hessian + hessian.T)
    gradient = whitened.T @ weighted_residual
    eigenvalues = np.linalg.eigvalsh(hessian)
    epsilon = compute_epsilon(eigenvalues, "relative_trace", epsilon_ratio)
    lambda_min = float(np.min(eigenvalues))
    lambda_max = float(np.max(eigenvalues))
    effective_rank = compute_effective_rank(eigenvalues, epsilon)
    return {
        "initial_gradient_norm": float(np.linalg.norm(gradient)),
        "lambda_min": lambda_min,
        "condition_number": float(lambda_max / max(lambda_min, epsilon)),
        "lambda_min_over_lambda_max": (
            float(lambda_min / lambda_max) if lambda_max > 0.0 else float("nan")
        ),
        "spectral_entropy": float(math.log(effective_rank)),
        "effective_rank": float(effective_rank),
        "ODI": float(compute_ODI(eigenvalues, epsilon)),
        "AIS": float(compute_AIS(hessian, epsilon)),
        "correspondence_count": int(evaluation.correspondence_count),
    }


__all__ = [
    "full_frozen_pose_difference",
    "matrix_to_tum",
    "pose_matrix",
    "rotation_vector",
    "traditional_information_metrics",
    "translation_vector",
    "zero_initialization_error",
]
