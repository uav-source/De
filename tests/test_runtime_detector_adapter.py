import copy

from fastlio2_adapter.detector_adapter import evaluate_readonly_observation
from fastlio2_adapter.detector_output_schema import canonical_sha256
from fastlio2_adapter.runtime_detector_adapter import (
    DETECTOR_EXECUTION_MODE,
    evaluate_runtime_observation,
    validate_runtime_detector_output,
)

from test_readonly_runtime_observation_schema import runtime_record


def test_runtime_output_is_real_post_replay_v2():
    output = evaluate_runtime_observation(runtime_record())
    validate_runtime_detector_output(output)
    assert output["schema_version"] == "readonly_detector_output_v2"
    assert output["record_source"] == "FASTLIO2_RUNTIME"
    assert output["synthetic_only"] is False
    assert output["detector_execution_mode"] == DETECTOR_EXECUTION_MODE


def test_runtime_and_synthetic_calls_share_exact_production_numbers():
    runtime = runtime_record()
    synthetic = copy.deepcopy(runtime)
    for field in (
        "record_source",
        "run_id",
        "sequence_id",
        "fastlio2_commit",
        "fastlio2_binary_sha256",
        "bag_sha256",
        "config_bundle_sha256",
        "adapter_contract_version",
    ):
        synthetic.pop(field)
    synthetic.update(
        schema_version="fastlio2-readonly-observation-v1",
        record_version="readonly_observation_v1",
        synthetic_only=True,
    )
    runtime_output = evaluate_runtime_observation(runtime)
    synthetic_output = evaluate_readonly_observation(synthetic)
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


def test_runtime_adapter_is_immutable_and_deterministic():
    record = runtime_record()
    before = copy.deepcopy(record)
    outputs = [evaluate_runtime_observation(record) for _ in range(3)]
    assert record == before
    assert len({canonical_sha256(output) for output in outputs}) == 1
    assert outputs[0] == outputs[1] == outputs[2]
