import numpy as np

from zero_perturbation.pcl_backend import REQUIRED_RESULT_FIELDS, validate_result_payload


def test_pcl_json_result_schema_and_independent_metric_recomputation():
    checksums = {
        "source_checksum": "source",
        "target_checksum": "target",
        "reference_pose_checksum": "pose",
        "snapshot_checksum": "snapshot",
    }
    payload = {
        "trial_id": "schema-test",
        "backend_name": "pcl_point_to_plane",
        "pcl_version": "1.15.1",
        "has_converged_raw": True,
        "has_converged": True,
        "final_transform_finite": True,
        "fitness_finite": True,
        "fitness_score": 0.0,
        "final_transformation_4x4": np.eye(4).reshape(-1).tolist(),
        "translation_update_norm_m": 0.0,
        "rotation_update_norm_rad": 0.0,
        "source_point_count": 64,
        "target_point_count": 64,
        "finite_output": True,
        "qualification_pass": True,
        "iteration_count": 1,
        "correspondence_count": 64,
        "source_normal_finite_count": 64,
        "source_normal_zero_count": 0,
        "source_normal_nan_count": 0,
        "source_normal_norm_min": 1.0,
        "source_normal_norm_median": 1.0,
        "source_normal_norm_max": 1.0,
        "target_normal_finite_count": 64,
        "target_normal_zero_count": 0,
        "target_normal_nan_count": 0,
        "target_normal_norm_min": 1.0,
        "target_normal_norm_median": 1.0,
        "target_normal_norm_max": 1.0,
        "runtime_ms": 1.0,
        "failure_reason": "",
        **checksums,
    }
    assert REQUIRED_RESULT_FIELDS <= payload.keys()
    result = validate_result_payload(
        payload,
        trial_id="schema-test",
        source_count=64,
        target_count=64,
        checksums=checksums,
        initial_transformation=np.eye(4),
        cli_exit_code=0,
    )
    assert result.solver_failed is False
