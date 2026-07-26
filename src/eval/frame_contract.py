"""Coordinate-frame contracts used only by the Measurement pilot audit."""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np

from degen_detector.whitened_info import compute_translation_schur_info


WEAK_DIRECTION_NATIVE_FRAME = "FAST_LIO_CAMERA_INIT_WORLD_MAP"
REFERENCE_AXIS_FRAME = "ENU"
COMPARISON_FRAME = "ENU"
FORMAL_LINEARIZATION_STATE = "CURRENT_ITERATED_IN_CALL_STATE_s"
PRIOR_POSE_ROLE = "TAP_SAVED_PRIOR_IS_METADATA_ONLY_NOT_REAPPLIED_TO_WEAK_AXIS"
POST_UPDATE_POSE_ROLE = "NOT_AVAILABLE_TO_IN_CALL_JACOBIAN_OR_WEAK_AXIS"
LIDAR_TO_IMU_ROLE = "FORWARD_IMU_FROM_LIDAR_APPLIED_UPSTREAM_IN_JACOBIAN"
OFFLINE_DIRECTION_TRANSFORM = "KABSCH_ROTATION_ONLY_NO_TRANSLATION"


def normalize_axis(value: Sequence[float]) -> np.ndarray:
    axis = np.asarray(value, dtype=np.float64)
    if axis.shape != (3,) or not np.all(np.isfinite(axis)):
        raise ValueError("axis must be a finite 3-vector")
    norm = float(np.linalg.norm(axis))
    if norm <= 1.0e-12:
        raise ValueError("axis must be nonzero")
    return axis / norm


def validate_rotation_matrix(rotation: np.ndarray, *, tolerance: float = 1.0e-10) -> np.ndarray:
    value = np.asarray(rotation, dtype=np.float64)
    if value.shape != (3, 3) or not np.all(np.isfinite(value)):
        raise ValueError("rotation must be a finite 3 x 3 matrix")
    if not np.allclose(value.T @ value, np.eye(3), atol=tolerance, rtol=0.0):
        raise ValueError("rotation is not orthonormal")
    if not math.isclose(float(np.linalg.det(value)), 1.0, abs_tol=tolerance):
        raise ValueError("rotation determinant must be +1")
    return value


def transform_axis(rotation_target_from_source: np.ndarray, axis_source: Sequence[float]) -> np.ndarray:
    rotation = validate_rotation_matrix(rotation_target_from_source)
    return normalize_axis(rotation @ normalize_axis(axis_source))


def transform_lidar_axis_to_world(
    axis_lidar: Sequence[float],
    rotation_imu_from_lidar: np.ndarray,
    rotation_world_from_imu: np.ndarray,
) -> np.ndarray:
    """Validate the forward LiDAR -> IMU -> world convention for a LiDAR axis.

    This helper tests the upstream FAST-LIO transform convention.  It is not an
    operation in the exported weak-axis pipeline: the translation Schur
    eigenvector is already expressed in FAST-LIO world coordinates.
    """

    return transform_axis(
        validate_rotation_matrix(rotation_world_from_imu)
        @ validate_rotation_matrix(rotation_imu_from_lidar),
        axis_lidar,
    )


def sign_invariant_angle_deg(left: Sequence[float], right: Sequence[float]) -> float:
    a = normalize_axis(left)
    b = normalize_axis(right)
    cosine = float(np.clip(abs(float(a @ b)), 0.0, 1.0))
    return math.degrees(math.acos(cosine))


