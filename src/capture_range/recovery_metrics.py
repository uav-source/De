"""Reference-pose recovery errors and frozen success contract."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np


DEFAULT_TRANSLATION_SUCCESS_THRESHOLD_M = 0.02
DEFAULT_ROTATION_SUCCESS_THRESHOLD_RAD = math.radians(0.5)


def _pose_translation(value: Sequence[float] | np.ndarray) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.shape == (8,):
        return array[1:4]
    if array.shape == (4, 4):
        return array[:3, 3]
    raise ValueError("pose must be a native length-8 row or a 4x4 matrix")


def _pose_quaternion(value: Sequence[float] | np.ndarray) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.shape == (4,):
        quaternion = array
    elif array.shape == (8,):
        quaternion = array[4:8]
    else:
        raise ValueError("rotation input must be xyzw quaternion [4] or native pose [8]")
    if not np.all(np.isfinite(quaternion)):
        raise ValueError("quaternion must be finite")
    norm = float(np.linalg.norm(quaternion))
    if norm <= 1.0e-12:
        raise ValueError("quaternion norm must be positive")
    return quaternion / norm


def _pose_rotation_matrix(value: Sequence[float] | np.ndarray) -> np.ndarray:
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (4, 4):
        raise ValueError("matrix pose must have shape [4,4]")
    rotation = array[:3, :3]
    if not np.all(np.isfinite(rotation)):
        raise ValueError("rotation matrix must be finite")
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1.0e-8) or not np.isclose(
        np.linalg.det(rotation), 1.0, atol=1.0e-8
    ):
        raise ValueError("rotation matrix must be in SO(3)")
    return rotation


def translation_error_m(
    final_pose: Sequence[float] | np.ndarray,
    reference_pose: Sequence[float] | np.ndarray,
) -> float:
    final = _pose_translation(final_pose)
    reference = _pose_translation(reference_pose)
    if not np.all(np.isfinite(final)) or not np.all(np.isfinite(reference)):
        return float("nan")
    return float(np.linalg.norm(final - reference))


def rotation_geodesic_error_rad(
    final_pose_or_quaternion: Sequence[float] | np.ndarray,
    reference_pose_or_quaternion: Sequence[float] | np.ndarray,
) -> float:
    """Stable, quaternion-sign-invariant SO(3) geodesic distance."""

    final_value = np.asarray(final_pose_or_quaternion)
    reference_value = np.asarray(reference_pose_or_quaternion)
    if final_value.shape == (4, 4) or reference_value.shape == (4, 4):
        if final_value.shape != (4, 4) or reference_value.shape != (4, 4):
            raise ValueError("rotation representations must match")
        final_rotation = _pose_rotation_matrix(final_value)
        reference_rotation = _pose_rotation_matrix(reference_value)
        relative = reference_rotation.T @ final_rotation
        cosine = float(np.clip((np.trace(relative) - 1.0) * 0.5, -1.0, 1.0))
        sine = 0.5 * float(
            np.linalg.norm(
                [
                    relative[2, 1] - relative[1, 2],
                    relative[0, 2] - relative[2, 0],
                    relative[1, 0] - relative[0, 1],
                ]
            )
        )
        return math.atan2(sine, cosine)
    final = _pose_quaternion(final_value)
    reference = _pose_quaternion(reference_value)
    if float(np.dot(final, reference)) < 0.0:
        final = -final
    numerator = float(np.linalg.norm(final - reference))
    denominator = float(np.linalg.norm(final + reference))
    # ``atan2(||q1-q2||, ||q1+q2||)`` is one quarter of the physical SO(3)
    # angle for sign-aligned unit quaternions.
    return 4.0 * math.atan2(numerator, denominator)


def evaluate_recovery_success(
    translation_error_m: float,
    rotation_error_rad: float,
    *,
    solver_converged: bool,
    finite_result: bool,
    iteration_limit_not_failed: bool,
    translation_success_threshold_m: float = DEFAULT_TRANSLATION_SUCCESS_THRESHOLD_M,
    rotation_success_threshold_rad: float = DEFAULT_ROTATION_SUCCESS_THRESHOLD_RAD,
) -> bool:
    """Apply the frozen Day 1 success predicate.

    Final cost is intentionally absent: residual alone cannot establish
    recovery to the independent reference pose.
    """

    translation_threshold = float(translation_success_threshold_m)
    rotation_threshold = float(rotation_success_threshold_rad)
    if not math.isfinite(translation_threshold) or translation_threshold < 0.0:
        raise ValueError("translation success threshold must be finite and non-negative")
    if not math.isfinite(rotation_threshold) or rotation_threshold < 0.0:
        raise ValueError("rotation success threshold must be finite and non-negative")
    errors_finite = math.isfinite(float(translation_error_m)) and math.isfinite(
        float(rotation_error_rad)
    )
    return bool(
        errors_finite
        and float(translation_error_m) <= translation_threshold
        and float(rotation_error_rad) <= rotation_threshold
        and solver_converged
        and finite_result
        and iteration_limit_not_failed
    )


def is_recovery_success(*args, **kwargs) -> bool:
    """Compatibility alias for :func:`evaluate_recovery_success`."""

    return evaluate_recovery_success(*args, **kwargs)
