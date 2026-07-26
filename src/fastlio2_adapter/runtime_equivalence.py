"""Deterministic Day 5 remediation comparisons and run-lock helpers."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import yaml


POSITION_TOLERANCE_M = 1.0e-12
ROTATION_TOLERANCE_RAD = 1.0e-12
COVARIANCE_TOLERANCE = 1.0e-12
RUNTIME_WARMUP_VALID_SCAN_COUNT = 20
HARD_MEAN_OVERHEAD_PERCENT = 25.0
HARD_Q95_OVERHEAD_PERCENT = 40.0
TARGET_MEAN_OVERHEAD_PERCENT = 10.0
TARGET_Q95_OVERHEAD_PERCENT = 15.0

CHECKSUM_FIELDS = (
    "measure_group_checksum",
    "prior_state_checksum",
    "prior_covariance_checksum",
    "posterior_state_checksum",
    "posterior_covariance_checksum",
    "formal_native_jacobian_checksum",
    "detector_jacobian_checksum",
    "formal_innovation_checksum",
    "geometric_residual_checksum",
    "accepted_index_checksum",
    "formal_correspondence_checksum",
)
EXACT_FIELDS = (
    "timestamp_begin",
    "timestamp_end",
    "update_invoked",
    "first_valid_linearization_found",
    "skip_reason",
    "measurement_call_count",
    "valid_measurement_call_count",
    "downsampled_point_count",
    "valid_correspondence_count",
    "map_size_after_update",
    "lidar_point_count",
    "imu_message_count",
    "first_imu_timestamp",
    "last_imu_timestamp",
    "lidar_begin_time",
    "lidar_end_time",
)
PARAMETER_DIFF_ALLOWLIST = frozenset(
    {
        "harmful_bias/runtime_mode",
        "harmful_bias/runtime_equivalence_output_dir",
        "harmful_bias/run_id",
    }
)
FIRST_DIVERGENCE_STAGES = (
    "NONE",
    "INPUT_GROUP",
    "PRIOR_STATE",
    "PRIOR_COVARIANCE",
    "FORMAL_LINEARIZATION",
    "POSTERIOR_STATE",
    "POSTERIOR_COVARIANCE",
    "MAP_SIZE",
    "FINAL_MAP",
)


def load_runtime_frames(path: Path) -> list[dict[str, Any]]:
    """Load a converted runtime CSV and reject duplicate scan identities."""

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            row = _parse_runtime_row(raw)
            key = (str(row["sequence_id"]), int(row["scan_index"]))
            if key in seen:
                raise ValueError(f"duplicate runtime scan: {key}")
            seen.add(key)
            rows.append(row)
    if not rows:
        raise ValueError(f"runtime audit has no rows: {path}")
    return rows


def compare_runtime_rows(
    left_rows: Sequence[Mapping[str, Any]],
    right_rows: Sequence[Mapping[str, Any]],
    *,
    comparison_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Strictly compare two runs and localize the first divergence stage."""

    left = _index_rows(left_rows)
    right = _index_rows(right_rows)
    missing_keys = sorted(set(left) ^ set(right))
    common = sorted(set(left) & set(right))
    detail: list[dict[str, Any]] = []
    max_position = 0.0
    max_rotation = 0.0
    max_covariance = 0.0
    exact_mismatches = {name: 0 for name in EXACT_FIELDS}
    checksum_mismatches = {name: 0 for name in CHECKSUM_FIELDS}
    first_divergence_scan_index: int | None = None
    first_divergence_stage = "NONE"

    if missing_keys:
        first_divergence_scan_index = int(missing_keys[0][1])
        first_divergence_stage = "INPUT_GROUP"

    for key in common:
        left_row = left[key]
        right_row = right[key]
        position = _euclidean_difference(
            left_row["posterior_position"], right_row["posterior_position"]
        )
        if left_row["posterior_state_checksum"] == right_row[
            "posterior_state_checksum"
        ]:
            rotation = 0.0
        else:
            rotation = quaternion_geodesic_difference(
                left_row["posterior_orientation_xyzw"],
                right_row["posterior_orientation_xyzw"],
            )
        covariance = _maximum_absolute_difference(
            left_row["posterior_covariance_native_flat"],
            right_row["posterior_covariance_native_flat"],
        )
        max_position = max(max_position, position)
        max_rotation = max(max_rotation, rotation)
        max_covariance = max(max_covariance, covariance)
        for field in EXACT_FIELDS:
            exact_mismatches[field] += int(left_row[field] != right_row[field])
        for field in CHECKSUM_FIELDS:
            checksum_mismatches[field] += int(
                left_row[field] != right_row[field]
            )

        stage = _row_divergence_stage(
            left_row,
            right_row,
            position=position,
            rotation=rotation,
            covariance=covariance,
        )
        if stage != "NONE":
            detail.append(
                {
                    "comparison_id": comparison_id,
                    "sequence_id": key[0],
                    "scan_index": key[1],
                    "first_mismatch_stage": stage,
                    "position_difference_m": position,
                    "rotation_difference_rad": rotation,
                    "covariance_difference": covariance,
                    "mismatch": True,
                }
            )
            if first_divergence_scan_index is None or key[1] < first_divergence_scan_index:
                first_divergence_scan_index = int(key[1])
                first_divergence_stage = stage

    checksum_total = sum(checksum_mismatches.values())
    exact_total = sum(exact_mismatches.values())
    runtime_pass = (
        not missing_keys
        and exact_total == 0
        and checksum_total == 0
        and max_position <= POSITION_TOLERANCE_M
        and max_rotation <= ROTATION_TOLERANCE_RAD
        and max_covariance <= COVARIANCE_TOLERANCE
    )
    summary: dict[str, Any] = {
        "comparison_id": comparison_id,
        "paired_scan_count": len(common),
        "missing_scan_count": len(missing_keys),
        "duplicate_scan_count": 0,
        "max_position_difference_m": max_position,
        "max_rotation_geodesic_difference_rad": max_rotation,
        "max_covariance_absolute_difference": max_covariance,
        "exact_field_mismatch_count": exact_total,
        "checksum_mismatch_count": checksum_total,
        "first_divergence_scan_index": first_divergence_scan_index,
        "first_divergence_stage": first_divergence_stage,
        "runtime_equivalence_pass": runtime_pass,
    }
    summary.update(
        {f"{name}_mismatch_count": value for name, value in checksum_mismatches.items()}
    )
    summary.update(
        {f"{name}_mismatch_count": value for name, value in exact_mismatches.items()}
    )
    return summary, detail


