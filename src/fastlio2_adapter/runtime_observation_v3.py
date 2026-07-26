"""Fail-closed validation for compact FAST-LIO2 runtime observations v3."""

from __future__ import annotations

import math
import re
import struct
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np


SCHEMA_VERSION = "readonly_observation_v3"
RECORD_VERSION = "readonly_observation_v3"
RECORD_SOURCE = "FASTLIO2_RUNTIME_COMPACT_BINARY"
ADAPTER_CONTRACT_VERSION = "fastlio2-readonly-observation-v3"
CHECKSUM_ALGORITHM = "FNV1A64_EXACT_BYTES_V1"
FNV_OFFSET = 14695981039346656037
FNV_PRIME = 1099511628211

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_FORBIDDEN_TOKENS = (
    "pose_gt",
    "axis_gt",
    "oracle_axis",
    "scene_label",
    "harmful_label",
    "ground_truth",
    "future_frame",
    "holdout_label",
    "candidate_offsets",
    "candidate_costs",
    "imu_conflict",
    "final_harmful_score",
    "harmful_trigger",
)
_REQUIRED = frozenset(
    {
        "schema_version",
        "record_version",
        "record_source",
        "synthetic_only",
        "run_id",
        "sequence_id",
        "fastlio2_commit",
        "fastlio2_binary_sha256",
        "bag_sha256",
        "config_bundle_sha256",
        "adapter_contract_version",
        "scan_index",
        "timestamp_begin",
        "timestamp_end",
        "timestamp_unit",
        "measurement_call_index",
        "prior_position_world",
        "prior_orientation_world_from_imu_xyzw",
        "prior_covariance_detector_order_raw",
        "prior_covariance_detector_order_symmetric",
        "prior_covariance_max_asymmetry",
        "prior_covariance_raw_checksum",
        "detector_pose_jacobian_rows",
        "formal_filter_innovation_h",
        "signed_geometric_residual_pd2_derived",
        "measurement_variance_scalar_m2",
        "measurement_weight_representation",
        "measurement_variance_applies_to_all_rows",
        "valid_correspondence_count",
        "native_jacobian_column_count",
        "detector_jacobian_column_count",
        "checksum_algorithm",
        "formal_native_jacobian_checksum",
        "detector_jacobian_checksum",
        "formal_innovation_checksum",
        "geometric_residual_checksum",
        "accepted_index_checksum",
        "formal_correspondence_checksum",
        "binary_record_checksum",
    }
)


