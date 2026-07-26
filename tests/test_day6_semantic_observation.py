from copy import deepcopy

import pytest

import fastlio2_adapter.day6_semantic_observation as semantic
from fastlio2_adapter.day6_semantic_observation import (
    Day6SemanticError,
    load_observation_records,
    semantic_observation_checksum,
)


def record():
    return {
        "scan_index": 3,
        "timestamp_begin": 1.0,
        "timestamp_end": 2.0,
        "measurement_call_index": 0,
        "prior_position_world": [0.0, 0.0, 0.0],
        "prior_orientation_world_from_imu_xyzw": [0.0, 0.0, 0.0, 1.0],
        "prior_covariance_detector_order_raw": [[1.0]],
        "prior_covariance_detector_order_symmetric": [[1.0]],
        "measurement_variance_scalar_m2": 0.04,
        "measurement_weight_representation": "CONSTANT_SCALAR_VARIANCE",
        "valid_correspondence_count": 1,
        "detector_pose_jacobian_rows": [[1.0, 0.0, 0.0, 0.0, 0.0, 0.0]],
        "formal_filter_innovation_h": [0.25],
        "formal_native_jacobian_checksum": 1,
        "detector_jacobian_checksum": 2,
        "formal_innovation_checksum": 3,
        "geometric_residual_checksum": 4,
        "accepted_index_checksum": 5,
        "formal_correspondence_checksum": 6,
        "run_id": "run_1",
        "binary_record_checksum": "left",
        "binary_record_self_checksum": "self-left",
    }


def test_semantic_checksum_excludes_run_and_record_identity_fields():
    left = record()
    right = deepcopy(left)
    right["run_id"] = "run_2"
    right["binary_record_checksum"] = "right"
    right["binary_record_self_checksum"] = "self-right"
    assert semantic_observation_checksum(left, 0) == semantic_observation_checksum(
        right, 0
    )


def test_formal_numeric_change_is_detected():
    left = record()
    right = deepcopy(left)
    right["formal_filter_innovation_h"] = [0.5]
    assert semantic_observation_checksum(left, 0) != semantic_observation_checksum(
        right, 0
    )


def test_binary_record_count_must_be_487(monkeypatch, tmp_path):
    monkeypatch.setattr(
        semantic,
        "indexed_frames",
        lambda path: ([], {"record_checksum_failure_count": 0}),
    )
    monkeypatch.setattr(semantic, "load_existing_converter", lambda: object())
    with pytest.raises(Day6SemanticError, match="expected 487"):
        load_observation_records(tmp_path / "short.bin")