def coordinate_frame_contract_rows() -> list[dict[str, Any]]:
    return [
        {
            "stage": "FAST_LIO_native_state",
            "input_frame": "IMU/body right-tangent rotation plus world additive position",
            "output_frame": "native [delta_p_world, delta_theta_body]",
            "transform": "FAST-LIO boxplus contract",
            "linearization_state": FORMAL_LINEARIZATION_STATE,
            "saved_prior_pose_role": PRIOR_POSE_ROLE,
            "post_update_pose_role": POST_UPDATE_POSE_ROLE,
            "source_file": "/home/lj/fastlio2_ws/src/FAST_LIO/include/use-ikfom.hpp",
            "source_line": "12-21; laserMapping.cpp:923-1068, 1568-1575",
            "verified": True,
        },
        {
            "stage": "formal_in_call_linearization",
            "input_frame": "LiDAR point transformed by current s.offset_R_L_I, s.offset_T_L_I, s.rot, and s.pos",
            "output_frame": "formal native Jacobian [delta_p_world, delta_theta_body, ...]",
            "transform": "h_share_model evaluates correspondences, residuals, and h_x at the current iterated in-call state s",
            "linearization_state": FORMAL_LINEARIZATION_STATE,
            "saved_prior_pose_role": PRIOR_POSE_ROLE,
            "post_update_pose_role": POST_UPDATE_POSE_ROLE,
            "lidar_to_imu_extrinsic_role": LIDAR_TO_IMU_ROLE,
            "forward_lidar_to_imu_applied_upstream": True,
            "source_file": "/home/lj/fastlio2_ws/src/FAST_LIO/src/laserMapping.cpp",
            "source_line": "923-1068, 1084-1115",
            "verified": True,
        },
        {
            "stage": "readonly_tap_prior_metadata",
            "input_frame": "pre-update FAST-LIO state and covariance",
            "output_frame": "record prior_position_world, prior_orientation_world_from_imu_xyzw, and prior covariance metadata",
            "transform": "copied into the record separately from the formal in-call Jacobian",
            "linearization_state": FORMAL_LINEARIZATION_STATE,
            "saved_prior_pose_role": PRIOR_POSE_ROLE,
            "post_update_pose_role": POST_UPDATE_POSE_ROLE,
            "prior_pose_used_for_weak_axis": False,
            "post_update_pose_used_for_weak_axis": False,
            "source_file": "/home/lj/fastlio2_ws/src/FAST_LIO/src/laserMapping.cpp; /home/lj/fastlio2_ws/src/FAST_LIO/src/readonly_observation_tap.cpp",
            "source_line": "laserMapping.cpp:1458-1487, 1568-1575; readonly_observation_tap.cpp:549-577",
            "verified": True,
        },
        {
            "stage": "readonly_tap_column_reorder",
            "input_frame": "formal h_x at current iterated state s: [delta_p_world, delta_theta_body]",
            "output_frame": "[delta_theta_body, delta_p_world]",
            "transform": "column permutation [3,4,5,0,1,2], no axis rotation",
            "linearization_state": FORMAL_LINEARIZATION_STATE,
            "saved_prior_pose_role": PRIOR_POSE_ROLE,
            "post_update_pose_role": POST_UPDATE_POSE_ROLE,
            "source_file": "/home/lj/fastlio2_ws/src/FAST_LIO/src/readonly_observation_tap.cpp",
            "source_line": "155, 549-574",
            "verified": True,
        },
        {
            "stage": "translation_Schur",
            "input_frame": "detector [delta_theta_body, delta_p_world]",
            "output_frame": WEAK_DIRECTION_NATIVE_FRAME,
            "transform": "marginalize body-rotation columns; minimum-eigenvalue direction of the remaining world-translation block",
            "translation_direction_already_world": True,
            "lidar_to_imu_extrinsic_role": LIDAR_TO_IMU_ROLE,
            "reapply_lidar_to_imu_to_weak_axis": False,
            "prior_pose_used_for_weak_axis": False,
            "post_update_pose_used_for_weak_axis": False,
            "source_file": "src/degen_detector/whitened_info.py",
            "source_line": "85-111; laserMapping.cpp:1036-1065",
            "verified": True,
        },
        {
            "stage": "offline_position_alignment",
            "input_frame": WEAK_DIRECTION_NATIVE_FRAME,
            "output_frame": COMPARISON_FRAME,
            "transform": "v_ENU = R_enu_from_fast_world @ v_world; translation omitted for axis",
            "offline_direction_transform": OFFLINE_DIRECTION_TRANSFORM,
            "translation_direction_already_world": True,
            "reapply_lidar_to_imu_to_weak_axis": False,
            "prior_pose_used_for_weak_axis": False,
            "post_update_pose_used_for_weak_axis": False,
            "source_file": "src/eval/navsat_reference.py; src/eval/measurement_pilot_scientific_audit.py",
            "source_line": "navsat_reference.py:191-214; measurement_pilot_scientific_audit.py:563-587",
            "verified": True,
        },
        {
            "stage": "reference_axis",
            "input_frame": "WGS84 fixes",
            "output_frame": REFERENCE_AXIS_FRAME,
            "transform": "ECEF then standard East/North/Up rotation; endpoint difference",
            "source_file": "src/eval/navsat_reference.py",
            "source_line": "73-164",
            "verified": True,
        },
        {
            "stage": "angle_comparison",
            "input_frame": COMPARISON_FRAME,
            "output_frame": COMPARISON_FRAME,
            "transform": "acos(clamp(abs(dot(unit(v), unit(a))), 0, 1))",
            "source_file": "src/eval/navsat_reference.py",
            "source_line": "297-308",
            "verified": True,
        },
    ]


