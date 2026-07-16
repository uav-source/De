import copy
import json
import math
from pathlib import Path

import jsonschema
import pytest

from fastlio2_adapter.readonly_observation_schema import (
    CHECKSUM_ALGORITHM,
    SCHEMA_VERSION,
    validate_first_valid_observation_record,
    validate_scan_lifecycle_record,
)


ROOT = Path(__file__).resolve().parents[1]
DAY3 = ROOT / "artifacts/current/harmful_bias_multihyp_dev/day3"
SCHEMA_PATH = (
    ROOT / "schemas/harmful_bias/readonly_observation_v1.schema.json"
)


def load_lifecycle():
    return json.loads((DAY3 / "synthetic_scan_lifecycle.json").read_text())


def load_observation():
    return json.loads(
        (DAY3 / "synthetic_first_valid_observation.json").read_text()
    )


def test_json_schema_is_well_formed_and_accepts_synthetic_records():
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(load_lifecycle())
    validator.validate(load_observation())


def test_valid_synthetic_records_pass_python_validators():
    validate_scan_lifecycle_record(load_lifecycle())
    validate_first_valid_observation_record(load_observation())


@pytest.mark.parametrize(
    ("factory", "validator", "field"),
    [
        (
            load_lifecycle,
            validate_scan_lifecycle_record,
            "measurement_call_count",
        ),
        (
            load_observation,
            validate_first_valid_observation_record,
            "detector_pose_jacobian_rows",
        ),
    ],
)
def test_missing_required_field_fails(factory, validator, field):
    record = factory()
    del record[field]
    with pytest.raises(ValueError, match="missing"):
        validator(record)


def test_correspondence_array_length_mismatch_fails():
    record = load_observation()
    record["accepted_source_indices"].pop()
    with pytest.raises(ValueError, match="length"):
        validate_first_valid_observation_record(record)


def test_jacobian_must_be_n_by_six():
    record = load_observation()
    record["detector_pose_jacobian_rows"][0].pop()
    with pytest.raises(ValueError, match="6 columns"):
        validate_first_valid_observation_record(record)


def test_covariance_must_be_six_by_six():
    record = load_observation()
    record["prior_covariance_detector_order"].pop()
    with pytest.raises(ValueError, match="6 rows"):
        validate_first_valid_observation_record(record)


def test_covariance_must_be_symmetric():
    record = load_observation()
    record["prior_covariance_detector_order"][0][1] += 0.1
    with pytest.raises(ValueError, match="symmetric"):
        validate_first_valid_observation_record(record)


def test_quaternion_must_have_unit_norm():
    record = load_observation()
    record["prior_orientation_world_from_imu_xyzw"] = [0.0, 0.0, 0.0, 2.0]
    with pytest.raises(ValueError, match="unit norm"):
        validate_first_valid_observation_record(record)


def test_formal_innovation_must_be_negative_pd2():
    record = load_observation()
    record["formal_filter_innovation_h"][1] += 0.01
    with pytest.raises(ValueError, match="disagree"):
        validate_first_valid_observation_record(record)


@pytest.mark.parametrize("variance", [0.0, -0.001])
def test_variance_must_be_positive(variance):
    record = load_observation()
    record["measurement_variance_scalar_m2"] = variance
    with pytest.raises(ValueError, match="positive"):
        validate_first_valid_observation_record(record)


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_nonfinite_observation_value_fails(value):
    record = load_observation()
    record["detector_pose_jacobian_rows"][0][0] = value
    with pytest.raises(ValueError, match="finite"):
        validate_first_valid_observation_record(record)


def test_forbidden_gt_field_fails():
    record = load_observation()
    record["pose_gt"] = [0.0, 0.0, 0.0]
    with pytest.raises(ValueError, match="forbidden field"):
        validate_first_valid_observation_record(record)


@pytest.mark.parametrize("field", ["future_frame", "holdout_label"])
def test_forbidden_deferred_evaluation_field_fails(field):
    record = load_observation()
    record[field] = "not-allowed"
    with pytest.raises(ValueError, match="forbidden field"):
        validate_first_valid_observation_record(record)


def test_forbidden_nested_field_fails():
    record = load_observation()
    record["ordered_neighbor_coordinates_world"][0][0] = {
        "axis_gt": [1.0, 0.0, 0.0]
    }
    with pytest.raises(ValueError, match="forbidden field"):
        validate_first_valid_observation_record(record)


def test_skip_reason_must_use_closed_enum():
    record = load_lifecycle()
    record["skip_reason"] = "CUSTOM_REASON"
    with pytest.raises(ValueError, match="unsupported skip_reason"):
        validate_scan_lifecycle_record(record)


@pytest.mark.parametrize(
    ("factory", "validator"),
    [
        (load_lifecycle, validate_scan_lifecycle_record),
        (load_observation, validate_first_valid_observation_record),
    ],
)
def test_schema_version_mismatch_fails(factory, validator):
    record = factory()
    record["schema_version"] = "wrong-version"
    with pytest.raises(ValueError, match="schema_version"):
        validator(record)


def test_checksum_algorithm_must_be_declared_exactly():
    record = load_observation()
    record["checksum_algorithm"] = "unspecified"
    with pytest.raises(ValueError, match="checksum_algorithm"):
        validate_first_valid_observation_record(record)
    assert CHECKSUM_ALGORITHM == "FNV1A64_EXACT_BYTES_V1"
    assert SCHEMA_VERSION == "fastlio2-readonly-observation-v1"


def test_first_valid_call_index_must_be_nonnegative_integer():
    record = load_observation()
    record["measurement_call_index"] = -1
    with pytest.raises(ValueError, match="unsigned"):
        validate_first_valid_observation_record(record)


def test_lifecycle_call_counts_must_be_consistent():
    record = load_lifecycle()
    record["valid_measurement_call_count"] = (
        record["measurement_call_count"] + 1
    )
    with pytest.raises(ValueError, match="exceeds"):
        validate_scan_lifecycle_record(record)


def test_input_records_are_not_mutated_by_validation():
    lifecycle = load_lifecycle()
    observation = load_observation()
    lifecycle_before = copy.deepcopy(lifecycle)
    observation_before = copy.deepcopy(observation)
    validate_scan_lifecycle_record(lifecycle)
    validate_first_valid_observation_record(observation)
    assert lifecycle == lifecycle_before
    assert observation == observation_before
