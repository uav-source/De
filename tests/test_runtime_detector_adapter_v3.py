import copy

from fastlio2_adapter.detector_adapter import evaluate_readonly_observation
from fastlio2_adapter.detector_output_schema import canonical_sha256
from fastlio2_adapter.runtime_detector_adapter_v3 import (
    DETECTOR_EXECUTION_MODE,
    evaluate_runtime_observation_v3,
    validate_runtime_detector_output_v3,
)

from test_runtime_observation_v3 import synthetic_record, v3_record


def test_runtime_v3_uses_post_replay_production_detector():
    output = evaluate_runtime_observation_v3(v3_record())
    validate_runtime_detector_output_v3(output)
    assert output["schema_version"] == "readonly_detector_output_v3"
    assert output["record_source"] == "FASTLIO2_RUNTIME_COMPACT_BINARY"
    assert output["synthetic_only"] is False
    assert output["detector_execution_mode"] == DETECTOR_EXECUTION_MODE


def test_runtime_v3_and_synthetic_share_production_numbers():
    runtime_output = evaluate_runtime_observation_v3(v3_record())
    synthetic_output = evaluate_readonly_observation(synthetic_record())
    for field in (
        "odi_trans",
        "ais_trans",
        "lambda_min_trans",
        "condition_number_trans",
        "translation_eigenvalues_ascending",
        "primary_weak_direction",
        "primary_eigengap_ratio",
        "primary_direction_stable",
        "degeneracy_triggered",
        "actionable_direction",
    ):
        assert runtime_output[field] == synthetic_output[field]


def test_detector_invalid_still_emits_one_structured_output():
    record = v3_record()
    record["detector_pose_jacobian_rows"] = record[
        "detector_pose_jacobian_rows"
    ][:3]
    record["formal_filter_innovation_h"] = record[
        "formal_filter_innovation_h"
    ][:3]
    record["valid_correspondence_count"] = 3
    output = evaluate_runtime_observation_v3(record)
    validate_runtime_detector_output_v3(output)
    assert output["valid"] is False
    assert output["invalid_reason"] == "TOO_FEW_CORRESPONDENCES"


def test_runtime_v3_adapter_is_immutable_and_deterministic():
    record = v3_record()
    before = copy.deepcopy(record)
    outputs = [evaluate_runtime_observation_v3(record) for _ in range(3)]
    assert record == before
    assert len({canonical_sha256(output) for output in outputs}) == 1
    assert outputs[0] == outputs[1] == outputs[2]