def validate_runtime_observation_v3(record: Mapping[str, Any]) -> None:
    if not isinstance(record, Mapping):
        raise ValueError("runtime observation v3 must be a mapping")
    _reject_forbidden_fields(record)
    missing = sorted(_REQUIRED - set(record))
    if missing:
        raise ValueError(f"runtime observation v3 missing fields: {missing}")
    if record["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unexpected v3 schema_version")
    if record["record_version"] != RECORD_VERSION:
        raise ValueError("unexpected v3 record_version")
    if record["record_source"] != RECORD_SOURCE:
        raise ValueError("unexpected v3 record_source")
    if record["synthetic_only"] is not False:
        raise ValueError("runtime v3 synthetic_only must be false")
    if record["adapter_contract_version"] != ADAPTER_CONTRACT_VERSION:
        raise ValueError("unexpected v3 adapter contract")
    if record["timestamp_unit"] != "seconds":
        raise ValueError("timestamp_unit must be seconds")
    if record["checksum_algorithm"] != CHECKSUM_ALGORITHM:
        raise ValueError("unexpected checksum algorithm")
    for name in ("run_id", "sequence_id"):
        if not isinstance(record[name], str) or _IDENTIFIER_RE.fullmatch(
            record[name]
        ) is None:
            raise ValueError(f"{name} must be a safe identifier")
    if _COMMIT_RE.fullmatch(str(record["fastlio2_commit"])) is None:
        raise ValueError("fastlio2_commit must be lowercase 40-hex")
    for name in (
        "fastlio2_binary_sha256",
        "bag_sha256",
        "config_bundle_sha256",
    ):
        if _SHA256_RE.fullmatch(str(record[name])) is None:
            raise ValueError(f"{name} must be lowercase SHA-256")
    for name in ("scan_index", "measurement_call_index"):
        _uint(record[name], name)
    for name in ("timestamp_begin", "timestamp_end"):
        _finite(record[name], name)
    if float(record["timestamp_end"]) < float(record["timestamp_begin"]):
        raise ValueError("timestamp_end precedes timestamp_begin")
    _vector(record["prior_position_world"], 3, "prior_position_world")
    orientation = _vector(
        record["prior_orientation_world_from_imu_xyzw"],
        4,
        "prior_orientation_world_from_imu_xyzw",
    )
    if abs(float(np.linalg.norm(orientation)) - 1.0) > 1.0e-6:
        raise ValueError("prior quaternion is not unit length")

    raw = _matrix(
        record["prior_covariance_detector_order_raw"],
        6,
        6,
        "prior_covariance_detector_order_raw",
    )
    symmetric = _matrix(
        record["prior_covariance_detector_order_symmetric"],
        6,
        6,
        "prior_covariance_detector_order_symmetric",
    )
    expected_symmetric = 0.5 * (raw + raw.T)
    if not np.array_equal(symmetric, expected_symmetric):
        raise ValueError("raw/symmetric covariance relationship is inconsistent")
    expected_asymmetry = float(np.max(np.abs(raw - raw.T)))
    actual_asymmetry = _finite(
        record["prior_covariance_max_asymmetry"],
        "prior_covariance_max_asymmetry",
    )
    if actual_asymmetry != expected_asymmetry:
        raise ValueError("prior covariance asymmetry summary mismatch")
    expected_raw_checksum = covariance_raw_checksum(raw)
    if _uint(
        record["prior_covariance_raw_checksum"],
        "prior_covariance_raw_checksum",
    ) != expected_raw_checksum:
        raise ValueError("prior covariance raw checksum mismatch")

    jacobian = np.asarray(record["detector_pose_jacobian_rows"], dtype=float)
    if jacobian.ndim != 2 or jacobian.shape[1] != 6 or jacobian.shape[0] < 1:
        raise ValueError("detector Jacobian must have shape N x 6")
    if not np.all(np.isfinite(jacobian)):
        raise ValueError("detector Jacobian contains nonfinite values")
    innovation = np.asarray(record["formal_filter_innovation_h"], dtype=float)
    if innovation.shape != (jacobian.shape[0],) or not np.all(
        np.isfinite(innovation)
    ):
        raise ValueError("formal innovation must be a finite N-vector")
    if record["signed_geometric_residual_pd2_derived"] is not True:
        raise ValueError("signed geometric residual must be marked derived")
    if record["measurement_weight_representation"] != "CONSTANT_SCALAR_VARIANCE":
        raise ValueError("unexpected measurement weight representation")
    if record["measurement_variance_applies_to_all_rows"] is not True:
        raise ValueError("measurement variance must apply to all rows")
    if _finite(
        record["measurement_variance_scalar_m2"],
        "measurement_variance_scalar_m2",
    ) <= 0.0:
        raise ValueError("measurement variance must be positive")
    if _uint(
        record["valid_correspondence_count"],
        "valid_correspondence_count",
    ) != jacobian.shape[0]:
        raise ValueError("valid correspondence count does not match rows")
    if record["native_jacobian_column_count"] != 12:
        raise ValueError("native Jacobian column count must be 12")
    if record["detector_jacobian_column_count"] != 6:
        raise ValueError("detector Jacobian column count must be 6")
    for name in (
        "formal_native_jacobian_checksum",
        "detector_jacobian_checksum",
        "formal_innovation_checksum",
        "geometric_residual_checksum",
        "accepted_index_checksum",
        "formal_correspondence_checksum",
        "binary_record_checksum",
    ):
        _uint(record[name], name)


def covariance_raw_checksum(raw: Sequence[Sequence[float]] | np.ndarray) -> int:
    matrix = np.asarray(raw, dtype=np.float64)
    if matrix.shape != (6, 6) or not np.all(np.isfinite(matrix)):
        raise ValueError("raw covariance must be finite 6x6")
    value = FNV_OFFSET
    for number in matrix.ravel(order="C"):
        for byte in struct.pack("<d", float(number)):
            value ^= byte
            value = (value * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return value


def _uint(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**64:
        raise ValueError(f"{name} must be uint64")
    return value


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _vector(value: Any, size: int, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.shape != (size,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite vector of length {size}")
    return array


def _matrix(value: Any, rows: int, columns: int, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.shape != (rows, columns) or not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must be a finite {rows}x{columns} matrix")
    return array


def _reject_forbidden_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for raw_name, child in value.items():
            if not isinstance(raw_name, str):
                raise ValueError(f"{path} contains a non-string field name")
            lowered = raw_name.lower()
            if any(token in lowered for token in _FORBIDDEN_TOKENS):
                raise ValueError(f"record contains forbidden field: {raw_name}")
            _reject_forbidden_fields(child, f"{path}.{raw_name}")
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, child in enumerate(value):
            _reject_forbidden_fields(child, f"{path}[{index}]")
