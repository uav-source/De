"""Schema and canonical digest support for Day 6 Experiment A.

The runtime service exports only checksums, counts, timestamps, and diagnostic
status. Matching checksums mean ``MATCHED_BY_CANONICAL_CHECKSUM`` and retain
the ordinary finite-checksum collision limitation.
"""

from __future__ import annotations

import csv
import json
import math
import struct
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "experiment_a_stage_hash_record_v2"
STATUS_SCHEMA_VERSION = "experiment_a_stage_hash_status_v2"
SNAPSHOT_SCHEMA_VERSION = "coherent_map_snapshot_v2"
SNAPSHOT_METHOD = "KD_TREE_REBUILD_PTR_THEN_WORKING_MUTEX_COPY_V1"
HASH_ALGORITHM = "FNV1A64_EXACT_BYTES_V1"
MAP_DIGEST_VERSION = "MapContentDigestV1+MapTraversalDigestV1"
SCAN_START = 135
SCAN_END = 160
EXPECTED_RECORD_COUNT = 26
FNV_OFFSET_BASIS = 14695981039346656037
FNV_PRIME = 1099511628211

SNAPSHOT_REQUIRED_SUFFIXES = (
    "snapshot_schema_version",
    "snapshot_stage",
    "snapshot_status",
    "snapshot_method",
    "snapshot_coherence_pass",
    "lock_wait_ns",
    "locked_copy_ns",
    "digest_compute_ns",
    "snapshot_attempt_count",
    "rebuild_active_before",
    "rebuild_active_after",
    "rebuild_generation_before",
    "rebuild_generation_after",
    "mutation_counter_before",
    "mutation_counter_after",
    "validnum_before",
    "validnum_after",
    "snapshot_point_count",
    "snapshot_nonfinite_point_count",
    "content_checksum",
    "traversal_checksum",
    "xor_of_point_hashes",
    "sum_of_point_hashes_mod_2_64",
    "sum_of_rotated_point_hashes_mod_2_64",
    "min_point_hash",
    "max_point_hash",
    "bbox_min_x",
    "bbox_min_y",
    "bbox_min_z",
    "bbox_max_x",
    "bbox_max_y",
    "bbox_max_z",
    "logical_add_call_count_total",
    "logical_delete_call_count_total",
    "logical_add_input_point_count_total",
    "logical_delete_box_count_total",
    "snapshot_error",
)

REQUIRED_FIELDS = (
    "schema_version",
    "run_id",
    "scan_index",
    "measurement_call_index",
    "timestamp_begin",
    "timestamp_end",
    "window_start",
    "window_end",
    "window_enabled",
    "raw_lidar_payload_checksum",
    "raw_lidar_point_count",
    "raw_lidar_byte_count",
    "raw_lidar_nonfinite_count",
    "raw_lidar_message_stamp",
    "imu_bundle_checksum",
    "imu_bundle_message_count",
    "imu_bundle_first_stamp",
    "imu_bundle_last_stamp",
    "imu_bundle_byte_count",
    "imu_bundle_nonfinite_count",
    "undistorted_cloud_checksum",
    "undistorted_point_count",
    "undistorted_cloud_byte_count",
    "undistorted_nonfinite_count",
    "prior_state_checksum",
    "prior_covariance_checksum",
    "map_content_before_measurement",
    "map_traversal_before_measurement",
    "map_count_before_measurement",
    "valid_correspondence_count",
    "accepted_index_checksum",
    "formal_correspondence_checksum",
    "formal_native_jacobian_checksum",
    "detector_jacobian_checksum",
    "formal_innovation_checksum",
    "geometric_residual_checksum",
    "post_update_state_checksum",
    "post_update_covariance_checksum",
    "map_insertion_executed",
    "map_insertion_batch_ordered_checksum",
    "map_insertion_batch_multiset_checksum",
    "map_insertion_batch_point_count",
    "map_content_after_insertion",
    "map_traversal_after_insertion",
    "map_count_after_insertion",
    "map_mutation_counter_before_measurement",
    "map_mutation_counter_after_insertion",
    "logical_add_call_count",
    "logical_delete_call_count",
    "logical_add_input_point_count",
    "logical_delete_box_count",
    "logical_added_point_count",
    "logical_deleted_point_count",
    "diagnostic_read_only_check_pass",
    "diagnostic_internal_error",
) + tuple(
    f"{prefix}_{suffix}"
    for prefix in ("map_before", "map_after")
    for suffix in SNAPSHOT_REQUIRED_SUFFIXES
)

