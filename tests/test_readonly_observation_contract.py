import json
from pathlib import Path

from fastlio2_adapter.readonly_observation_schema import (
    ADAPTER_CONTRACT_VERSION,
    CHECKSUM_ALGORITHM,
    DETECTOR_COLUMN_MAP,
    DETECTOR_COVARIANCE_ORDER,
    DETECTOR_JACOBIAN_COLUMNS,
    NATIVE_COVARIANCE_DIMENSION,
    NATIVE_JACOBIAN_COLUMNS,
    SCHEMA_VERSION,
    SKIP_REASONS,
    validate_first_valid_observation_record,
    validate_scan_lifecycle_record,
)


ROOT = Path(__file__).resolve().parents[1]
DAY3 = ROOT / "artifacts/current/harmful_bias_multihyp_dev/day3"
SCHEMA_PATH = (
    ROOT / "schemas/harmful_bias/readonly_observation_v1.schema.json"
)
MODULE_PATH = (
    ROOT / "src/fastlio2_adapter/readonly_observation_schema.py"
)
CONTRACT_PATH = ROOT / "docs/harmful_bias/day3_readonly_tap_contract.md"


def load_json(path):
    return json.loads(path.read_text())


def test_contract_constants_match_frozen_fastlio2_interface():
    assert SCHEMA_VERSION == ADAPTER_CONTRACT_VERSION
    assert NATIVE_COVARIANCE_DIMENSION == 23
    assert NATIVE_JACOBIAN_COLUMNS == 12
    assert DETECTOR_JACOBIAN_COLUMNS == 6
    assert DETECTOR_COLUMN_MAP == (3, 4, 5, 0, 1, 2)
    assert DETECTOR_COVARIANCE_ORDER == (
        "delta_theta_xyz_then_delta_position_xyz"
    )
    assert CHECKSUM_ALGORITHM == "FNV1A64_EXACT_BYTES_V1"


def test_skip_reason_contract_is_closed_and_complete():
    assert SKIP_REASONS == (
        "NONE",
        "FIRST_SCAN_INITIALIZATION",
        "EMPTY_UNDISTORTED_SCAN",
        "LOCAL_MAP_INITIALIZATION",
        "DOWNSAMPLED_POINTS_TOO_FEW",
        "FILTER_UPDATE_NOT_INVOKED",
        "NO_VALID_LINEARIZATION",
        "EXTRINSIC_ESTIMATION_ENABLED",
        "NONFINITE_OBSERVATION",
        "BUFFER_FULL",
        "INTERNAL_LIFECYCLE_ERROR",
    )


def test_schema_contains_no_prohibited_scientific_fields():
    schema_text = SCHEMA_PATH.read_text().lower()
    prohibited = (
        "pose_gt",
        "axis_gt",
        "oracle_axis",
        "scene_label",
        "harmful_label",
        "future_frame",
        "holdout_label",
        "ground_truth",
        "final_score",
        "trigger",
    )
    assert all(token not in schema_text for token in prohibited)


def test_validator_module_does_not_call_detector_logic():
    module_text = MODULE_PATH.read_text()
    prohibited_calls = (
        "compute_metrics_for_frame(",
        "compute_odi(",
        "compute_weak_direction(",
    )
    assert all(call not in module_text for call in prohibited_calls)


def test_schema_defines_both_record_types_and_exact_artifact_fields():
    schema = load_json(SCHEMA_PATH)
    lifecycle_schema = schema["$defs"]["scanLifecycleRecord"]
    observation_schema = schema["$defs"]["firstValidObservationRecord"]
    lifecycle = load_json(DAY3 / "synthetic_scan_lifecycle.json")
    observation = load_json(
        DAY3 / "synthetic_first_valid_observation.json"
    )
    assert set(lifecycle_schema["required"]) == set(lifecycle)
    assert set(observation_schema["required"]) == set(observation)
    assert lifecycle_schema["additionalProperties"] is False
    assert observation_schema["additionalProperties"] is False


