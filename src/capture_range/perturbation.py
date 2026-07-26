"""Repository-native translation and rotation perturbations."""

from __future__ import annotations

import math

import numpy as np

from minibench.motion_simulator import apply_se3_increment, rotvec_to_quat
from minibench.observation_simulator import quat_to_rot

from .types import PerturbationSpec


def _pose(value: np.ndarray) -> np.ndarray:
    pose = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(pose)):
        raise ValueError("pose must be finite")
    if pose.shape == (8,):
        if float(np.linalg.norm(pose[4:8])) <= 1.0e-12:
            raise ValueError("pose quaternion cannot be zero")
        return pose
    if pose.shape == (4, 4):
        if not np.allclose(pose[3], [0.0, 0.0, 0.0, 1.0], atol=1.0e-12):
            raise ValueError("pose has an invalid homogeneous bottom row")
        rotation = pose[:3, :3]
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1.0e-8) or not np.isclose(
            np.linalg.det(rotation), 1.0, atol=1.0e-8
        ):
            raise ValueError("pose rotation block must be in SO(3)")
        return pose
    raise ValueError("pose must have shape [8] or [4,4]")


def _unit_direction(value: np.ndarray) -> np.ndarray:
    direction = np.asarray(value, dtype=np.float64)
    if direction.shape != (3,) or not np.all(np.isfinite(direction)):
        raise ValueError("direction must be a finite length-3 vector")
    norm = float(np.linalg.norm(direction))
    if norm <= 1.0e-12:
        raise ValueError("direction cannot be zero")
    return direction / norm


def _amplitude(value: float) -> float:
    amplitude = float(value)
    if not math.isfinite(amplitude):
        raise ValueError("signed amplitude must be finite")
    return amplitude


def apply_translation_perturbation(
    reference_pose: np.ndarray,
    direction: np.ndarray,
    signed_amplitude_m: float,
) -> np.ndarray:
    """Apply the frozen world-frame additive translation boxplus.

    Rotation is unchanged, even when the reference orientation is non-identity.
    """

    pose = _pose(reference_pose)
    delta = np.zeros(6, dtype=np.float64)
    delta[3:6] = _unit_direction(direction) * _amplitude(signed_amplitude_m)
    if pose.shape == (8,):
        return apply_se3_increment(pose, delta)
    updated = np.array(pose, dtype=np.float64, copy=True)
    updated[:3, 3] += delta[3:6]
    return updated


def apply_rotation_perturbation(
    reference_pose: np.ndarray,
    direction: np.ndarray,
    signed_amplitude_rad: float,
) -> np.ndarray:
    """Apply a right-multiplicative rotation-vector perturbation."""

    pose = _pose(reference_pose)
    delta = np.zeros(6, dtype=np.float64)
    delta[:3] = _unit_direction(direction) * _amplitude(signed_amplitude_rad)
    if pose.shape == (8,):
        return apply_se3_increment(pose, delta)
    updated = np.array(pose, dtype=np.float64, copy=True)
    updated[:3, :3] = pose[:3, :3] @ quat_to_rot(rotvec_to_quat(delta[:3]))
    return updated


def apply_perturbation(
    reference_pose: np.ndarray, perturbation: PerturbationSpec
) -> np.ndarray:
    if perturbation.perturbation_type == "translation":
        return apply_translation_perturbation(
            reference_pose, perturbation.direction, perturbation.signed_amplitude
        )
    if perturbation.perturbation_type == "rotation":
        return apply_rotation_perturbation(
            reference_pose, perturbation.direction, perturbation.signed_amplitude
        )
    raise ValueError(f"unsupported perturbation type: {perturbation.perturbation_type}")
