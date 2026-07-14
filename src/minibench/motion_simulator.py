"""Deterministic 6DoF motion-propagation surrogate retained for historical reproduction.

This is not a full IMU model. Ground truth is consumed only here to synthesize
standalone relative-motion measurements; the estimator reads the saved
measurements and never reconstructs ground-truth deltas.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from .observation_simulator import quat_to_rot


def simulate_motion_measurements(
    gt_poses: np.ndarray,
    process_seed: int,
    config: Dict[str, Any],
    axes: Optional[np.ndarray] = None,
    motion_profile_id: str = "default_motion_profile",
    experiment_family: Optional[str] = None,
    geometry_seed: Optional[int] = None,
    sensor_seed: Optional[int] = None,
) -> Dict[str, np.ndarray]:
    poses = np.asarray(gt_poses, dtype=float)
    if poses.ndim != 2 or poses.shape[1] != 8 or poses.shape[0] < 1:
        raise ValueError("gt_poses must have shape [N, 8]")
    context = [experiment_family, geometry_seed, sensor_seed]
    if all(value is not None for value in context):
        resolved_noise_seed = derive_process_noise_seed(
            str(experiment_family),
            int(geometry_seed),
            int(sensor_seed),
            int(process_seed),
            motion_profile_id,
        )
    elif any(value is not None for value in context):
        raise ValueError("experiment_family, geometry_seed, and sensor_seed must be provided together")
    else:
        # Preserve the compatibility random stream for old runs and tests.
        resolved_noise_seed = process_noise_seed(process_seed, motion_profile_id)
    rng = np.random.default_rng(resolved_noise_seed)
    count = max(poses.shape[0] - 1, 0)
    translation = np.zeros((count, 3), dtype=float)
    rotation = np.zeros((count, 3), dtype=float)
    axis_sigma = float(config.get("axis_sigma", config.get("translation_sigma_m", 0.004)))
    cross_sigma = float(config.get("cross_sigma", config.get("translation_sigma_m", 0.004)))
    translation_noise_frame = str(config.get("translation_noise_frame", "world_axis"))
    if translation_noise_frame not in {"world_axis", "body"}:
        raise ValueError("translation_noise_frame must be 'world_axis' or 'body'")
    forward_sigma = float(config.get("forward_sigma_m", axis_sigma))
    lateral_sigma = float(config.get("lateral_sigma_m", cross_sigma))
    vertical_sigma = float(config.get("vertical_sigma_m", cross_sigma))
    rotation_sigma = np.asarray(
        config.get(
            "rotation_sigma_rad",
            [config.get("roll_sigma", 0.0004), config.get("pitch_sigma", 0.0004), config.get("yaw_sigma", 0.0008)],
        ),
        dtype=float,
    )
    if rotation_sigma.shape == ():
        rotation_sigma = np.full(3, float(rotation_sigma))
    if rotation_sigma.shape != (3,):
        raise ValueError("rotation_sigma_rad must be a scalar or length-3 vector")
    axis_bias = float(config.get("axis_bias", 0.0))

    for index in range(count):
        previous = poses[index]
        current = poses[index + 1]
        R_previous = quat_to_rot(previous[4:8])
        true_translation_body = R_previous.T @ (current[1:4] - previous[1:4])
        q_relative = quat_multiply(quat_conjugate(previous[4:8]), current[4:8])
        true_rotation_vector = quat_to_rotvec(q_relative)

        if translation_noise_frame == "body":
            translation_noise_body = np.array(
                [
                    axis_bias + rng.normal(0.0, forward_sigma),
                    rng.normal(0.0, lateral_sigma),
                    rng.normal(0.0, vertical_sigma),
                ],
                dtype=float,
            )
            translation[index] = true_translation_body + translation_noise_body
        else:
            if axes is None:
                world_axis = np.array([1.0, 0.0, 0.0])
            else:
                world_axis = normalize_vector(np.asarray(axes[index + 1], dtype=float))
            cross_1, cross_2 = orthonormal_cross_basis(world_axis)
            world_noise = (
                world_axis * (axis_bias + rng.normal(0.0, axis_sigma))
                + cross_1 * rng.normal(0.0, cross_sigma)
                + cross_2 * rng.normal(0.0, cross_sigma)
            )
            translation[index] = true_translation_body + R_previous.T @ world_noise
        rotation[index] = true_rotation_vector + rng.normal(0.0, rotation_sigma, size=3)

    if translation_noise_frame == "body":
        translation_covariance_body = np.diag(
            [forward_sigma**2, lateral_sigma**2, vertical_sigma**2]
        )
    else:
        # Historical modes retain their old sampling semantics. This covariance
        # is metadata only and is not consumed by Stage 1c.
        translation_covariance_body = np.diag([axis_sigma**2, cross_sigma**2, cross_sigma**2])
    rotation_covariance_local = np.diag(rotation_sigma**2)

    return {
        "timestamps": poses[:, 0].copy(),
        "initial_pose": poses[0].copy(),
        "delta_translation_body": translation,
        "delta_rotation_vector": rotation,
        "process_seed": np.asarray(int(process_seed), dtype=np.int64),
        "process_noise_seed": np.asarray(resolved_noise_seed, dtype=np.uint64),
        "process_noise_seed_resolved": np.asarray(resolved_noise_seed, dtype=np.uint64),
        "experiment_family": np.asarray("common_legacy" if experiment_family is None else str(experiment_family)),
        "geometry_seed": np.asarray(-1 if geometry_seed is None else int(geometry_seed), dtype=np.int64),
        "sensor_seed": np.asarray(-1 if sensor_seed is None else int(sensor_seed), dtype=np.int64),
        "motion_profile_id": np.asarray(str(motion_profile_id)),
        "surrogate_type": np.asarray("6dof_motion_propagation_surrogate"),
        "translation_noise_frame": np.asarray(translation_noise_frame),
        "translation_covariance_body": translation_covariance_body,
        "rotation_covariance_local": rotation_covariance_local,
    }


def process_noise_seed(process_seed: int, motion_profile_id: str) -> int:
    """Resolve common random numbers without sequence, level, or sensor ids."""

    payload = f"common:{int(process_seed)}:{str(motion_profile_id)}".encode("utf-8")
    # NumPy accepts a 64-bit integer seed; keep this stable across processes.
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def derive_process_noise_seed(
    experiment_family: str,
    geometry_seed: int,
    sensor_seed: int,
    process_seed: int,
    motion_profile_id: str,
) -> int:
    """Derive a Stage 1c seed paired across levels but independent by block.

    Level and sequence identifiers are deliberately absent. SHA-256 is used
    instead of Python's randomized built-in hash, so values are stable across
    processes and PYTHONHASHSEED settings.
    """

    if not str(experiment_family):
        raise ValueError("experiment_family must be non-empty")
    payload = (
        f"{experiment_family}|{int(geometry_seed)}|{int(sensor_seed)}|"
        f"{int(process_seed)}|{motion_profile_id}"
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def process_noise_checksum(measurements: Dict[str, np.ndarray]) -> str:
    """Checksum only stochastic increments, excluding paths and level labels."""

    digest = hashlib.sha256()
    for key in ["delta_translation_body", "delta_rotation_vector"]:
        value = np.asarray(measurements[key])
        digest.update(key.encode("utf-8"))
        digest.update(value.dtype.str.encode("ascii"))
        digest.update(np.ascontiguousarray(value).tobytes())
    return digest.hexdigest()


def save_motion_measurements(measurements: Dict[str, np.ndarray], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **measurements)


def load_motion_measurements(path: str | Path) -> Dict[str, np.ndarray]:
    with np.load(Path(path)) as loaded:
        return {key: loaded[key].copy() for key in loaded.files}


def rotvec_to_quat(rotation_vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(rotation_vector, dtype=float)
    if vector.shape != (3,):
        raise ValueError("rotation_vector must have shape [3]")
    angle = float(np.linalg.norm(vector))
    if angle < 1.0e-10:
        xyz = 0.5 * vector
        quat = np.array([xyz[0], xyz[1], xyz[2], 1.0 - angle * angle / 8.0])
        return quat_normalize(quat)
    axis = vector / angle
    half = 0.5 * angle
    return np.concatenate([axis * np.sin(half), [np.cos(half)]])


def quat_to_rotvec(quaternion: np.ndarray) -> np.ndarray:
    quat = quat_normalize(quaternion)
    if quat[3] < 0.0:
        quat = -quat
    vector_norm = float(np.linalg.norm(quat[:3]))
    if vector_norm < 1.0e-10:
        return 2.0 * quat[:3]
    angle = 2.0 * np.arctan2(vector_norm, float(quat[3]))
    return quat[:3] * (angle / vector_norm)


def quat_multiply(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    x1, y1, z1, w1 = quat_normalize(left)
    x2, y2, z2, w2 = quat_normalize(right)
    return quat_normalize(
        np.array(
            [
                w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
                w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            ],
            dtype=float,
        )
    )


def quat_conjugate(quaternion: np.ndarray) -> np.ndarray:
    quat = quat_normalize(quaternion)
    return np.array([-quat[0], -quat[1], -quat[2], quat[3]], dtype=float)


def quat_normalize(quaternion: np.ndarray) -> np.ndarray:
    quat = np.asarray(quaternion, dtype=float)
    if quat.shape != (4,):
        raise ValueError("quaternion must have shape [4]")
    norm = float(np.linalg.norm(quat))
    if norm < 1.0e-12:
        raise ValueError("Cannot normalize zero quaternion")
    return quat / norm


def apply_se3_increment(pose: np.ndarray, delta: np.ndarray) -> np.ndarray:
    """Apply a right rotational perturbation and world-frame translation update."""

    value = np.asarray(pose, dtype=float)
    increment = np.asarray(delta, dtype=float)
    if value.shape != (8,) or increment.shape != (6,):
        raise ValueError("pose and delta must have shapes [8] and [6]")
    updated = value.copy()
    updated[1:4] = value[1:4] + increment[3:6]
    updated[4:8] = quat_multiply(value[4:8], rotvec_to_quat(increment[:3]))
    return updated


def compose_pose_with_body_increment(
    pose: np.ndarray,
    delta_translation_body: np.ndarray,
    delta_rotation_vector: np.ndarray,
) -> np.ndarray:
    value = np.asarray(pose, dtype=float)
    R = quat_to_rot(value[4:8])
    updated = value.copy()
    updated[1:4] = value[1:4] + R @ np.asarray(delta_translation_body, dtype=float)
    updated[4:8] = quat_multiply(value[4:8], rotvec_to_quat(delta_rotation_vector))
    return updated


def normalize_vector(vector: np.ndarray) -> np.ndarray:
    value = np.asarray(vector, dtype=float)
    norm = float(np.linalg.norm(value))
    if norm < 1.0e-12:
        raise ValueError("Cannot normalize zero vector")
    return value / norm


def orthonormal_cross_basis(axis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    unit = normalize_vector(axis)
    candidate = np.array([0.0, 0.0, 1.0])
    if abs(float(unit @ candidate)) > 0.9:
        candidate = np.array([0.0, 1.0, 0.0])
    first = normalize_vector(np.cross(unit, candidate))
    second = normalize_vector(np.cross(unit, first))
    return first, second
