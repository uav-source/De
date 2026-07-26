"""Offline semantic comparison for frozen Day 6 compact observations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Optional

from .frozen_observation import (
    FrozenObservationError,
    indexed_frames,
    load_existing_converter,
)
from .runtime_observation_v3 import validate_runtime_observation_v3


SEMANTIC_SCHEMA_VERSION = "SEMANTIC_OBSERVATION_V1"
SEMANTIC_FIELDS = (
    "scan_index",
    "timestamp_begin",
    "timestamp_end",
    "measurement_call_index",
    "prior_position_world",
    "prior_orientation_world_from_imu_xyzw",
    "prior_covariance_detector_order_raw",
    "prior_covariance_detector_order_symmetric",
    "measurement_variance_scalar_m2",
    "measurement_weight_representation",
    "valid_correspondence_count",
    "detector_pose_jacobian_rows",
    "formal_filter_innovation_h",
    "formal_native_jacobian_checksum",
    "detector_jacobian_checksum",
    "formal_innovation_checksum",
    "geometric_residual_checksum",
    "accepted_index_checksum",
    "formal_correspondence_checksum",
)
SEMANTIC_IDENTITY_EXCLUSIONS = (
    "run_id",
    "binary_record_checksum",
    "binary_record_self_checksum",
    "output_checksum",
    "created_at",
    "binary_offset",
    "process_id",
    "runtime_path",
)
PRIOR_FIELDS = (
    "prior_position_world",
    "prior_orientation_world_from_imu_xyzw",
    "prior_covariance_detector_order_raw",
    "prior_covariance_detector_order_symmetric",
)
MEASUREMENT_FIELDS = (
    "valid_correspondence_count",
    "detector_pose_jacobian_rows",
    "formal_filter_innovation_h",
    "formal_native_jacobian_checksum",
    "detector_jacobian_checksum",
    "formal_innovation_checksum",
    "geometric_residual_checksum",
    "accepted_index_checksum",
    "formal_correspondence_checksum",
)
DIVERGENCE_ORDER_CLASSES = {
    "PRIOR_STATE_ALREADY_DIVERGED",
    "MEASUREMENT_OR_CORRESPONDENCE_DIVERGED_WITH_EQUAL_PRIOR",
    "SAME_RECORD_ORDER_UNRESOLVED",
    "INSUFFICIENT_RECORD_GRANULARITY",
}
EVIDENCE_STATUSES = {
    "AVAILABLE_AND_VALIDATED",
    "CHECKSUM_ONLY",
    "NOT_RECORDED",
    "NOT_APPLICABLE",
}


class Day6SemanticError(ValueError):
    """Frozen semantic evidence violates the fail-closed audit contract."""


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_observation_records(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse and validate one frozen compact observation binary."""

    frames, integrity = indexed_frames(path)
    converter = load_existing_converter()
    records = [
        converter.decode_observation_record(
            converter.FramedRecord(frame.payload, frame.checksum)
        )
        for frame in frames
    ]
    if len(records) != 487:
        raise Day6SemanticError(
            f"expected 487 observations, found {len(records)}"
        )
    for expected, record in enumerate(records):
        try:
            validate_runtime_observation_v3(record)
        except ValueError as error:
            raise Day6SemanticError(
                f"record {expected} schema rejected: {error}"
            ) from error
        if int(record["scan_index"]) != expected + 3:
            raise Day6SemanticError("scan index is not the frozen 3..489 range")
        if int(record["measurement_call_index"]) < 0:
            raise Day6SemanticError("measurement call index is negative")
    if int(integrity["record_checksum_failure_count"]) != 0:
        raise Day6SemanticError("record checksum failure")
    if int(integrity["truncated_record_count"]) != 0:
        raise Day6SemanticError("truncated observation record")
    if int(integrity["extra_trailing_bytes"]) != 0:
        raise Day6SemanticError("extra trailing bytes")
    return records, integrity


def semantic_observation(
    record: Mapping[str, Any],
    record_index: int,
) -> dict[str, Any]:
    """Return only the formal numerical semantics authorized for comparison."""

    missing = [name for name in SEMANTIC_FIELDS if name not in record]
    if missing:
        raise Day6SemanticError(f"semantic fields missing: {missing}")
    value = {
        "schema_version": SEMANTIC_SCHEMA_VERSION,
        "record_index": int(record_index),
    }
    value.update({name: record[name] for name in SEMANTIC_FIELDS})
    if "map_size" in record:
        value["map_size"] = record["map_size"]
        value["map_size_observed"] = True
    else:
        value["map_size_observed"] = False
    value["semantic_observation_checksum"] = canonical_sha256(value)
    return value


