import copy
import importlib.util
import json
from pathlib import Path

import jsonschema
import numpy as np
import pytest

from fastlio2_adapter.readonly_observation_schema import (
    validate_first_valid_observation_record,
)
from fastlio2_adapter.runtime_observation_v3 import (
    covariance_raw_checksum,
    validate_runtime_observation_v3,
)


ROOT = Path(__file__).resolve().parents[1]


def synthetic_record():
    spec = importlib.util.spec_from_file_location(
        "day4_fixture_v3",
        ROOT / "scripts/42_run_harmful_bias_day4_synthetic_adapter.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return copy.deepcopy(module.build_synthetic_observations()["well_conditioned"])


def v3_record():
    synthetic = synthetic_record()
    raw = copy.deepcopy(synthetic["prior_covariance_detector_order"])
    raw[0][1] += 5e-11
    symmetric = (
        0.5 * (np.asarray(raw, dtype=float) + np.asarray(raw, dtype=float).T)
    ).tolist()
    return {
        "schema_version": "readonly_observation_v3",
        "record_version": "readonly_observation_v3",
        "record_source": "FASTLIO2_RUNTIME_COMPACT_BINARY",
        "synthetic_only": False,
        "run_id": "multihyp_day5_remediation_export_v1",
        "sequence_id": "avia_quick_shack",
        "fastlio2_commit": "a" * 40,
        "fastlio2_binary_sha256": "b" * 64,
        "bag_sha256": "c" * 64,
        "config_bundle_sha256": "d" * 64,
        "adapter_contract_version": "fastlio2-readonly-observation-v3",
        "scan_index": synthetic["scan_index"],
        "timestamp_begin": synthetic["timestamp_begin"],
        "timestamp_end": synthetic["timestamp_end"],
        "timestamp_unit": "seconds",
        "measurement_call_index": synthetic["measurement_call_index"],
        "prior_position_world": synthetic["prior_position_world"],
        "prior_orientation_world_from_imu_xyzw": synthetic[
            "prior_orientation_world_from_imu_xyzw"
        ],
        "prior_covariance_detector_order_raw": raw,
        "prior_covariance_detector_order_symmetric": symmetric,
        "prior_covariance_max_asymmetry": float(
            np.max(np.abs(np.asarray(raw) - np.asarray(raw).T))
        ),
        "prior_covariance_raw_checksum": covariance_raw_checksum(raw),
        "detector_pose_jacobian_rows": synthetic[
            "detector_pose_jacobian_rows"
        ],
        "formal_filter_innovation_h": synthetic[
            "formal_filter_innovation_h"
        ],
        "signed_geometric_residual_pd2_derived": True,
        "measurement_variance_scalar_m2": synthetic[
            "measurement_variance_scalar_m2"
        ],
        "measurement_weight_representation": "CONSTANT_SCALAR_VARIANCE",
        "measurement_variance_applies_to_all_rows": True,
        "valid_correspondence_count": synthetic["valid_correspondence_count"],
        "native_jacobian_column_count": 12,
        "detector_jacobian_column_count": 6,
        "checksum_algorithm": "FNV1A64_EXACT_BYTES_V1",
        "formal_native_jacobian_checksum": 1,
        "detector_jacobian_checksum": 2,
        "formal_innovation_checksum": 3,
        "geometric_residual_checksum": 4,
        "accepted_index_checksum": 5,
        "formal_correspondence_checksum": 6,
        "binary_record_checksum": 7,
    }


def test_v3_accepts_finite_small_raw_covariance_asymmetry():
    record = v3_record()
    validate_runtime_observation_v3(record)
    assert record["prior_covariance_max_asymmetry"] > 1e-12
    schema = json.loads(
        (ROOT / "schemas/harmful_bias/readonly_observation_v3.schema.json").read_text()
    )
    jsonschema.Draft202012Validator(schema).validate(record)


def test_v3_raw_and_symmetric_relationship_is_exact_and_immutable():
    record = v3_record()
    before = copy.deepcopy(record)
    validate_runtime_observation_v3(record)
    assert record == before
    record["prior_covariance_detector_order_symmetric"][0][1] += 1e-15
    with pytest.raises(ValueError, match="raw/symmetric"):
        validate_runtime_observation_v3(record)


def test_v3_rejects_nonfinite_and_raw_checksum_error():
    record = v3_record()
    record["prior_covariance_detector_order_raw"][0][0] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        validate_runtime_observation_v3(record)
    record = v3_record()
    record["prior_covariance_raw_checksum"] += 1
    with pytest.raises(ValueError, match="checksum"):
        validate_runtime_observation_v3(record)


@pytest.mark.parametrize("field", ["pose_gt", "future_frame", "holdout_label"])
def test_v3_rejects_ground_truth_future_and_holdout(field):
    record = v3_record()
    record[field] = 1
    with pytest.raises(ValueError, match="forbidden"):
        validate_runtime_observation_v3(record)


def test_v1_and_v3_cannot_be_confused():
    record = v3_record()
    with pytest.raises(ValueError):
        validate_first_valid_observation_record(record)
    with pytest.raises(ValueError):
        validate_runtime_observation_v3(synthetic_record())
