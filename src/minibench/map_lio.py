"""Prior-relinearized covariance-aware synthetic MAP estimator for Stage 2B."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

import numpy as np

from degen_detector.odi_tracker import compute_metrics_for_frame
from .motion_simulator import apply_se3_increment, compose_pose_with_body_increment
from .observation_simulator import quat_to_rot, skew_matrix
from .update_strategies import build_normal_equation, execute_update_strategy


def linearize_point_to_plane(
    prior_pose: np.ndarray,
    points_lidar: np.ndarray,
    normals_world: np.ndarray,
    plane_points_world: np.ndarray,
    base_residual: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    pose = np.asarray(prior_pose, dtype=float)
    points = np.asarray(points_lidar, dtype=float)
    normals = np.asarray(normals_world, dtype=float)
    anchors = np.asarray(plane_points_world, dtype=float)
    noise = np.asarray(base_residual, dtype=float)
    if pose.shape != (8,) or points.ndim != 2 or points.shape[1] != 3:
        raise ValueError("prior pose must be [8] and points must be [N,3]")
    if normals.shape != points.shape or anchors.shape != points.shape or noise.shape != (points.shape[0],):
        raise ValueError("point-to-plane inputs have inconsistent shapes")
    rotation = quat_to_rot(pose[4:8])
    world = (rotation @ points.T).T + pose[1:4]
    residual = np.einsum("ij,ij->i", normals, world - anchors) + noise
    jacobian = np.zeros((points.shape[0], 6), dtype=float)
    for index, (point, normal) in enumerate(zip(points, normals)):
        jacobian[index, :3] = normal @ (-rotation @ skew_matrix(point))
        jacobian[index, 3:6] = normal
    return jacobian, residual


def propagate_covariance(
    posterior_covariance: np.ndarray,
    prior_pose: np.ndarray,
    translation_covariance_body: np.ndarray,
    rotation_covariance_local: np.ndarray,
) -> np.ndarray:
    """Propagate correction covariance with F = I controlled approximation.

    F = I is a controlled first-order approximation for Stage 2B.
    """

    posterior = _validate_covariance(posterior_covariance)
    translation_body = np.asarray(translation_covariance_body, dtype=float)
    rotation_local = np.asarray(rotation_covariance_local, dtype=float)
    if translation_body.shape != (3, 3) or rotation_local.shape != (3, 3):
        raise ValueError("process covariance blocks must be 3x3")
    rotation = quat_to_rot(np.asarray(prior_pose, dtype=float)[4:8])
    process = np.zeros((6, 6), dtype=float)
    process[:3, :3] = rotation_local
    process[3:6, 3:6] = rotation @ translation_body @ rotation.T
    return _validate_covariance(posterior + process)


def run_map_lio(
    observations: Mapping[str, np.ndarray],
    motion_measurements: Mapping[str, np.ndarray],
    detector_config: Mapping[str, Any],
    update_config: Mapping[str, Any],
    strategy: str,
    online_odi_threshold: float,
    attenuation_alpha: float,
    oracle_directions: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    required = [
        "timestamps", "points_lidar", "normals_world", "plane_points_world",
        "r_list", "R_diag_list",
    ]
    if any(name not in observations for name in required):
        raise ValueError("Stage 2B observations are incomplete")
    points = np.asarray(observations["points_lidar"], dtype=float)
    normals = np.asarray(observations["normals_world"], dtype=float)
    anchors = np.asarray(observations["plane_points_world"], dtype=float)
    base_residual = np.asarray(observations["r_list"], dtype=float)
    variances = np.asarray(observations["R_diag_list"], dtype=float)
    timestamps = np.asarray(observations["timestamps"], dtype=float)
    frame_count = timestamps.size
    translations = np.asarray(motion_measurements["delta_translation_body"], dtype=float)
    rotations = np.asarray(motion_measurements["delta_rotation_vector"], dtype=float)
    translation_covariance = np.asarray(motion_measurements["translation_covariance_body"], dtype=float)
    rotation_covariance = np.asarray(motion_measurements["rotation_covariance_local"], dtype=float)
    if translations.shape != (frame_count - 1, 3) or rotations.shape != (frame_count - 1, 3):
        raise ValueError("motion measurement count does not match observations")
    if int(update_config.get("lidar_update_iterations", 1)) != 1:
        raise ValueError("Stage 2B freezes lidar_update_iterations at one")
    if strategy == "huber_oracle_selective" and oracle_directions is None:
        raise ValueError("oracle_only offline_evaluation_only direction is required")
    if strategy != "huber_oracle_selective" and oracle_directions is not None:
        raise ValueError("GT directions are isolated to the oracle_only path")

    poses = np.zeros((frame_count, 8), dtype=float)
    poses[0] = np.asarray(motion_measurements["initial_pose"], dtype=float)
    covariance = np.diag(np.asarray(update_config["initial_covariance_diag"], dtype=float))
    covariance = _validate_covariance(covariance)
    covariance_history = np.zeros((frame_count, 6, 6), dtype=float)
    covariance_history[0] = covariance
    diagnostics = []
    solver_failures = 0
    detector_runtime = dict(detector_config)
    detector_runtime["odi_trigger_threshold"] = float(online_odi_threshold)
    for frame in range(1, frame_count):
        prior = compose_pose_with_body_increment(poses[frame - 1], translations[frame - 1], rotations[frame - 1])
        prior[0] = timestamps[frame]
        covariance_prior = propagate_covariance(
            covariance,
            prior,
            _frame_covariance(translation_covariance, frame - 1),
            _frame_covariance(rotation_covariance, frame - 1),
        )
        J, residual = linearize_point_to_plane(
            prior, points[frame], normals[frame], anchors[frame], base_residual[frame]
        )
        detector = compute_metrics_for_frame(J, variances[frame], detector_runtime, axis=None)
        triggered = bool(detector["degeneracy_triggered"])
        stable = bool(detector["primary_direction_stable"])
        actionable = bool(triggered and stable)
        detected_direction = np.array(
            [detector["primary_weak_dir_x"], detector["primary_weak_dir_y"], detector["primary_weak_dir_z"]]
        )
        direction = detected_direction
        if strategy == "huber_oracle_selective":
            direction = np.asarray(oracle_directions[frame], dtype=float)
            actionable = triggered
        normal = build_normal_equation(
            J,
            residual,
            variances[frame],
            float(update_config["huber_delta_sigma"]),
        )
        try:
            update = execute_update_strategy(
                strategy,
                covariance_prior,
                normal,
                attenuation_alpha,
                triggered,
                actionable,
                direction,
            )
        except (ValueError, RuntimeError, np.linalg.LinAlgError):
            solver_failures += 1
            update_delta = np.zeros(6, dtype=float)
            update_covariance = covariance_prior
            solver_condition_number = float("inf")
        else:
            update_delta = update.delta
            update_covariance = update.posterior_covariance
            solver_condition_number = update.solver_condition_number
        poses[frame] = apply_se3_increment(prior, update_delta)
        poses[frame, 0] = timestamps[frame]
        covariance = update_covariance
        covariance_history[frame] = covariance
        weak_component = abs(float(detected_direction @ update_delta[3:6]))
        strong_vector = update_delta[3:6] - detected_direction * float(detected_direction @ update_delta[3:6])
        diagnostics.append(
            {
                "frame_index": frame,
                "ODI_trans": float(detector["ODI_trans"]),
                "degeneracy_triggered": triggered,
                "primary_direction_stable": stable,
                "actionable_direction": actionable,
                "weak_update_component_abs": weak_component,
                "strong_update_component_norm": float(np.linalg.norm(strong_vector)),
                "rotation_update_norm": float(np.linalg.norm(update_delta[:3])),
                "update_norm": float(np.linalg.norm(update_delta)),
                "solver_condition_number": solver_condition_number,
                "posterior_covariance_trace": float(np.trace(covariance)),
                "huber_outlier_ratio": float(np.mean(normal.robust_weights < 1.0)),
                "contaminated_measurement_ratio": float(
                    np.mean(np.asarray(observations.get("contamination_mask", np.zeros_like(base_residual, dtype=bool)))[frame])
                ),
            }
        )
    return {
        "poses": poses,
        "covariances": covariance_history,
        "frame_diagnostics": diagnostics,
        "solver_failure_count": solver_failures,
        "strategy": strategy,
    }


def _frame_covariance(values: np.ndarray, index: int) -> np.ndarray:
    if values.shape == (3, 3):
        return values
    if values.ndim == 3 and values.shape[1:] == (3, 3):
        return values[index]
    raise ValueError("motion covariance must be [3,3] or [N,3,3]")


def _validate_covariance(matrix: np.ndarray) -> np.ndarray:
    value = np.asarray(matrix, dtype=float)
    if value.shape != (6, 6) or not np.all(np.isfinite(value)):
        raise ValueError("covariance must be finite and 6x6")
    value = 0.5 * (value + value.T)
    eigenvalues, eigenvectors = np.linalg.eigh(value)
    if float(np.min(eigenvalues)) < -1.0e-10:
        raise ValueError("covariance is not PSD")
    eigenvalues = np.maximum(eigenvalues, 0.0)
    return 0.5 * ((eigenvectors * eigenvalues) @ eigenvectors.T + (eigenvectors * eigenvalues) @ eigenvectors.T)
