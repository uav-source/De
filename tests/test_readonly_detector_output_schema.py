import copy
import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

from fastlio2_adapter.detector_adapter import evaluate_readonly_observation
from fastlio2_adapter.detector_output_schema import (
    detector_output_payload_checksum,
    validate_readonly_detector_output,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas/harmful_bias/readonly_detector_output_v1.schema.json"
RUNNER_PATH = ROOT / "scripts/42_run_harmful_bias_day4_synthetic_adapter.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("day4_synthetic_runner_schema", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def valid_output():
    record = load_runner().build_synthetic_observations()["weak_x"]
    return evaluate_readonly_observation(record)


def reseal(output):
    output["detector_output_checksum"] = detector_output_payload_checksum(output)
    return output


def test_output_json_schema_is_well_formed_and_accepts_valid_output(valid_output):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(valid_output)
    validate_readonly_detector_output(valid_output)


def test_missing_required_field_fails(valid_output):
    output = copy.deepcopy(valid_output)
    del output["odi_trans"]
    with pytest.raises(ValueError, match="missing"):
        validate_readonly_detector_output(output)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("translation_eigenvalues_ascending", [1.0, 2.0], "length 3"),
        ("translation_eigenvalues_ascending", [2.0, 1.0, 3.0], "nondecreasing"),
        ("primary_weak_direction", [1.0, 0.0], "length 3"),
        ("primary_weak_direction", [2.0, 0.0, 0.0], "unit norm"),
    ],
)
def test_vector_shape_order_and_norm_fail(valid_output, field, value, message):
    output = reseal(copy.deepcopy(valid_output))
    output[field] = value
    reseal(output)
    with pytest.raises(ValueError, match=message):
        validate_readonly_detector_output(output)


def test_actionable_requires_stable_direction(valid_output):
    output = copy.deepcopy(valid_output)
    output["actionable_direction"] = True
    output["primary_direction_stable"] = False
    output["degeneracy_triggered"] = True
    reseal(output)
    with pytest.raises(ValueError, match="stable"):
        validate_readonly_detector_output(output)


def test_actionable_requires_degeneracy_trigger(valid_output):
    output = copy.deepcopy(valid_output)
    output["actionable_direction"] = True
    output["primary_direction_stable"] = True
    output["degeneracy_triggered"] = False
    reseal(output)
    with pytest.raises(ValueError, match="trigger"):
        validate_readonly_detector_output(output)


@pytest.mark.parametrize(
    "field", ["pose_gt", "future_frame", "final_harmful_score"]
)
def test_forbidden_scientific_and_deferred_fields_fail(valid_output, field):
    output = copy.deepcopy(valid_output)
    output[field] = 1
    reseal(output)
    with pytest.raises(ValueError, match="forbidden field"):
        validate_readonly_detector_output(output)


def test_bad_checksum_format_fails(valid_output):
    output = copy.deepcopy(valid_output)
    output["input_observation_checksum"] = "not-a-sha"
    with pytest.raises(ValueError, match="SHA-256"):
        validate_readonly_detector_output(output)


def test_synthetic_only_false_fails(valid_output):
    output = copy.deepcopy(valid_output)
    output["synthetic_only"] = False
    reseal(output)
    with pytest.raises(ValueError, match="synthetic_only"):
        validate_readonly_detector_output(output)


def test_invalid_output_uses_explicit_null_policy():
    record = load_runner().build_synthetic_observations()["well_conditioned"]
    row_fields = (
        "detector_pose_jacobian_rows",
        "signed_geometric_residual_pd2",
        "formal_filter_innovation_h",
        "accepted_source_indices",
        "correspondence_proxy_ids",
        "plane_parameters_world",
        "ordered_neighbor_coordinates_world",
    )
    for field in row_fields:
        record[field] = record[field][:5]
    record["valid_correspondence_count"] = 5
    output = evaluate_readonly_observation(record)
    validate_readonly_detector_output(output)
    assert output["valid"] is False
    assert output["invalid_reason"] == "TOO_FEW_CORRESPONDENCES"
    assert output["translation_eigenvalues_ascending"] is None
    assert output["primary_weak_direction"] is None


def test_schema_contains_no_forbidden_output_fields():
    text = SCHEMA_PATH.read_text(encoding="utf-8").lower()
    for token in (
        "pose_gt",
        "axis_gt",
        "oracle_axis",
        "scene_label",
        "harmful_label",
        "future_frame",
        "holdout_label",
        "ground_truth",
        "final_harmful_score",
        "harmful_trigger",
        "candidate_offsets",
        "candidate_costs",
        "imu_conflict",
        "future_gain",
    ):
        assert token not in text
