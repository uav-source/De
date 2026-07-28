import numpy as np

from zero_perturbation.pcl_backend import validate_result_payload


def test_pcl_result_must_echo_the_shared_open3d_pcl_input_checksums():
    checksums = {
        "source_checksum": "same-source",
        "target_checksum": "same-target",
        "reference_pose_checksum": "same-pose",
        "snapshot_checksum": "same-snapshot",
    }
    payload = {
        "trial_id": "pairing",
        "backend_name": "pcl_point_to_plane",
        "pcl_version": "1.15.1",
        "has_converged": True,
        "fitness_score": 0.0,
        "final_transformation_4x4": np.eye(4).reshape(-1).tolist(),
        "translation_update_norm_m": 0.0,
        "rotation_update_norm_rad": 0.0,
        "source_point_count": 64,
        "target_point_count": 64,
        "finite_output": True,
        "runtime_ms": 1.0,
        "failure_reason": "",
        **checksums,
    }
    payload["source_checksum"] = "wrong"
    try:
        validate_result_payload(
            payload,
            trial_id="pairing",
            source_count=64,
            target_count=64,
            checksums=checksums,
            initial_transformation=np.eye(4),
            cli_exit_code=0,
        )
    except ValueError as error:
        assert "checksum echo mismatch" in str(error)
    else:
        raise AssertionError("checksum mismatch was accepted")

