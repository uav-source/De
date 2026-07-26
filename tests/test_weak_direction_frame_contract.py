import numpy as np

from degen_detector.whitened_info import compute_translation_schur_info
from eval.frame_contract import (
    FORMAL_LINEARIZATION_STATE,
    LIDAR_TO_IMU_ROLE,
    OFFLINE_DIRECTION_TRANSFORM,
    POST_UPDATE_POSE_ROLE,
    PRIOR_POSE_ROLE,
    coordinate_frame_contract_rows,
    rotation_covariance_validation,
)


def test_translation_schur_retains_world_translation_block_after_rotation_marginalization():
    hessian = np.diag([8.0, 9.0, 10.0, 1.0, 3.0, 7.0])
    schur = compute_translation_schur_info(hessian)
    np.testing.assert_allclose(schur, np.diag([1.0, 3.0, 7.0]), atol=1e-12)
    rows = {row["stage"]: row for row in coordinate_frame_contract_rows()}
    assert rows["translation_Schur"]["output_frame"] == "FAST_LIO_CAMERA_INIT_WORLD_MAP"
    assert rows["translation_Schur"]["translation_direction_already_world"] is True


def test_contract_distinguishes_in_call_linearization_from_prior_and_post_update_metadata():
    rows = {row["stage"]: row for row in coordinate_frame_contract_rows()}
    formal = rows["formal_in_call_linearization"]
    metadata = rows["readonly_tap_prior_metadata"]
    schur = rows["translation_Schur"]

    assert formal["linearization_state"] == FORMAL_LINEARIZATION_STATE
    assert formal["saved_prior_pose_role"] == PRIOR_POSE_ROLE
    assert formal["post_update_pose_role"] == POST_UPDATE_POSE_ROLE
    assert metadata["prior_pose_used_for_weak_axis"] is False
    assert metadata["post_update_pose_used_for_weak_axis"] is False
    assert schur["prior_pose_used_for_weak_axis"] is False
    assert schur["post_update_pose_used_for_weak_axis"] is False


def test_contract_applies_forward_extrinsic_upstream_and_only_kabsch_rotation_offline():
    rows = {row["stage"]: row for row in coordinate_frame_contract_rows()}
    formal = rows["formal_in_call_linearization"]
    schur = rows["translation_Schur"]
    offline = rows["offline_position_alignment"]

    assert formal["lidar_to_imu_extrinsic_role"] == LIDAR_TO_IMU_ROLE
    assert formal["forward_lidar_to_imu_applied_upstream"] is True
    assert schur["reapply_lidar_to_imu_to_weak_axis"] is False
    assert offline["reapply_lidar_to_imu_to_weak_axis"] is False
    assert offline["offline_direction_transform"] == OFFLINE_DIRECTION_TRANSFORM


def test_fixed_seed_random_so3_schur_and_weak_axis_covariance_passes():
    validations = rotation_covariance_validation(random_seed=20260726, random_count=100)
    assert {row["validation"] for row in validations} == {
        "random_so3_translation_schur_covariance",
        "random_so3_minimum_eigenvector_covariance_up_to_sign",
        "random_so3_sign_invariant_angle_invariance_degrees",
    }
    assert all(row["trial_count"] == 100 for row in validations)
    assert all(row["pass"] is True for row in validations)