FORBIDDEN_FIELDS = (
    "raw_lidar_payload",
    "imu_messages",
    "undistorted_cloud",
    "map_points",
    "accepted_indices",
    "nearest_neighbors",
    "plane_parameters",
    "ground_truth",
    "detector_output",
    "odi",
    "weak_direction",
)


class ExperimentAStageHashError(ValueError):
    """Raised when bounded stage-hash evidence violates its contract."""


def _fnv1a(data: bytes) -> int:
    value = FNV_OFFSET_BASIS
    for byte in data:
        value ^= byte
        value = (value * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return value


def _point_bytes(point: Sequence[float]) -> bytes:
    if len(point) != 8:
        raise ExperimentAStageHashError("canonical point requires 8 floats")
    return b"".join(struct.pack("<f", float(value)) for value in point)


def canonical_point_hash(point: Sequence[float]) -> int:
    return _fnv1a(_point_bytes(point))


def _rotate_left(value: int, shift: int) -> int:
    shift &= 63
    if not shift:
        return value & 0xFFFFFFFFFFFFFFFF
    return (
        (value << shift) | (value >> (64 - shift))
    ) & 0xFFFFFFFFFFFFFFFF


def map_digest(points: Iterable[Sequence[float]]) -> dict[str, Any]:
    """Reproduce the C++ MapContentDigestV1/MapTraversalDigestV1 reduction."""

    rows = [tuple(float(value) for value in point) for point in points]
    hashes = [canonical_point_hash(point) for point in rows]
    xor_hash = 0
    sum_hash = 0
    rotated_sum = 0
    for value in hashes:
        xor_hash ^= value
        sum_hash = (sum_hash + value) & 0xFFFFFFFFFFFFFFFF
        rotated_sum = (
            rotated_sum + _rotate_left(value, value & 63)
        ) & 0xFFFFFFFFFFFFFFFF
    minimum = min(hashes, default=0)
    maximum = max(hashes, default=0)
    content_bytes = struct.pack(
        "<QQQQQQ",
        len(hashes),
        xor_hash,
        sum_hash,
        rotated_sum,
        minimum,
        maximum,
    )
    traversal_bytes = struct.pack("<Q", len(hashes)) + b"".join(
        struct.pack("<Q", value) for value in hashes
    )
    finite_xyz = [
        row[:3] for row in rows if all(math.isfinite(value) for value in row[:3])
    ]
    bbox_min = (
        [min(row[axis] for row in finite_xyz) for axis in range(3)]
        if finite_xyz
        else [0.0, 0.0, 0.0]
    )
    bbox_max = (
        [max(row[axis] for row in finite_xyz) for axis in range(3)]
        if finite_xyz
        else [0.0, 0.0, 0.0]
    )
    return {
        "map_digest_version": MAP_DIGEST_VERSION,
        "point_count": len(rows),
        "xor_of_point_hashes": xor_hash,
        "sum_of_point_hashes_mod_2_64": sum_hash,
        "sum_of_rotated_point_hashes_mod_2_64": rotated_sum,
        "min_point_hash": minimum,
        "max_point_hash": maximum,
        "map_content_multiset_checksum": _fnv1a(content_bytes),
        "map_traversal_order_checksum": _fnv1a(traversal_bytes),
        "map_nonfinite_count": sum(
            not math.isfinite(value) for row in rows for value in row
        ),
        "map_bbox_min": bbox_min,
        "map_bbox_max": bbox_max,
    }


def validate_record(record: Mapping[str, Any]) -> dict[str, Any]:
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    forbidden = [field for field in FORBIDDEN_FIELDS if field in record]
    if missing:
        raise ExperimentAStageHashError(f"missing stage fields: {missing}")
    if forbidden:
        raise ExperimentAStageHashError(f"forbidden payload fields: {forbidden}")
    if record["schema_version"] != SCHEMA_VERSION:
        raise ExperimentAStageHashError("stage schema version mismatch")
    scan = int(record["scan_index"])
    if not SCAN_START <= scan <= SCAN_END:
        raise ExperimentAStageHashError(f"scan outside window: {scan}")
    if int(record["window_start"]) != SCAN_START:
        raise ExperimentAStageHashError("window start mismatch")
    if int(record["window_end"]) != SCAN_END:
        raise ExperimentAStageHashError("window end mismatch")
    if record["window_enabled"] is not True:
        raise ExperimentAStageHashError("window must be enabled")
    if record["diagnostic_read_only_check_pass"] is not True:
        raise ExperimentAStageHashError("diagnostic mutation detected")
    if record["diagnostic_internal_error"] is not False:
        raise ExperimentAStageHashError("diagnostic internal error")
    expected_stages = {
        "map_before": "map_snapshot_before_measurement",
        "map_after": "map_snapshot_after_all_map_mutations",
    }
    for prefix, expected_stage in expected_stages.items():
        if record[f"{prefix}_snapshot_schema_version"] != (
            SNAPSHOT_SCHEMA_VERSION
        ):
            raise ExperimentAStageHashError(
                f"{prefix} snapshot schema mismatch"
            )
        if record[f"{prefix}_snapshot_stage"] != expected_stage:
            raise ExperimentAStageHashError(
                f"{prefix} snapshot stage mismatch"
            )
        if record[f"{prefix}_snapshot_method"] != SNAPSHOT_METHOD:
            raise ExperimentAStageHashError(
                f"{prefix} snapshot method mismatch"
            )
        if record[f"{prefix}_snapshot_status"] != (
            "COHERENT_SYNCHRONIZED_COPY"
        ):
            raise ExperimentAStageHashError(
                f"{prefix} snapshot not coherent"
            )
        if record[f"{prefix}_snapshot_coherence_pass"] is not True:
            raise ExperimentAStageHashError(
                f"{prefix} snapshot coherence gate failed"
            )
        if record[f"{prefix}_snapshot_error"] is not None:
            raise ExperimentAStageHashError(
                f"{prefix} snapshot has error"
            )
        if not 1 <= int(record[f"{prefix}_snapshot_attempt_count"]) <= 3:
            raise ExperimentAStageHashError(
                f"{prefix} snapshot attempt count invalid"
            )
        if int(record[f"{prefix}_validnum_before"]) != int(
            record[f"{prefix}_validnum_after"]
        ):
            raise ExperimentAStageHashError(
                f"{prefix} validnum changed during snapshot"
            )
        if int(record[f"{prefix}_validnum_before"]) != int(
            record[f"{prefix}_snapshot_point_count"]
        ):
            raise ExperimentAStageHashError(
                f"{prefix} snapshot point count mismatch"
            )
        if int(record[f"{prefix}_rebuild_generation_before"]) != int(
            record[f"{prefix}_rebuild_generation_after"]
        ):
            raise ExperimentAStageHashError(
                f"{prefix} generation changed during snapshot"
            )
        if int(record[f"{prefix}_mutation_counter_before"]) != int(
            record[f"{prefix}_mutation_counter_after"]
        ):
            raise ExperimentAStageHashError(
                f"{prefix} mutation counter changed during snapshot"
            )
        alias_suffix = (
            "before_measurement" if prefix == "map_before"
            else "after_insertion"
        )
        if int(record[f"map_content_{alias_suffix}"]) != int(
            record[f"{prefix}_content_checksum"]
        ):
            raise ExperimentAStageHashError(
                f"{prefix} content alias mismatch"
            )
        if int(record[f"map_traversal_{alias_suffix}"]) != int(
            record[f"{prefix}_traversal_checksum"]
        ):
            raise ExperimentAStageHashError(
                f"{prefix} traversal alias mismatch"
            )
        if int(record[f"map_count_{alias_suffix}"]) != int(
            record[f"{prefix}_snapshot_point_count"]
        ):
            raise ExperimentAStageHashError(
                f"{prefix} count alias mismatch"
            )
    for field in (
        "raw_lidar_nonfinite_count",
        "imu_bundle_nonfinite_count",
        "undistorted_nonfinite_count",
        "map_before_nonfinite_count",
        "map_insertion_nonfinite_count",
        "map_after_nonfinite_count",
        "map_before_snapshot_nonfinite_point_count",
        "map_after_snapshot_nonfinite_point_count",
    ):
        if int(record.get(field, 0)) != 0:
            raise ExperimentAStageHashError(f"nonfinite stage input: {field}")
    for field in (
        "raw_lidar_payload_checksum",
        "imu_bundle_checksum",
        "undistorted_cloud_checksum",
        "prior_state_checksum",
        "prior_covariance_checksum",
        "map_content_before_measurement",
        "map_traversal_before_measurement",
        "accepted_index_checksum",
        "formal_correspondence_checksum",
        "formal_native_jacobian_checksum",
        "detector_jacobian_checksum",
        "formal_innovation_checksum",
        "geometric_residual_checksum",
        "post_update_state_checksum",
        "post_update_covariance_checksum",
        "map_insertion_batch_ordered_checksum",
        "map_insertion_batch_multiset_checksum",
        "map_content_after_insertion",
        "map_traversal_after_insertion",
    ):
        if int(record[field]) == 0:
            raise ExperimentAStageHashError(f"zero checksum: {field}")
    return dict(record)


def validate_status(status: Mapping[str, Any]) -> dict[str, Any]:
    if status.get("schema_version") != STATUS_SCHEMA_VERSION:
        raise ExperimentAStageHashError("status schema mismatch")
    if status.get("enabled") is not True:
        raise ExperimentAStageHashError("stage hash collector disabled")
    if status.get("hash_algorithm") != HASH_ALGORITHM:
        raise ExperimentAStageHashError("hash algorithm mismatch")
    if status.get("map_digest_version") != MAP_DIGEST_VERSION:
        raise ExperimentAStageHashError("map digest version mismatch")
    if status.get("snapshot_schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise ExperimentAStageHashError("snapshot schema mismatch")
    if status.get("snapshot_method") != SNAPSHOT_METHOD:
        raise ExperimentAStageHashError("snapshot method mismatch")
    if int(status.get("diagnostic_mutation_count", -1)) != 0:
        raise ExperimentAStageHashError("diagnostic mutation count is nonzero")
    if int(status.get("internal_error_count", -1)) != 0:
        raise ExperimentAStageHashError("stage collector internal error")
    raw_records = status.get("records")
    if not isinstance(raw_records, list):
        raise ExperimentAStageHashError("status records must be a list")
    records = [validate_record(record) for record in raw_records]
    scans = [int(record["scan_index"]) for record in records]
    expected = list(range(SCAN_START, SCAN_END + 1))
    if scans != expected:
        raise ExperimentAStageHashError(
            f"stage scan coverage mismatch: {scans}"
        )
    if len(records) != EXPECTED_RECORD_COUNT:
        raise ExperimentAStageHashError("stage record count mismatch")
    run_ids = {str(record["run_id"]) for record in records}
    if len(run_ids) != 1 or not next(iter(run_ids)):
        raise ExperimentAStageHashError("stage run-id mismatch")
    return {
        **dict(status),
        "records": records,
        "stage_hash_schema_pass": True,
        "stage_hash_record_count_pass": True,
        "stage_hash_window_coverage_pass": True,
        "checksum_collision_limitation": (
            "MATCHED_BY_CANONICAL_CHECKSUM; finite FNV-1a checksums may collide"
        ),
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def materialize_status(
    status: Mapping[str, Any], output_dir: Path
) -> dict[str, Any]:
    validated = validate_status(status)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = validated["records"]
    _write_json(
        output_dir / "experiment_a_stage_hash_records_v2.json", records
    )
    with (output_dir / "experiment_a_stage_hash_records_v2.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    summary = {
        key: value for key, value in validated.items() if key != "records"
    }
    summary.update(
        {
            "schema_version": "experiment_a_stage_hash_summary_v2",
            "run_id": records[0]["run_id"],
            "stage_record_count": len(records),
            "first_scan_index": records[0]["scan_index"],
            "last_scan_index": records[-1]["scan_index"],
            "diagnostic_mutation_count": 0,
            "diagnostic_internal_error_count": 0,
            "raw_lidar_hash_capture_pass": True,
            "imu_bundle_hash_capture_pass": True,
            "undistorted_cloud_hash_capture_pass": True,
            "map_before_hash_capture_pass": True,
            "correspondence_hash_reuse_pass": True,
            "insertion_batch_hash_capture_pass": True,
            "map_after_hash_capture_pass": True,
        }
    )
    _write_json(
        output_dir / "experiment_a_stage_hash_summary_v2.json", summary
    )
    summary_specs = {
        "raw_lidar_hash_summary.json": (
            "raw_lidar_payload_checksum",
            "raw_lidar_point_count",
            "raw_lidar_byte_count",
        ),
        "imu_bundle_hash_summary.json": (
            "imu_bundle_checksum",
            "imu_bundle_message_count",
            "imu_bundle_byte_count",
        ),
        "undistorted_cloud_hash_summary.json": (
            "undistorted_cloud_checksum",
            "undistorted_point_count",
            "undistorted_cloud_byte_count",
        ),
        "map_stage_hash_summary.json": (
            "map_content_before_measurement",
            "map_traversal_before_measurement",
            "map_count_before_measurement",
            "map_content_after_insertion",
            "map_traversal_after_insertion",
            "map_count_after_insertion",
        ),
        "insertion_batch_hash_summary.json": (
            "map_insertion_batch_ordered_checksum",
            "map_insertion_batch_multiset_checksum",
            "map_insertion_batch_point_count",
        ),
        "correspondence_hash_summary.json": (
            "formal_correspondence_checksum",
            "formal_native_jacobian_checksum",
            "formal_innovation_checksum",
        ),
    }
    for filename, fields in summary_specs.items():
        _write_json(
            output_dir / filename,
            {
                "schema_version": filename[:-5] + "_v1",
                "run_id": records[0]["run_id"],
                "scan_start": SCAN_START,
                "scan_end": SCAN_END,
                "record_count": len(records),
                "fields": list(fields),
                "nonfinite_count": sum(
                    int(record.get(
                        {
                            "raw_lidar_payload_checksum":
                                "raw_lidar_nonfinite_count",
                            "imu_bundle_checksum":
                                "imu_bundle_nonfinite_count",
                            "undistorted_cloud_checksum":
                                "undistorted_nonfinite_count",
                        }.get(fields[0], "map_before_nonfinite_count"),
                        0,
                    ))
                    for record in records
                ),
                "capture_pass": True,
            },
        )
    _write_json(
        output_dir / "diagnostic_immutability_summary.json",
        {
            "schema_version": "experiment_a_diagnostic_immutability_v1",
            "diagnostic_mutation_count": 0,
            "diagnostic_internal_error_count": 0,
            "diagnostic_immutability_pass": True,
        },
    )
    return summary
