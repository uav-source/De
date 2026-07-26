import copy

from fastlio2_adapter.offline_detector_determinism import (
    evaluate_frozen_observation,
    input_component_identity,
)
from test_runtime_observation_v3 import v3_record


def test_full_input_and_required_components_are_immutable():
    record = v3_record()
    snapshot = copy.deepcopy(record)
    before = input_component_identity(record)
    evaluate_frozen_observation(record, record_index=0)
    after = input_component_identity(record)
    assert record == snapshot
    assert before == after


def test_input_component_identity_detects_jacobian_mutation():
    record = v3_record()
    before = input_component_identity(record)
    record["detector_pose_jacobian_rows"][0][0] += 1.0
    after = input_component_identity(record)
    assert before["input_observation_checksum"] != after[
        "input_observation_checksum"
    ]
    assert before["detector_pose_jacobian_rows_checksum"] != after[
        "detector_pose_jacobian_rows_checksum"
    ]


def test_input_component_identity_detects_prior_covariance_mutation():
    record = v3_record()
    before = input_component_identity(record)
    record["prior_covariance_detector_order_raw"][0][0] += 1.0
    after = input_component_identity(record)
    assert before["prior_covariance_checksum"] != after[
        "prior_covariance_checksum"
    ]
