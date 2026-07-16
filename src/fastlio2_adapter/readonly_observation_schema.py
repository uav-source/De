"""Validation for the FAST-LIO2 read-only observation tap v1 records."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any


SCHEMA_VERSION = "fastlio2-readonly-observation-v1"
ADAPTER_CONTRACT_VERSION = "fastlio2-readonly-observation-v1"
FIRST_VALID_RECORD_VERSION = "readonly_observation_v1"
CHECKSUM_ALGORITHM = "FNV1A64_EXACT_BYTES_V1"

NATIVE_COVARIANCE_DIMENSION = 23
NATIVE_JACOBIAN_COLUMNS = 12
DETECTOR_JACOBIAN_COLUMNS = 6
DETECTOR_COLUMN_MAP = (3, 4, 5, 0, 1, 2)
DETECTOR_COVARIANCE_ORDER = "delta_theta_xyz_then_delta_position_xyz"

SKIP_REASONS = (
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

_FORBIDDEN_FIELD_TOKENS = (
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

_LIFECYCLE_FIELDS = frozenset(
    {
        "record_type",
        "schema_version",
        "synthetic_only",
        "scan_index",
        "timestamp_begin",
        "timestamp_end",
        "timestamp_unit",
        "tap_enabled",
        "update_invoked",
        "first_valid_linearization_found",
        "record_emitted",
        "measurement_call_count",
        "valid_measurement_call_count",
        "downsampled_point_count",
        "valid_correspondence_count",
        "skip_reason",
        "adapter_contract_version",
        "fastlio2_commit",
    }
)

_OBSERVATION_FIELDS = frozenset(
    {
        "record_type",
        "schema_version",
        "synthetic_only",
        "scan_index",
        "timestamp_begin",
        "timestamp_end",
        "timestamp_unit",
        "measurement_call_index",
        "record_version",
        "prior_position_world",
        "prior_position_frame",
        "prior_position_unit",
        "prior_orientation_world_from_imu_xyzw",
        "prior_orientation_from_frame",
        "prior_orientation_to_frame",
        "prior_orientation_representation",
        "prior_covariance_detector_order",
        "prior_covariance_native_dimension",
        "prior_covariance_order",
        "prior_covariance_unit_convention",
        "detector_pose_jacobian_rows",
        "detector_pose_jacobian_column_order",
        "detector_pose_jacobian_unit_convention",
        "signed_geometric_residual_pd2",
        "formal_filter_innovation_h",
        "residual_unit",
        "measurement_weight_representation",
        "measurement_variance_scalar_m2",
        "measurement_variance_applies_to_all_rows",
        "accepted_source_indices",
        "correspondence_proxy_ids",
        "plane_parameters_world",
        "plane_parameter_convention",
        "ordered_neighbor_coordinates_world",
        "neighbor_coordinate_frame",
        "neighbor_coordinate_unit",
        "valid_correspondence_count",
        "native_jacobian_column_count",
        "detector_jacobian_column_count",
        "checksum_algorithm",
        "formal_native_jacobian_checksum",
        "detector_jacobian_checksum",
        "formal_innovation_checksum",
        "geometric_residual_checksum",
        "accepted_index_checksum",
        "correspondence_proxy_checksum",
        "prior_covariance_checksum",
    }
)

_CHECKSUM_FIELDS = (
    "formal_native_jacobian_checksum",
    "detector_jacobian_checksum",
    "formal_innovation_checksum",
    "geometric_residual_checksum",
    "accepted_index_checksum",
    "correspondence_proxy_checksum",
    "prior_covariance_checksum",
)

_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_UINT64_MAX = (1 << 64) - 1


def validate_scan_lifecycle_record(record: Mapping[str, Any]) -> None:
    """Validate one scan lifecycle record."""

    _require_mapping(record, "scan lifecycle record")
    _reject_forbidden_fields(record)
    _require_exact_fields(record, _LIFECYCLE_FIELDS, "scan lifecycle record")

    _require_constant(record, "record_type", "scan_lifecycle")
    _require_constant(record, "schema_version", SCHEMA_VERSION)
    _require_bool(record, "synthetic_only")
    _require_uint(record, "scan_index")
    _require_finite_number(record, "timestamp_begin")
    _require_finite_number(record, "timestamp_end")
    if float(record["timestamp_end"]) < float(record["timestamp_begin"]):
        raise ValueError("timestamp_end must not precede timestamp_begin")
    _require_constant(record, "timestamp_unit", "seconds")

    for name in (
        "tap_enabled",
        "update_invoked",
        "first_valid_linearization_found",
        "record_emitted",
    ):
        _require_bool(record, name)
    for name in (
        "measurement_call_count",
        "valid_measurement_call_count",
        "downsampled_point_count",
        "valid_correspondence_count",
    ):
        _require_uint(record, name, maximum=(1 << 32) - 1)

    if int(record["valid_measurement_call_count"]) > int(
        record["measurement_call_count"]
    ):
        raise ValueError(
            "valid_measurement_call_count exceeds measurement_call_count"
        )
    if bool(record["record_emitted"]) and not bool(
        record["first_valid_linearization_found"]
    ):
        raise ValueError("record_emitted requires a first valid linearization")
    if bool(record["record_emitted"]) and int(
        record["valid_correspondence_count"]
    ) <= 0:
        raise ValueError("an emitted record requires positive correspondence count")

    if record["skip_reason"] not in SKIP_REASONS:
        raise ValueError(f"unsupported skip_reason: {record['skip_reason']!r}")
    _require_constant(
        record, "adapter_contract_version", ADAPTER_CONTRACT_VERSION
    )
    commit = record["fastlio2_commit"]
    if not isinstance(commit, str) or _COMMIT_RE.fullmatch(commit) is None:
        raise ValueError("fastlio2_commit must be a lowercase 40-hex commit")


def validate_first_valid_observation_record(
    record: Mapping[str, Any],
) -> None:
    """Validate one first-valid observation record."""

    _require_mapping(record, "first-valid observation record")
    _reject_forbidden_fields(record)
    _require_exact_fields(
        record, _OBSERVATION_FIELDS, "first-valid observation record"
    )

    _require_constant(record, "record_type", "first_valid_observation")
    _require_constant(record, "schema_version", SCHEMA_VERSION)
    _require_bool(record, "synthetic_only")
    _require_uint(record, "scan_index")
    _require_finite_number(record, "timestamp_begin")
    _require_finite_number(record, "timestamp_end")
    if float(record["timestamp_end"]) < float(record["timestamp_begin"]):
        raise ValueError("timestamp_end must not precede timestamp_begin")
    _require_constant(record, "timestamp_unit", "seconds")
    _require_uint(record, "measurement_call_index", maximum=(1 << 32) - 1)
    _require_constant(record, "record_version", FIRST_VALID_RECORD_VERSION)

    _require_numeric_vector(record, "prior_position_world", length=3)
    _require_constant(record, "prior_position_frame", "world")
    _require_constant(record, "prior_position_unit", "meters")
    quaternion = _require_numeric_vector(
        record, "prior_orientation_world_from_imu_xyzw", length=4
    )
    quaternion_norm = math.sqrt(sum(value * value for value in quaternion))
    if abs(quaternion_norm - 1.0) > 1.0e-6:
        raise ValueError("prior orientation quaternion must have unit norm")
    _require_constant(record, "prior_orientation_from_frame", "imu")
    _require_constant(record, "prior_orientation_to_frame", "world")
    _require_constant(
        record, "prior_orientation_representation", "quaternion_xyzw"
    )

    covariance = _require_numeric_matrix(
        record, "prior_covariance_detector_order", rows=6, columns=6
    )
    for row in range(6):
        for column in range(6):
            if abs(covariance[row][column] - covariance[column][row]) > 1.0e-12:
                raise ValueError("prior covariance must be symmetric")
    _require_uint(record, "prior_covariance_native_dimension")
    _require_constant(
        record,
        "prior_covariance_native_dimension",
        NATIVE_COVARIANCE_DIMENSION,
    )
    _require_constant(
        record, "prior_covariance_order", DETECTOR_COVARIANCE_ORDER
    )
    _require_constant(
        record,
        "prior_covariance_unit_convention",
        "rotation_radians_then_translation_meters",
    )

    jacobian = _require_numeric_matrix(
        record, "detector_pose_jacobian_rows", columns=6, minimum_rows=1
    )
    row_count = len(jacobian)
    _require_constant(
        record,
        "detector_pose_jacobian_column_order",
        "delta_theta_xyz_then_delta_position_xyz",
    )
    _require_constant(
        record,
        "detector_pose_jacobian_unit_convention",
        "meters_per_rotation_radian_then_meters_per_translation_meter",
    )

    pd2 = _require_numeric_vector(
        record, "signed_geometric_residual_pd2", length=row_count
    )
    innovation = _require_numeric_vector(
        record, "formal_filter_innovation_h", length=row_count
    )
    for index, (geometric, formal) in enumerate(zip(pd2, innovation)):
        if abs(formal + geometric) > 1.0e-12:
            raise ValueError(
                f"formal innovation and geometric residual disagree at row {index}"
            )
    _require_constant(record, "residual_unit", "meters")

    _require_constant(
        record,
        "measurement_weight_representation",
        "CONSTANT_SCALAR_VARIANCE",
    )
    variance = _require_finite_number(
        record, "measurement_variance_scalar_m2"
    )
    if variance <= 0.0:
        raise ValueError("measurement variance must be positive")
    _require_bool(record, "measurement_variance_applies_to_all_rows")
    if not bool(record["measurement_variance_applies_to_all_rows"]):
        raise ValueError("measurement variance must apply to every row")

    accepted = _require_uint_vector(
        record, "accepted_source_indices", length=row_count
    )
    if any(index < 0 for index in accepted):
        raise ValueError("accepted source indices must be nonnegative")
    _require_uint_vector(record, "correspondence_proxy_ids", length=row_count)
    _require_numeric_matrix(
        record, "plane_parameters_world", rows=row_count, columns=4
    )
    _require_constant(
        record,
        "plane_parameter_convention",
        "normalized_normal_xyz_and_offset_meters",
    )
    _require_neighbor_coordinates(
        record["ordered_neighbor_coordinates_world"], row_count
    )
    _require_constant(record, "neighbor_coordinate_frame", "world")
    _require_constant(record, "neighbor_coordinate_unit", "meters")

    _require_uint(record, "valid_correspondence_count", maximum=(1 << 32) - 1)
    if int(record["valid_correspondence_count"]) != row_count:
        raise ValueError("valid_correspondence_count does not match row count")
    _require_constant(
        record, "native_jacobian_column_count", NATIVE_JACOBIAN_COLUMNS
    )
    _require_constant(
        record, "detector_jacobian_column_count", DETECTOR_JACOBIAN_COLUMNS
    )
    _require_constant(record, "checksum_algorithm", CHECKSUM_ALGORITHM)
    for name in _CHECKSUM_FIELDS:
        _require_uint(record, name, maximum=_UINT64_MAX)


def _reject_forbidden_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for raw_name, child in value.items():
            if not isinstance(raw_name, str):
                raise ValueError(f"{path} contains a non-string field name")
            lowered = raw_name.lower()
            if any(token in lowered for token in _FORBIDDEN_FIELD_TOKENS):
                raise ValueError(f"record contains forbidden field: {raw_name}")
            _reject_forbidden_fields(child, f"{path}.{raw_name}")
    elif _is_sequence(value):
        for index, child in enumerate(value):
            _reject_forbidden_fields(child, f"{path}[{index}]")


def _require_mapping(value: Any, label: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")


def _require_exact_fields(
    record: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    actual = set(record)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise ValueError(
            f"{label} field mismatch: missing={missing}, extra={extra}"
        )


def _require_constant(
    record: Mapping[str, Any], name: str, expected: Any
) -> None:
    if record[name] != expected or (
        isinstance(expected, int) and isinstance(record[name], bool)
    ):
        raise ValueError(f"{name} must equal {expected!r}")


def _require_bool(record: Mapping[str, Any], name: str) -> None:
    if not isinstance(record[name], bool):
        raise ValueError(f"{name} must be boolean")


def _require_uint(
    record: Mapping[str, Any],
    name: str,
    *,
    maximum: int = _UINT64_MAX,
) -> int:
    value = record[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if not 0 <= value <= maximum:
        raise ValueError(f"{name} is outside the unsigned range")
    return value


def _require_finite_number(
    record: Mapping[str, Any], name: str
) -> float:
    value = record[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


def _require_numeric_vector(
    record: Mapping[str, Any], name: str, *, length: int
) -> list[float]:
    values = record[name]
    if not _is_sequence(values) or len(values) != length:
        raise ValueError(f"{name} must have length {length}")
    result: list[float] = []
    for index, value in enumerate(values):
        result.append(_finite_scalar(value, f"{name}[{index}]"))
    return result


def _require_uint_vector(
    record: Mapping[str, Any], name: str, *, length: int
) -> list[int]:
    values = record[name]
    if not _is_sequence(values) or len(values) != length:
        raise ValueError(f"{name} must have length {length}")
    result: list[int] = []
    for index, value in enumerate(values):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value <= _UINT64_MAX
        ):
            raise ValueError(f"{name}[{index}] must be an unsigned integer")
        result.append(value)
    return result


def _require_numeric_matrix(
    record: Mapping[str, Any],
    name: str,
    *,
    columns: int,
    rows: int | None = None,
    minimum_rows: int | None = None,
) -> list[list[float]]:
    matrix = record[name]
    if not _is_sequence(matrix):
        raise ValueError(f"{name} must be an array")
    if rows is not None and len(matrix) != rows:
        raise ValueError(f"{name} must have {rows} rows")
    if minimum_rows is not None and len(matrix) < minimum_rows:
        raise ValueError(f"{name} must have at least {minimum_rows} row")
    result: list[list[float]] = []
    for row_index, row in enumerate(matrix):
        if not _is_sequence(row) or len(row) != columns:
            raise ValueError(
                f"{name}[{row_index}] must have {columns} columns"
            )
        result.append(
            [
                _finite_scalar(value, f"{name}[{row_index}][{column_index}]")
                for column_index, value in enumerate(row)
            ]
        )
    return result


def _require_neighbor_coordinates(value: Any, row_count: int) -> None:
    if not _is_sequence(value) or len(value) != row_count:
        raise ValueError(
            "ordered_neighbor_coordinates_world must have one row per correspondence"
        )
    for row_index, neighbors in enumerate(value):
        if not _is_sequence(neighbors) or len(neighbors) < 1:
            raise ValueError(
                f"ordered_neighbor_coordinates_world[{row_index}] must be nonempty"
            )
        for neighbor_index, point in enumerate(neighbors):
            if not _is_sequence(point) or len(point) != 3:
                raise ValueError(
                    "each ordered neighbor coordinate must have three components"
                )
            for coordinate_index, coordinate in enumerate(point):
                _finite_scalar(
                    coordinate,
                    "ordered_neighbor_coordinates_world"
                    f"[{row_index}][{neighbor_index}][{coordinate_index}]",
                )


def _finite_scalar(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{path} must be finite")
    return numeric


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )
