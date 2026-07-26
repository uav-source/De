"""Read-only validation and indexing for a frozen real observation binary."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import struct
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .runtime_observation_v3 import validate_runtime_observation_v3


SCHEMA_VERSION = "frozen_real_observation_conversion_v1"
RECORD_SCHEMA_VERSION = "readonly_observation_v3"
RECORD_SOURCE = "FASTLIO2_RUNTIME_COMPACT_BINARY"
PAYLOAD_PROFILE = "DETECTOR_MINIMAL_V1"
BINARY_MAGIC = b"HBROBSV3"
BINARY_VERSION = 3
TRAILER_MAGIC = b"HBRENDV1"
HEADER_SIZE = 16
TRAILER_SIZE = 24
CHECKSUM_ALGORITHM = "FNV1A64_EXACT_BYTES_V1"
FORBIDDEN_TOKENS = (
    "pose_gt",
    "axis_gt",
    "oracle",
    "ground_truth",
    "scene_label",
    "harmful_label",
    "future",
    "holdout",
    "reserved_test",
    "trajectory_error",
    "odi",
    "ais",
    "weak_direction",
    "degeneracy_triggered",
    "detector_output",
    "candidate_offsets",
    "candidate_costs",
    "imu_conflict",
)
FORBIDDEN_TOPIC_TOKENS = (
    "ground_truth",
    "groundtruth",
    "pose_gt",
    "mocap",
    "vicon",
    "truth",
    "oracle",
)


class FrozenObservationError(ValueError):
    """The frozen observation evidence violates a fail-closed contract."""


@dataclass(frozen=True)
class IndexedFrame:
    payload: bytes
    checksum: int
    frame_offset: int
    payload_offset: int
    payload_length: int
    frame_length: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_existing_converter(root: Path | None = None) -> Any:
    repository = root or Path(__file__).resolve().parents[2]
    path = repository / "scripts/46_convert_fastlio2_runtime_binary.py"
    spec = importlib.util.spec_from_file_location(
        "frozen_observation_existing_converter", path
    )
    if spec is None or spec.loader is None:
        raise FrozenObservationError("existing compact binary converter missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def indexed_frames(path: Path) -> tuple[list[IndexedFrame], dict[str, Any]]:
    converter = load_existing_converter()
    try:
        records, integrity = converter.read_framed_binary(
            path, magic=BINARY_MAGIC, version=BINARY_VERSION
        )
    except converter.BinaryFormatError as error:
        raise FrozenObservationError(str(error)) from error
    data = path.read_bytes()
    trailer_offset = len(data) - TRAILER_SIZE
    frames: list[IndexedFrame] = []
    offset = HEADER_SIZE
    for record in records:
        frame_offset = offset
        (payload_length,) = struct.unpack_from("<I", data, offset)
        payload_offset = offset + 4
        offset = payload_offset + payload_length + 8
        frames.append(
            IndexedFrame(
                payload=record.payload,
                checksum=record.checksum,
                frame_offset=frame_offset,
                payload_offset=payload_offset,
                payload_length=payload_length,
                frame_length=4 + payload_length + 8,
            )
        )
    if offset != trailer_offset:
        raise FrozenObservationError("indexed frames do not end at trailer")
    integrity = dict(integrity)
    integrity.update(
        {
            "binary_size_bytes": len(data),
            "binary_sha256": sha256_file(path),
            "header_size_bytes": HEADER_SIZE,
            "trailer_size_bytes": TRAILER_SIZE,
            "trailer_offset": trailer_offset,
            "binary_header_pass": True,
            "binary_record_checksums_pass": True,
            "binary_trailer_pass": True,
            "binary_file_checksum_pass": True,
            "extra_trailing_bytes": 0,
        }
    )
    return frames, integrity


def forbidden_field_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for raw_name, child in value.items():
            name = str(raw_name)
            lowered = name.lower()
            if any(token in lowered for token in FORBIDDEN_TOKENS):
                found.append(f"{path}.{name}")
            found.extend(forbidden_field_paths(child, f"{path}.{name}"))
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, child in enumerate(value):
            found.extend(forbidden_field_paths(child, f"{path}[{index}]"))
    return found


def forbidden_topic_count(texts: Sequence[str]) -> int:
    count = 0
    for text in texts:
        lowered = text.lower()
        for line in lowered.splitlines():
            if any(token in line for token in FORBIDDEN_TOPIC_TOKENS):
                count += 1
    return count


def validate_record_index(
    rows: Sequence[Mapping[str, Any]],
    *,
    binary_size: int,
    trailer_offset: int,
) -> dict[str, Any]:
    invalid_offset_count = 0
    duplicate_offset_count = 0
    duplicate_record_count = 0
    duplicate_scan_first_valid_count = 0
    offsets: set[int] = set()
    record_ids: set[tuple[int, int]] = set()
    scans: set[int] = set()
    previous_end = HEADER_SIZE
    previous_scan: int | None = None
    for expected, row in enumerate(rows):
        if int(row["record_index"]) != expected:
            raise FrozenObservationError("record index is not contiguous")
        offset = int(row["binary_offset"])
        length = int(row["binary_record_length"])
        if offset in offsets:
            duplicate_offset_count += 1
        offsets.add(offset)
        if offset != previous_end or length <= 12 or offset + length > trailer_offset:
            invalid_offset_count += 1
        previous_end = offset + length
        scan = int(row["scan_index"])
        call = int(row["measurement_call_index"])
        identity = (scan, call)
        if identity in record_ids:
            duplicate_record_count += 1
        record_ids.add(identity)
        if scan in scans:
            duplicate_scan_first_valid_count += 1
        scans.add(scan)
        if previous_scan is not None and scan <= previous_scan:
            raise FrozenObservationError("scan index is not strictly increasing")
        previous_scan = scan
    if previous_end != trailer_offset or trailer_offset + TRAILER_SIZE != binary_size:
        invalid_offset_count += 1
    result = {
        "record_index_row_count": len(rows),
        "record_index_contiguous": True,
        "scan_index_strictly_increasing": True,
        "duplicate_record_count": duplicate_record_count,
        "duplicate_binary_offset_count": duplicate_offset_count,
        "duplicate_scan_first_valid_count": duplicate_scan_first_valid_count,
        "invalid_offset_count": invalid_offset_count,
        "record_index_pass": (
            duplicate_record_count == 0
            and duplicate_offset_count == 0
            and duplicate_scan_first_valid_count == 0
            and invalid_offset_count == 0
        ),
    }
    if not result["record_index_pass"]:
        raise FrozenObservationError("record index integrity failed")
    return result


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_index(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise FrozenObservationError("cannot freeze an empty observation set")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def convert_frozen_set(
    *,
    observation_binary: Path,
    runtime_binary: Path,
    output_dir: Path,
    endpoint_contract_sha256: str,
    expected_run_id: str,
    expected_sequence_id: str,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FrozenObservationError(f"conversion output exists: {output_dir}")
    converter = load_existing_converter()
    frames, binary = indexed_frames(observation_binary)
    try:
        runtime_records, runtime_integrity = converter.read_framed_binary(
            runtime_binary,
            magic=converter.RUNTIME_MAGIC,
            version=converter.RUNTIME_VERSION,
        )
    except converter.BinaryFormatError as error:
        raise FrozenObservationError(str(error)) from error
    observations = [
        converter.decode_observation_record(
            converter.FramedRecord(frame.payload, frame.checksum)
        )
        for frame in frames
    ]
    runtime_rows = [
        converter.decode_runtime_record(record) for record in runtime_records
    ]
    if not observations:
        raise FrozenObservationError("observation binary contains no records")

    index_rows: list[dict[str, Any]] = []
    schema_rejected = 0
    nonfinite = 0
    forbidden_count = 0
    for index, (record, frame) in enumerate(zip(observations, frames)):
        try:
            validate_runtime_observation_v3(record)
        except ValueError as error:
            schema_rejected += 1
            raise FrozenObservationError(
                f"record {index} schema rejected: {error}"
            ) from error
        if record["run_id"] != expected_run_id:
            raise FrozenObservationError("observation run_id mismatch")
        if record["sequence_id"] != expected_sequence_id:
            raise FrozenObservationError("observation sequence_id mismatch")
        forbidden = forbidden_field_paths(record)
        forbidden_count += len(forbidden)
        if forbidden:
            raise FrozenObservationError(
                f"record {index} contains forbidden fields: {forbidden}"
            )
        numeric_values = (
            list(record["prior_position_world"])
            + list(record["prior_orientation_world_from_imu_xyzw"])
            + [
                value
                for row in record["prior_covariance_detector_order_raw"]
                for value in row
            ]
            + [
                value
                for row in record["detector_pose_jacobian_rows"]
                for value in row
            ]
            + list(record["formal_filter_innovation_h"])
        )
        if not all(math.isfinite(float(value)) for value in numeric_values):
            nonfinite += 1
            raise FrozenObservationError(f"record {index} is nonfinite")
        jacobian = record["detector_pose_jacobian_rows"]
        index_rows.append(
            {
                "record_index": index,
                "scan_index": record["scan_index"],
                "timestamp_begin": repr(record["timestamp_begin"]),
                "timestamp_end": repr(record["timestamp_end"]),
                "measurement_call_index": record["measurement_call_index"],
                "valid_correspondence_count": record[
                    "valid_correspondence_count"
                ],
                "jacobian_row_count": len(jacobian),
                "jacobian_column_count": 6,
                "binary_offset": frame.frame_offset,
                "binary_record_length": frame.frame_length,
                "binary_record_checksum": frame.checksum,
                "prior_covariance_raw_checksum": record[
                    "prior_covariance_raw_checksum"
                ],
                "formal_native_jacobian_checksum": record[
                    "formal_native_jacobian_checksum"
                ],
                "detector_jacobian_checksum": record[
                    "detector_jacobian_checksum"
                ],
                "formal_innovation_checksum": record[
                    "formal_innovation_checksum"
                ],
                "geometric_residual_checksum": record[
                    "geometric_residual_checksum"
                ],
                "accepted_index_checksum": record[
                    "accepted_index_checksum"
                ],
                "formal_correspondence_checksum": record[
                    "formal_correspondence_checksum"
                ],
                "schema_validation_pass": "true",
                "finite_validation_pass": "true",
                "no_gt_validation_pass": "true",
            }
        )

    index_validation = validate_record_index(
        index_rows,
        binary_size=int(binary["binary_size_bytes"]),
        trailer_offset=int(binary["trailer_offset"]),
    )
    runtime_scan_indices = [int(row["scan_index"]) for row in runtime_rows]
    if len(runtime_scan_indices) != len(set(runtime_scan_indices)):
        raise FrozenObservationError("runtime lifecycle has duplicate scan indices")
    first_valid = [
        row for row in runtime_rows if row["first_valid_linearization_found"]
    ]
    observed_scans = {int(row["scan_index"]) for row in index_rows}
    first_valid_scans = {int(row["scan_index"]) for row in first_valid}
    missing_lifecycle = len(observed_scans - set(runtime_scan_indices))
    lifecycle_gap = len(first_valid_scans.symmetric_difference(observed_scans))
    skip_counts = Counter(
        str(row["skip_reason"])
        for row in runtime_rows
        if not row["first_valid_linearization_found"]
    )
    lifecycle = {
        "schema_version": "frozen_observation_lifecycle_summary_v1",
        "runtime_scan_count": len(runtime_rows),
        "first_valid_linearization_count": len(first_valid),
        "observation_record_count": len(observations),
        "skipped_scan_count": len(runtime_rows) - len(first_valid),
        "skip_reason_counts": dict(sorted(skip_counts.items())),
        "lifecycle_gap_count": lifecycle_gap,
        "observation_scan_not_found_count": missing_lifecycle,
        "duplicate_scan_first_valid_count": index_validation[
            "duplicate_scan_first_valid_count"
        ],
        "lifecycle_consistency_pass": (
            len(observations) == len(first_valid)
            and lifecycle_gap == 0
            and missing_lifecycle == 0
        ),
    }
    if not lifecycle["lifecycle_consistency_pass"]:
        raise FrozenObservationError("observation/runtime lifecycle mismatch")

    output_dir.mkdir(parents=True)
    index_path = output_dir / "record_index.csv"
    _write_index(index_path, index_rows)
    manifest = {
        "schema_version": "frozen_observation_record_manifest_v1",
        "record_schema_version": RECORD_SCHEMA_VERSION,
        "record_source": RECORD_SOURCE,
        "payload_profile": PAYLOAD_PROFILE,
        "source_commit": observations[0]["fastlio2_commit"],
        "fastlio2_binary_sha256": observations[0]["fastlio2_binary_sha256"],
        "clip_sha256": observations[0]["bag_sha256"],
        "endpoint_contract_sha256": endpoint_contract_sha256,
        "adapter_contract_version": observations[0][
            "adapter_contract_version"
        ],
        "observation_record_count": len(observations),
        "record_index_sha256": sha256_file(index_path),
        "binary_sha256": binary["binary_sha256"],
        "binary_size_bytes": binary["binary_size_bytes"],
        "first_scan_index": index_rows[0]["scan_index"],
        "last_scan_index": index_rows[-1]["scan_index"],
        **index_validation,
    }
    schema_summary = {
        "schema_version": "frozen_observation_schema_validation_summary_v1",
        "record_schema_version": RECORD_SCHEMA_VERSION,
        "schema_accepted_record_count": len(observations),
        "schema_rejected_record_count": schema_rejected,
        "nonfinite_record_count": nonfinite,
        "forbidden_field_count": forbidden_count,
        "all_quaternions_valid": True,
        "all_covariance_relationships_valid": True,
        "all_jacobian_shapes_valid": True,
        "schema_validation_pass": True,
    }
    no_gt = {
        "schema_version": "frozen_observation_no_gt_audit_v1",
        "scanned_record_count": len(observations),
        "forbidden_field_count": forbidden_count,
        "gt_topic_consumed_count": 0,
        "contains_gt": False,
        "contains_future_information": False,
        "contains_holdout_information": False,
        "no_gt_pass": True,
    }
    binary_summary = {
        "schema_version": "frozen_observation_binary_validation_v1",
        **binary,
        "binary_magic": BINARY_MAGIC.decode("ascii"),
        "binary_version": BINARY_VERSION,
        "checksum_algorithm": CHECKSUM_ALGORITHM,
        "binary_checksum_failure_count": 0,
        "truncated_record_count": 0,
        "runtime_binary_record_count": len(runtime_records),
        "runtime_binary_integrity_pass": bool(
            runtime_integrity["file_checksum_valid"]
            and runtime_integrity["trailer_valid"]
        ),
        "binary_integrity_pass": True,
    }
    _write_json(output_dir / "record_manifest.json", manifest)
    _write_json(output_dir / "schema_validation_summary.json", schema_summary)
    _write_json(output_dir / "no_gt_audit.json", no_gt)
    _write_json(output_dir / "binary_validation_summary.json", binary_summary)
    _write_json(output_dir / "lifecycle_summary.json", lifecycle)
    return {
        "schema_version": SCHEMA_VERSION,
        "record_manifest": manifest,
        "schema_validation": schema_summary,
        "no_gt": no_gt,
        "binary_validation": binary_summary,
        "lifecycle": lifecycle,
    }


REQUIRED_GATE_FIELDS = (
    "COMPACT_EXPORT_CAPABILITY_CONFIRMED",
    "SOURCE_PROVENANCE_PASS",
    "RUN_COMPLETENESS_PASS",
    "BINARY_INTEGRITY_PASS",
    "RECORD_COUNT_CONSISTENCY_PASS",
    "RECORD_INDEX_PASS",
    "SCHEMA_VALIDATION_PASS",
    "LIFECYCLE_CONSISTENCY_PASS",
    "NO_GT_PASS",
    "IN_CALL_IMMUTABILITY_RECONFIRMED",
    "NO_DROP_PASS",
    "FREEZE_REPRODUCIBILITY_PASS",
    "FREEZE_ROUNDTRIP_PASS",
    "DIFF_SCOPE_PASS",
)
REMEDIATION_REQUIRED_GATE_FIELDS = (
    "CORE_OBSERVATION_DATA_INTEGRITY_PASS",
    "CONTENT_ABSOLUTE_PATH_SCAN_PASS",
    "ARCHIVE_MODE_NORMALIZATION_PASS",
    "FREEZE_REPRODUCIBILITY_PASS",
    "FREEZE_ROUNDTRIP_PASS",
    "FREEZE_ARCHIVE_PROTOCOL_PASS",
    "DIFF_SCOPE_PASS",
    "MAIN_AUDIT_CONTENT_PATH_PASS",
    "MAIN_AUDIT_MODE_PASS",
    "AUDIT_PACKAGE_SCOPE_PASS",
    "AUDIT_INTERNAL_HASH_PASS",
)
CORE_OBSERVATION_INVARIANT_FIELDS = (
    "core_binary_sha256",
    "binary_size_bytes",
    "observation_record_count",
    "binary_trailer_count",
    "record_index_sha256",
    "record_index_row_count",
    "scan_index_sequence_sha256",
    "binary_offset_sequence_sha256",
    "runtime_scan_count",
    "skipped_scan_count",
    "schema_rejected_record_count",
    "nonfinite_record_count",
    "forbidden_field_count",
    "gt_topic_consumed_count",
    "tap_drop_count",
    "writer_error_count",
    "binary_checksum_failure_count",
    "truncated_record_count",
)


def validate_core_observation_integrity(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, Any]:
    mismatches = [
        {
            "field": field,
            "before": before.get(field),
            "after": after.get(field),
        }
        for field in CORE_OBSERVATION_INVARIANT_FIELDS
        if before.get(field) != after.get(field)
    ]
    return {
        "checked_field_count": len(CORE_OBSERVATION_INVARIANT_FIELDS),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "core_observation_data_integrity_pass": not mismatches,
    }


def evaluate_remediation_gate(
    facts: Mapping[str, Any],
) -> dict[str, bool]:
    gates = {
        name: bool(facts.get(name, False))
        for name in REMEDIATION_REQUIRED_GATE_FIELDS
    }
    execution_boundary_pass = all(
        facts.get(name) is False
        for name in (
            "fastlio2_modified",
            "fastlio2_build_run",
            "fastlio2_test_run",
            "fastlio2_node_run",
            "roscore_run",
            "roslaunch_run",
            "rosbag_run",
            "real_data_reprocessed",
            "detector_called",
            "odi_computed",
            "weak_direction_computed",
            "development_run",
            "holdout_run",
            "future_test_run",
            "commit_created",
            "push_performed",
        )
    )
    final = all(gates.values()) and execution_boundary_pass
    gates.update(
        {
            "FROZEN_REAL_OBSERVATION_RECORD_PASS": final,
            "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_AUTHORIZED": final,
            "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED": False,
            "REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE_AUTHORIZED": False,
        }
    )
    return gates


def evaluate_freeze_gate(facts: Mapping[str, Any]) -> dict[str, bool]:
    gates = {name: bool(facts.get(name, False)) for name in REQUIRED_GATE_FIELDS}
    counts_pass = all(
        int(facts.get(name, -1)) == 0
        for name in (
            "schema_rejected_record_count",
            "nonfinite_record_count",
            "forbidden_field_count",
            "gt_topic_consumed_count",
            "tap_drop_count",
            "writer_error_count",
            "binary_checksum_failure_count",
            "truncated_record_count",
            "in_call_mutation_count",
        )
    )
    execution_boundary_pass = all(
        facts.get(name) is False
        for name in (
            "detector_called",
            "odi_computed",
            "development_run",
            "holdout_run",
            "future_test_run",
            "commit_created",
            "push_performed",
        )
    )
    final = (
        all(gates.values())
        and int(facts.get("observation_record_count", 0)) > 0
        and counts_pass
        and execution_boundary_pass
    )
    gates.update(
        {
            "FROZEN_REAL_OBSERVATION_RECORD_PASS": final,
            "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_AUTHORIZED": final,
            "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED": False,
            "REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE_AUTHORIZED": False,
        }
    )
    return gates


def validate_freeze_manifest(value: Mapping[str, Any]) -> None:
    required = {
        "schema_version",
        "artifact_name",
        "artifact_version",
        "run_id",
        "sequence_id",
        "scientific_label_status",
        "eligible_as_ground_truth_label",
        "eligible_for_auroc_label",
        "holdout_or_test",
        "redistribution_authorized",
        "observation_record_count",
        "binary_sha256",
        "record_index_sha256",
        *REQUIRED_GATE_FIELDS,
        "FROZEN_REAL_OBSERVATION_RECORD_PASS",
        "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_AUTHORIZED",
        "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED",
    }
    missing = sorted(required - set(value))
    if missing:
        raise FrozenObservationError(f"freeze manifest missing fields: {missing}")
    if value["scientific_label_status"] != "UNVERIFIED":
        raise FrozenObservationError("scientific label status must be UNVERIFIED")
    for field in (
        "eligible_as_ground_truth_label",
        "eligible_for_auroc_label",
        "holdout_or_test",
        "redistribution_authorized",
        "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED",
    ):
        if value[field] is not False:
            raise FrozenObservationError(f"{field} must remain false")
    if int(value["observation_record_count"]) <= 0:
        raise FrozenObservationError("freeze manifest record count must be positive")
    if value.get("remediation_type") is not None:
        if value["remediation_type"] != "OFFLINE_ARCHIVE_PROTOCOL_FIX":
            raise FrozenObservationError("unexpected remediation type")
        if value.get("core_observation_binary_unchanged") is not True:
            raise FrozenObservationError(
                "remediation must preserve the observation binary"
            )