def semantic_observation_checksum(
    record: Mapping[str, Any],
    record_index: int,
) -> str:
    return str(
        semantic_observation(record, record_index)[
            "semantic_observation_checksum"
        ]
    )


def differing_semantic_fields(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> list[str]:
    fields = [
        name for name in SEMANTIC_FIELDS if left[name] != right[name]
    ]
    left_has_map = "map_size" in left
    right_has_map = "map_size" in right
    if left_has_map != right_has_map:
        fields.append("map_size")
    elif left_has_map and left["map_size"] != right["map_size"]:
        fields.append("map_size")
    return fields


def compare_semantic_pair(
    *,
    pair: str,
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if len(left) != len(right):
        raise Day6SemanticError("pair length mismatch")
    rows = []
    for index, (left_record, right_record) in enumerate(zip(left, right)):
        left_semantic = semantic_observation(left_record, index)
        right_semantic = semantic_observation(right_record, index)
        differing = differing_semantic_fields(left_record, right_record)
        map_observed = "map_size" in left_record or "map_size" in right_record
        rows.append(
            {
                "pair": pair,
                "record_index": index,
                "scan_index": int(left_record["scan_index"]),
                "semantic_equal": not differing,
                "left_semantic_observation_checksum": left_semantic[
                    "semantic_observation_checksum"
                ],
                "right_semantic_observation_checksum": right_semantic[
                    "semantic_observation_checksum"
                ],
                "timestamp_equal": (
                    left_record["timestamp_begin"]
                    == right_record["timestamp_begin"]
                    and left_record["timestamp_end"]
                    == right_record["timestamp_end"]
                ),
                "prior_position_equal": (
                    left_record["prior_position_world"]
                    == right_record["prior_position_world"]
                ),
                "prior_orientation_equal": (
                    left_record["prior_orientation_world_from_imu_xyzw"]
                    == right_record["prior_orientation_world_from_imu_xyzw"]
                ),
                "prior_covariance_equal": (
                    left_record["prior_covariance_detector_order_raw"]
                    == right_record["prior_covariance_detector_order_raw"]
                    and left_record[
                        "prior_covariance_detector_order_symmetric"
                    ]
                    == right_record[
                        "prior_covariance_detector_order_symmetric"
                    ]
                ),
                "valid_correspondence_count_equal": (
                    left_record["valid_correspondence_count"]
                    == right_record["valid_correspondence_count"]
                ),
                "jacobian_equal": (
                    left_record["detector_pose_jacobian_rows"]
                    == right_record["detector_pose_jacobian_rows"]
                ),
                "innovation_equal": (
                    left_record["formal_filter_innovation_h"]
                    == right_record["formal_filter_innovation_h"]
                ),
                "native_jacobian_checksum_equal": (
                    left_record["formal_native_jacobian_checksum"]
                    == right_record["formal_native_jacobian_checksum"]
                ),
                "detector_jacobian_checksum_equal": (
                    left_record["detector_jacobian_checksum"]
                    == right_record["detector_jacobian_checksum"]
                ),
                "geometric_residual_checksum_equal": (
                    left_record["geometric_residual_checksum"]
                    == right_record["geometric_residual_checksum"]
                ),
                "accepted_index_checksum_equal": (
                    left_record["accepted_index_checksum"]
                    == right_record["accepted_index_checksum"]
                ),
                "formal_correspondence_checksum_equal": (
                    left_record["formal_correspondence_checksum"]
                    == right_record["formal_correspondence_checksum"]
                ),
                "map_size_equal_or_not_observed": (
                    (
                        left_record.get("map_size")
                        == right_record.get("map_size")
                    )
                    if map_observed
                    else "NOT_OBSERVED"
                ),
                "first_differing_field": differing[0] if differing else "",
                "all_differing_fields": differing,
            }
        )
    return rows


def first_divergence_by_field(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Optional[dict[str, int]]]:
    result: dict[str, Optional[dict[str, int]]] = {
        name: None for name in SEMANTIC_FIELDS + ("map_size",)
    }
    for row in rows:
        for field in row["all_differing_fields"]:
            if result[field] is None:
                result[field] = {
                    "record_index": int(row["record_index"]),
                    "scan_index": int(row["scan_index"]),
                }
    return result


def first_semantic_divergence(
    rows: Sequence[Mapping[str, Any]],
) -> Optional[dict[str, int]]:
    for row in rows:
        if not bool(row["semantic_equal"]):
            return {
                "record_index": int(row["record_index"]),
                "scan_index": int(row["scan_index"]),
            }
    return None


def previous_record_semantic_identity(
    rows: Sequence[Mapping[str, Any]],
) -> str:
    first = first_semantic_divergence(rows)
    if first is None:
        return "NOT_APPLICABLE_NO_DIVERGENCE"
    index = int(first["record_index"])
    if index == 0:
        return "NOT_OBSERVABLE_NO_PREVIOUS_RECORD"
    return "CONFIRMED" if bool(rows[index - 1]["semantic_equal"]) else "FALSE"


def classify_divergence_order(
    rows: Sequence[Mapping[str, Any]],
    *,
    arrays_observed: bool = True,
) -> str:
    first = first_semantic_divergence(rows)
    if first is None:
        return "INSUFFICIENT_RECORD_GRANULARITY"
    row = rows[int(first["record_index"])]
    differing = set(row["all_differing_fields"])
    prior_differs = bool(differing.intersection(PRIOR_FIELDS))
    measurement_differs = bool(differing.intersection(MEASUREMENT_FIELDS))
    if prior_differs and not measurement_differs:
        value = "PRIOR_STATE_ALREADY_DIVERGED"
    elif measurement_differs and not prior_differs:
        if not arrays_observed and differing.issubset(
            {
                "accepted_index_checksum",
                "formal_correspondence_checksum",
            }
        ):
            value = "INSUFFICIENT_RECORD_GRANULARITY"
        else:
            value = (
                "MEASUREMENT_OR_CORRESPONDENCE_DIVERGED_WITH_EQUAL_PRIOR"
            )
    elif prior_differs and measurement_differs:
        value = "SAME_RECORD_ORDER_UNRESOLVED"
    else:
        value = "INSUFFICIENT_RECORD_GRANULARITY"
    if value not in DIVERGENCE_ORDER_CLASSES:
        raise Day6SemanticError("invalid divergence order classification")
    return value


def evidence_granularity_matrix(
    sample_record: Mapping[str, Any],
) -> list[dict[str, str]]:
    """Describe only what is actually present in the frozen compact schema."""

    rows = [
        (
            "raw_lidar_payload_checksum",
            "NOT_RECORDED",
            "No raw LiDAR payload digest field is present.",
        ),
        (
            "raw_imu_bundle_checksum",
            "NOT_RECORDED",
            "No raw IMU bundle digest field is present.",
        ),
        (
            "undistorted_point_cloud_checksum",
            "NOT_RECORDED",
            "No undistorted-cloud digest field is present.",
        ),
        (
            "map_content_checksum",
            "NOT_RECORDED",
            "No complete map-content digest field is present.",
        ),
        (
            "map_insertion_order_checksum",
            "NOT_RECORDED",
            "No insertion-order digest field is present.",
        ),
        (
            "full_accepted_index_array",
            (
                "CHECKSUM_ONLY"
                if "accepted_index_checksum" in sample_record
                else "NOT_RECORDED"
            ),
            "Only the accepted-index checksum is retained.",
        ),
        (
            "full_plane_parameter_array",
            (
                "CHECKSUM_ONLY"
                if "formal_correspondence_checksum" in sample_record
                else "NOT_RECORDED"
            ),
            "Only the aggregate formal-correspondence checksum is retained.",
        ),
        (
            "full_nearest_neighbor_identity_array",
            "NOT_RECORDED",
            "Nearest-neighbor identities are not retained.",
        ),
        (
            "openmp_scheduling_trace",
            "NOT_RECORDED",
            "No scheduling trace is retained.",
        ),
        (
            "thread_identity_trace",
            "NOT_RECORDED",
            "No per-operation thread trace is retained.",
        ),
        (
            "map_size",
            (
                "AVAILABLE_AND_VALIDATED"
                if "map_size" in sample_record
                else "NOT_RECORDED"
            ),
            "Compact records do not expose map size in this archive.",
        ),
    ]
    result = []
    for evidence, status, limitation in rows:
        if status not in EVIDENCE_STATUSES:
            raise Day6SemanticError(f"invalid evidence status: {status}")
        result.append(
            {
                "evidence": evidence,
                "status": status,
                "limitation": limitation,
            }
        )
    return result


def validate_checksum_only_claim(
    status: str,
    claim_level: str,
) -> None:
    if status == "CHECKSUM_ONLY" and claim_level == "ARRAY_ELEMENT_IDENTITY":
        raise Day6SemanticError(
            "checksum-only evidence cannot support array-element identity"
        )


def validate_record_index_file(path: Path) -> dict[str, Any]:
    import csv

    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    indices = [int(row["record_index"]) for row in rows]
    scans = [int(row["scan_index"]) for row in rows]
    passed = indices == list(range(487)) and scans == list(range(3, 490))
    if not passed:
        raise FrozenObservationError("record index identity failed")
    return {
        "record_index_row_count": len(rows),
        "first_record_index": indices[0],
        "last_record_index": indices[-1],
        "first_scan_index": scans[0],
        "last_scan_index": scans[-1],
        "record_index_pass": True,
    }