def rotation_covariance_validation(
    *, random_seed: int = 20260726, random_count: int = 100
) -> list[dict[str, Any]]:
    """Numerically validate translation-Schur/eigenvector SO(3) covariance."""

    rng = np.random.default_rng(random_seed)
    maximum_schur_error = 0.0
    maximum_vector_error = 0.0
    maximum_angle_error = 0.0
    for _ in range(random_count):
        base = rng.normal(size=(6, 6))
        hessian = base.T @ base + np.diag([3.0, 4.0, 5.0, 0.3, 1.2, 3.4])
        matrix = rng.normal(size=(3, 3))
        u, _, vt = np.linalg.svd(matrix)
        rotation = u @ vt
        if np.linalg.det(rotation) < 0.0:
            u[:, -1] *= -1.0
            rotation = u @ vt
        basis = np.block(
            [[np.eye(3), np.zeros((3, 3))], [np.zeros((3, 3)), rotation]]
        )
        transformed = basis @ hessian @ basis.T
        schur = compute_translation_schur_info(hessian)
        schur_transformed = compute_translation_schur_info(transformed)
        maximum_schur_error = max(
            maximum_schur_error,
            float(np.max(np.abs(schur_transformed - rotation @ schur @ rotation.T))),
        )
        _, vectors = np.linalg.eigh(schur)
        _, vectors_transformed = np.linalg.eigh(schur_transformed)
        expected = rotation @ vectors[:, 0]
        observed = vectors_transformed[:, 0]
        maximum_vector_error = max(
            maximum_vector_error,
            min(float(np.linalg.norm(observed - expected)), float(np.linalg.norm(observed + expected))),
        )
        reference = normalize_axis(rng.normal(size=3))
        before = sign_invariant_angle_deg(vectors[:, 0], reference)
        after = sign_invariant_angle_deg(rotation @ vectors[:, 0], rotation @ reference)
        maximum_angle_error = max(maximum_angle_error, abs(before - after))
    return [
        {
            "validation": "random_so3_translation_schur_covariance",
            "random_seed": random_seed,
            "trial_count": random_count,
            "maximum_abs_error": maximum_schur_error,
            "tolerance": 1.0e-12,
            "pass": maximum_schur_error <= 1.0e-12,
        },
        {
            "validation": "random_so3_minimum_eigenvector_covariance_up_to_sign",
            "random_seed": random_seed,
            "trial_count": random_count,
            "maximum_abs_error": maximum_vector_error,
            "tolerance": 1.0e-12,
            "pass": maximum_vector_error <= 1.0e-12,
        },
        {
            "validation": "random_so3_sign_invariant_angle_invariance_degrees",
            "random_seed": random_seed,
            "trial_count": random_count,
            "maximum_abs_error": maximum_angle_error,
            "tolerance": 1.0e-12,
            "pass": maximum_angle_error <= 1.0e-12,
        },
    ]