def test_synthetic_artifacts_are_explicitly_non_operational():
    lifecycle = load_json(DAY3 / "synthetic_scan_lifecycle.json")
    observation = load_json(
        DAY3 / "synthetic_first_valid_observation.json"
    )
    summary = load_json(DAY3 / "synthetic_validation_summary.json")
    assert lifecycle["synthetic_only"] is True
    assert observation["synthetic_only"] is True
    assert summary["synthetic_only"] is True
    assert summary["real_data_used"] is False
    assert summary["rosbag_used"] is False
    assert summary["scientific_experiment"] is False
    validate_scan_lifecycle_record(lifecycle)
    validate_first_valid_observation_record(observation)


def test_observation_dimensions_and_units_are_explicit():
    record = load_json(DAY3 / "synthetic_first_valid_observation.json")
    row_count = record["valid_correspondence_count"]
    assert row_count == 3
    assert len(record["detector_pose_jacobian_rows"]) == row_count
    assert all(len(row) == 6 for row in record["detector_pose_jacobian_rows"])
    assert record["prior_position_frame"] == "world"
    assert record["prior_position_unit"] == "meters"
    assert record["prior_orientation_from_frame"] == "imu"
    assert record["prior_orientation_to_frame"] == "world"
    assert record["residual_unit"] == "meters"
    assert record["neighbor_coordinate_frame"] == "world"
    assert record["neighbor_coordinate_unit"] == "meters"


def test_observation_uses_one_positive_variance_for_all_rows():
    record = load_json(DAY3 / "synthetic_first_valid_observation.json")
    assert (
        record["measurement_weight_representation"]
        == "CONSTANT_SCALAR_VARIANCE"
    )
    assert record["measurement_variance_scalar_m2"] == 0.001
    assert record["measurement_variance_applies_to_all_rows"] is True
    assert not any("variance" in name for name in record if name.startswith("point_"))


def test_residual_sign_contract_is_machine_precision_exact():
    record = load_json(DAY3 / "synthetic_first_valid_observation.json")
    assert max(
        abs(formal + geometric)
        for formal, geometric in zip(
            record["formal_filter_innovation_h"],
            record["signed_geometric_residual_pd2"],
        )
    ) <= 1.0e-12


def test_correspondence_payload_has_native_neighbors_and_proxy_ids():
    record = load_json(DAY3 / "synthetic_first_valid_observation.json")
    row_count = record["valid_correspondence_count"]
    assert len(record["accepted_source_indices"]) == row_count
    assert len(record["correspondence_proxy_ids"]) == row_count
    assert len(record["plane_parameters_world"]) == row_count
    assert len(record["ordered_neighbor_coordinates_world"]) == row_count
    assert all(
        len(neighbors) == 5
        for neighbors in record["ordered_neighbor_coordinates_world"]
    )
    assert all(index >= 0 for index in record["accepted_source_indices"])
    assert all(proxy >= 0 for proxy in record["correspondence_proxy_ids"])


def test_checksum_fields_are_explicit_uint64_values():
    record = load_json(DAY3 / "synthetic_first_valid_observation.json")
    checksum_fields = [
        name for name in record if name.endswith("_checksum")
    ]
    assert len(checksum_fields) == 7
    assert record["checksum_algorithm"] == CHECKSUM_ALGORITHM
    assert all(
        isinstance(record[name], int)
        and not isinstance(record[name], bool)
        and 0 <= record[name] < (1 << 64)
        for name in checksum_fields
    )


def test_formal_variance_is_documented_as_callsite_owned():
    contract = CONTRACT_PATH.read_text()
    schema = SCHEMA_PATH.read_text()
    assert "copied from the formal FAST-LIO2 update call site" in contract
    assert "The tap defines no formal variance symbol or constant" in contract
    assert "formalLaserPointVariance" not in schema


def test_contract_stops_payload_copy_after_first_valid_capture():
    contract = CONTRACT_PATH.read_text()
    assert "capturePending()" in contract
    assert "perform no observation-payload copy" in contract
    assert "later iterations retain only lightweight call counts" in contract


def test_contract_rejects_invalid_prior_before_activation():
    contract = CONTRACT_PATH.read_text()
    assert "before activating the scan" in contract
    assert "INTERNAL_LIFECYCLE_ERROR" in contract
    assert "cannot produce an observation" in contract


def test_contract_canonicalizes_plane_sign_for_proxy_only():
    contract = CONTRACT_PATH.read_text()
    assert "sign-canonicalized" in contract
    assert "[n,d]` and `[-n,-d]" in contract
    assert "never modifies the formal plane or residual" in contract