def compare_final_maps(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> dict[str, Any]:
    size_match = int(left["final_map_point_count"]) == int(
        right["final_map_point_count"]
    )
    checksum_match = int(left["final_map_checksum"]) == int(
        right["final_map_checksum"]
    )
    algorithm_match = (
        left["map_checksum_algorithm"] == right["map_checksum_algorithm"]
        == "FNV1A64_SORTED_FLOAT32_XYZI_V1"
    )
    return {
        "final_map_size_match": size_match,
        "final_map_checksum_match": checksum_match,
        "final_map_algorithm_match": algorithm_match,
        "final_map_equivalence_pass": (
            size_match and checksum_match and algorithm_match
        ),
    }


def combine_equivalence_results(
    runtime_result: Mapping[str, Any],
    map_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Combine independently named runtime and final-map results."""

    combined = {**runtime_result, **map_result}
    combined["overall_equivalence_pass"] = bool(
        combined["runtime_equivalence_pass"]
        and combined["final_map_equivalence_pass"]
    )
    if (
        combined.get("first_divergence_stage") == "NONE"
        and not combined["final_map_equivalence_pass"]
    ):
        combined["first_divergence_stage"] = "FINAL_MAP"
        combined["first_divergence_scan_index"] = None
    return combined


def compare_parameter_documents(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    allowlist: frozenset[str] = PARAMETER_DIFF_ALLOWLIST,
) -> dict[str, Any]:
    left_flat = _flatten_mapping(left)
    right_flat = _flatten_mapping(right)
    differing = sorted(
        key
        for key in set(left_flat) | set(right_flat)
        if not _is_ephemeral_ros_parameter(key)
        and left_flat.get(key) != right_flat.get(key)
    )
    normalized = [_normalize_parameter_name(key) for key in differing]
    forbidden = [
        key
        for key, name in zip(differing, normalized)
        if name not in allowlist
    ]
    return {
        "differing_parameter_count": len(differing),
        "non_allowlisted_parameter_difference_count": len(forbidden),
        "differing_parameters": differing,
        "non_allowlisted_parameters": forbidden,
        "parameter_diff_allowlist_pass": not forbidden,
    }


def runtime_overhead(
    baseline_rows: Sequence[Mapping[str, Any]],
    active_rows: Sequence[Mapping[str, Any]],
    *,
    warmup_valid_scan_count: int = RUNTIME_WARMUP_VALID_SCAN_COUNT,
) -> dict[str, Any]:
    baseline = _index_rows(baseline_rows)
    active = _index_rows(active_rows)
    common = sorted(set(baseline) & set(active))
    valid = [
        key
        for key in common
        if bool(baseline[key]["update_invoked"])
        and bool(active[key]["update_invoked"])
    ]
    measured = valid[warmup_valid_scan_count:]
    if not measured:
        raise ValueError("too few valid scans after runtime warmup")
    relative: list[float] = []
    tap_capture: list[float] = []
    binary_writer: list[float] = []
    for key in measured:
        baseline_ns = int(baseline[key]["scan_total_runtime_ns"])
        active_ns = int(active[key]["scan_total_runtime_ns"])
        if baseline_ns <= 0 or active_ns <= 0:
            raise ValueError("runtime must be positive")
        relative.append((active_ns / baseline_ns - 1.0) * 100.0)
        tap_capture.append(float(active[key]["tap_capture_ns"]))
        binary_writer.append(float(active[key]["binary_writer_ns"]))
    result = {
        "warmup_valid_scan_count": warmup_valid_scan_count,
        "measured_scan_count": len(measured),
        "mean_overhead_percent": float(np.mean(relative)),
        "median_overhead_percent": float(np.median(relative)),
        "q95_overhead_percent": float(np.quantile(relative, 0.95)),
        "max_overhead_percent": float(np.max(relative)),
        "tap_capture_mean_ns": float(np.mean(tap_capture)),
        "tap_capture_q95_ns": float(np.quantile(tap_capture, 0.95)),
        "binary_writer_mean_ns": float(np.mean(binary_writer)),
        "binary_writer_q95_ns": float(np.quantile(binary_writer, 0.95)),
    }
    result["runtime_hard_gate"] = (
        result["mean_overhead_percent"] <= HARD_MEAN_OVERHEAD_PERCENT
        and result["q95_overhead_percent"] <= HARD_Q95_OVERHEAD_PERCENT
    )
    result["runtime_target_gate"] = (
        result["mean_overhead_percent"] <= TARGET_MEAN_OVERHEAD_PERCENT
        and result["q95_overhead_percent"] <= TARGET_Q95_OVERHEAD_PERCENT
    )
    return result


def verify_file_sha256(path: Path, expected: str) -> bool:
    return hashlib.sha256(path.read_bytes()).hexdigest() == expected


def verify_run_lock(lock: Mapping[str, Any], actual: Mapping[str, Any]) -> None:
    """Fail closed if any locked key supplied by the caller changed."""

    for key, value in actual.items():
        if key not in lock:
            raise ValueError(f"run lock is missing {key}")
        if lock[key] != value:
            raise ValueError(f"run lock mismatch for {key}")


def load_yaml(path: Path) -> Mapping[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"YAML document must be a mapping: {path}")
    return value


def load_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"JSON document must be a mapping: {path}")
    return value


def quaternion_geodesic_difference(
    left: Sequence[float], right: Sequence[float]
) -> float:
    """Stable sign-invariant quaternion distance using atan2."""

    left_array = np.asarray(left, dtype=np.float64)
    right_array = np.asarray(right, dtype=np.float64)
    if left_array.shape != (4,) or right_array.shape != (4,):
        raise ValueError("quaternions must have four xyzw components")
    if np.array_equal(left_array, right_array):
        return 0.0
    left_norm = float(np.linalg.norm(left_array))
    right_norm = float(np.linalg.norm(right_array))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ValueError("quaternion norm must be positive")
    left_unit = left_array / left_norm
    right_unit = right_array / right_norm
    if float(np.dot(left_unit, right_unit)) < 0.0:
        right_unit = -right_unit
    numerator = float(np.linalg.norm(left_unit - right_unit))
    denominator = float(np.linalg.norm(left_unit + right_unit))
    return 2.0 * math.atan2(numerator, denominator)


def _row_divergence_stage(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    position: float,
    rotation: float,
    covariance: float,
) -> str:
    if any(
        left[field] != right[field]
        for field in (
            "measure_group_checksum",
            "timestamp_begin",
            "timestamp_end",
            "lidar_point_count",
            "imu_message_count",
            "first_imu_timestamp",
            "last_imu_timestamp",
            "lidar_begin_time",
            "lidar_end_time",
        )
    ):
        return "INPUT_GROUP"
    if left["prior_state_checksum"] != right["prior_state_checksum"]:
        return "PRIOR_STATE"
    if left["prior_covariance_checksum"] != right["prior_covariance_checksum"]:
        return "PRIOR_COVARIANCE"
    if any(
        left[field] != right[field]
        for field in (
            "formal_native_jacobian_checksum",
            "detector_jacobian_checksum",
            "formal_innovation_checksum",
            "geometric_residual_checksum",
            "accepted_index_checksum",
            "formal_correspondence_checksum",
            "measurement_call_count",
            "valid_measurement_call_count",
            "valid_correspondence_count",
        )
    ):
        return "FORMAL_LINEARIZATION"
    if (
        left["posterior_state_checksum"] != right["posterior_state_checksum"]
        or position > POSITION_TOLERANCE_M
        or rotation > ROTATION_TOLERANCE_RAD
    ):
        return "POSTERIOR_STATE"
    if (
        left["posterior_covariance_checksum"]
        != right["posterior_covariance_checksum"]
        or covariance > COVARIANCE_TOLERANCE
    ):
        return "POSTERIOR_COVARIANCE"
    if left["map_size_after_update"] != right["map_size_after_update"]:
        return "MAP_SIZE"
    if any(left[field] != right[field] for field in EXACT_FIELDS):
        return "FORMAL_LINEARIZATION"
    return "NONE"


def _parse_runtime_row(raw: Mapping[str, str]) -> dict[str, Any]:
    row: dict[str, Any] = dict(raw)
    integer_fields = (
        "scan_index",
        "measurement_call_count",
        "valid_measurement_call_count",
        "downsampled_point_count",
        "valid_correspondence_count",
        "map_size_after_update",
        "lidar_point_count",
        "imu_message_count",
        *CHECKSUM_FIELDS,
        "tap_drop_count",
        "tap_pre_state_checksum",
        "tap_post_state_checksum",
        "tap_pre_covariance_checksum",
        "tap_post_covariance_checksum",
        "tap_pre_native_jacobian_checksum",
        "tap_post_native_jacobian_checksum",
        "tap_pre_innovation_checksum",
        "tap_post_innovation_checksum",
        "tap_pre_geometric_residual_checksum",
        "tap_post_geometric_residual_checksum",
        "tap_pre_correspondence_checksum",
        "tap_post_correspondence_checksum",
        "tap_pre_map_size",
        "tap_post_map_size",
        "export_pre_estimator_checksum",
        "export_post_estimator_checksum",
        "scan_total_runtime_ns",
        "runtime_audit_ns",
        "tap_capture_ns",
        "binary_writer_ns",
    )
    for field in integer_fields:
        row[field] = int(raw[field])
    for field in (
        "timestamp_begin",
        "timestamp_end",
        "first_imu_timestamp",
        "last_imu_timestamp",
        "lidar_begin_time",
        "lidar_end_time",
    ):
        row[field] = float(raw[field])
        if not math.isfinite(row[field]):
            raise ValueError(f"nonfinite runtime value in {field}")
    for field in (
        "update_invoked",
        "first_valid_linearization_found",
        "tap_enabled",
        "tap_record_emitted",
        "tap_call_mutation_detected",
        "export_call_mutation_detected",
    ):
        if raw[field] not in {"true", "false"}:
            raise ValueError(f"invalid boolean in {field}")
        row[field] = raw[field] == "true"
    for field in (
        "prior_position",
        "prior_orientation_xyzw",
        "posterior_position",
        "posterior_orientation_xyzw",
        "posterior_state_native",
        "posterior_covariance_native_flat",
    ):
        row[field] = [float(value) for value in raw[field].split(";") if value]
        if not all(math.isfinite(value) for value in row[field]):
            raise ValueError(f"nonfinite runtime value in {field}")
    return row


def _index_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, int], Mapping[str, Any]]:
    result: dict[tuple[str, int], Mapping[str, Any]] = {}
    for row in rows:
        key = (str(row["sequence_id"]), int(row["scan_index"]))
        if key in result:
            raise ValueError(f"duplicate scan: {key}")
        result[key] = row
    return result


def _euclidean_difference(left: Sequence[float], right: Sequence[float]) -> float:
    return float(
        np.linalg.norm(
            np.asarray(left, dtype=np.float64)
            - np.asarray(right, dtype=np.float64)
        )
    )


def _maximum_absolute_difference(
    left: Sequence[float], right: Sequence[float]
) -> float:
    left_array = np.asarray(left, dtype=np.float64)
    right_array = np.asarray(right, dtype=np.float64)
    if left_array.shape != right_array.shape:
        return math.inf
    if left_array.size == 0:
        return 0.0
    return float(np.max(np.abs(left_array - right_array)))


def _flatten_mapping(
    value: Mapping[str, Any], prefix: str = ""
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, child in value.items():
        name = f"{prefix}/{key}" if prefix else str(key)
        if isinstance(child, Mapping):
            result.update(_flatten_mapping(child, name))
        else:
            result[name] = child
    return result


def _normalize_parameter_name(name: str) -> str:
    stripped = name.lstrip("/")
    if stripped.startswith("laserMapping/"):
        stripped = stripped[len("laserMapping/") :]
    return stripped


def _is_ephemeral_ros_parameter(name: str) -> bool:
    stripped = name.lstrip("/")
    return stripped == "run_id" or stripped.startswith("roslaunch/")
