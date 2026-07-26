"""Load and validate bounded Day 7 mutation traces."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any, Iterable, Mapping

from .day7_map_point_identity import (
    SHA256_RE,
    load_snapshot_sets,
    validate_snapshot_binary,
)


EXPECTED_SCAN_START = 150
EXPECTED_SCAN_END = 170
MAX_EVENT_COUNT = 131072
MUTATION_MAGIC = b"D7MUTV1\x00"
LOGGER_MAGIC = b"D7LOGV1\x00"

OUTCOMES = {
    "INSERTED_NEW_VOXEL_REPRESENTATIVE",
    "REPLACED_EXISTING_VOXEL_REPRESENTATIVE",
    "REINSERTED_EXISTING_VOXEL_REPRESENTATIVE",
    "REJECTED_EXISTING_REPRESENTATIVE_CLOSER",
    "ADDED_WITHOUT_DOWNSAMPLING",
    "DELETED_BY_BOX",
    "DELETE_BOX_NO_MATCH",
}
OUTCOME_ENUMS = {
    "INSERTED_NEW_VOXEL_REPRESENTATIVE": 1,
    "REPLACED_EXISTING_VOXEL_REPRESENTATIVE": 2,
    "REINSERTED_EXISTING_VOXEL_REPRESENTATIVE": 3,
    "REJECTED_EXISTING_REPRESENTATIVE_CLOSER": 4,
    "ADDED_WITHOUT_DOWNSAMPLING": 5,
    "DELETED_BY_BOX": 6,
    "DELETE_BOX_NO_MATCH": 7,
    "UNCLASSIFIED_FORMAL_PATH": 255,
}
DESTINATION_ENUMS = {
    "NONE": 0,
    "DIRECT_TREE": 1,
    "REBUILD_LOGGER": 2,
    "BOTH": 3,
}
FNV_OFFSET = 14695981039346656037
FNV_PRIME = 1099511628211


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_sidecar(path: Path) -> str:
    sidecar = path.with_name(path.name + ".sha256")
    fields = sidecar.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[1] != path.name:
        raise ValueError(f"invalid SHA sidecar: {sidecar}")
    actual = sha256_file(path)
    if fields[0] != actual:
        raise ValueError(f"binary SHA mismatch: {path}")
    return actual


def validate_fixed_binary(path: Path, expected_magic: bytes) -> dict[str, Any]:
    validate_sidecar(path)
    payload = path.read_bytes()
    if len(payload) < 40 or payload[:8] != expected_magic:
        raise ValueError(f"binary header mismatch: {path}")
    version, record_size, record_count = struct.unpack_from("<IIQ", payload, 8)
    expected_size = 8 + 4 + 4 + 8 + record_size * record_count + 8 + 8
    if version != 1 or len(payload) != expected_size:
        raise ValueError(f"binary framing mismatch: {path}")
    if payload[-16:-8] != b"D7TRAIL1":
        raise ValueError(f"binary trailer mismatch: {path}")
    if struct.unpack_from("<Q", payload, len(payload) - 8)[0] != record_count:
        raise ValueError(f"binary trailer count mismatch: {path}")
    return {
        "path": str(path),
        "record_size": record_size,
        "record_count": record_count,
        "sha256": sha256_file(path),
    }


def _integer(row: Mapping[str, str], name: str) -> int:
    try:
        return int(row[name])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"invalid integer field: {name}") from error


def _fnv_append(checksum: int, payload: bytes) -> int:
    for byte in payload:
        checksum ^= byte
        checksum = (checksum * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return checksum


def _u64(value: int) -> bytes:
    return (value & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "big")


def _u32(value: int) -> bytes:
    return (value & 0xFFFFFFFF).to_bytes(4, "big")


def _identity_bytes(value: str) -> bytes:
    return bytes.fromhex(value) if value else bytes(32)


def _voxel_words(value: str) -> tuple[int, ...]:
    if not value:
        return (0, 0, 0, 0, 0, 0)
    if len(value) != 48 or re.fullmatch(r"[0-9a-f]{48}", value) is None:
        raise ValueError("invalid VoxelIdentityV1")
    return tuple(int(value[offset:offset + 8], 16)
                 for offset in range(0, 48, 8))


def mutation_event_checksum(event: Mapping[str, Any]) -> int:
    checksum = FNV_OFFSET
    checksum = _fnv_append(checksum, _u64(int(event["scan_index"])))
    checksum = _fnv_append(checksum, _u32(int(event["call_index"])))
    checksum = _fnv_append(
        checksum, _u32(int(event["batch_point_index"]))
    )
    checksum = _fnv_append(
        checksum, _u32(int(event["event_index_within_call"]))
    )
    checksum = _fnv_append(
        checksum, _identity_bytes(str(event["candidate_point_sha256"]))
    )
    for word in _voxel_words(str(event["voxel_identity"])):
        checksum = _fnv_append(checksum, _u32(word))
    checksum = _fnv_append(
        checksum,
        _identity_bytes(str(event["existing_representative_sha256"])),
    )
    checksum = _fnv_append(
        checksum,
        _identity_bytes(str(event["selected_representative_sha256"])),
    )
    checksum = _fnv_append(
        checksum, _u64(int(event["decision_context_ordered_checksum"]))
    )
    checksum = _fnv_append(
        checksum, _u64(int(event["decision_context_multiset_checksum"]))
    )
    checksum = _fnv_append(
        checksum, _u64(int(event["logical_point_count_delta_claimed"]))
    )
    checksum = _fnv_append(
        checksum, _u64(int(event["logger_entry_sequence"]))
    )
    try:
        outcome = OUTCOME_ENUMS[str(event["formal_outcome"])]
        destination = DESTINATION_ENUMS[str(event["mutation_destination"])]
    except KeyError as error:
        raise ValueError("event enum cannot be checksummed") from error
    return _fnv_append(
        checksum,
        bytes((
            int(event["operation_type"]),
            destination,
            outcome,
            int(event["downsample_enabled"]),
        )),
    )


def load_events(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
    required = {
        "schema_version",
        "run_id",
        "event_sequence",
        "scan_index",
        "call_index",
        "batch_id",
        "batch_kind",
        "batch_point_index",
        "event_index_within_call",
        "operation_type",
        "formal_callsite",
        "candidate_point_sha256",
        "voxel_identity",
        "existing_representative_sha256",
        "selected_representative_sha256",
        "downsample_enabled",
        "decision_context_member_count",
        "decision_context_ordered_checksum",
        "decision_context_multiset_checksum",
        "formal_outcome",
        "mutation_destination",
        "rebuild_active_at_decision",
        "rebuild_generation",
        "logical_mutation_epoch",
        "logical_point_count_delta_claimed",
        "logger_entry_sequence",
        "event_schema_pass",
        "diagnostic_internal_error",
        "event_checksum",
    }
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError("mutation event index schema mismatch")
    if not 0 < len(rows) <= MAX_EVENT_COUNT:
        raise ValueError("mutation event count outside bounded contract")
    result: list[dict[str, Any]] = []
    previous_sequence = 0
    for row in rows:
        event = dict(row)
        for name in (
            "event_sequence",
            "scan_index",
            "call_index",
            "batch_point_index",
            "event_index_within_call",
            "operation_type",
            "downsample_enabled",
            "decision_context_member_count",
            "decision_context_ordered_checksum",
            "decision_context_multiset_checksum",
            "rebuild_active_at_decision",
            "rebuild_generation",
            "logical_mutation_epoch",
            "logical_point_count_delta_claimed",
            "logger_entry_sequence",
            "event_schema_pass",
            "diagnostic_internal_error",
            "event_checksum",
        ):
            event[name] = _integer(row, name)
        if event["event_sequence"] <= previous_sequence:
            raise ValueError("mutation event sequence is not increasing")
        previous_sequence = event["event_sequence"]
        if not EXPECTED_SCAN_START <= event["scan_index"] <= EXPECTED_SCAN_END:
            raise ValueError("mutation event outside Day 7 window")
        for name in (
            "candidate_point_sha256",
            "existing_representative_sha256",
            "selected_representative_sha256",
        ):
            if event[name] and SHA256_RE.fullmatch(event[name]) is None:
                raise ValueError(f"invalid point SHA field: {name}")
        if event["formal_outcome"] not in OUTCOMES:
            raise ValueError("unclassified or unknown formal outcome")
        if event["mutation_destination"] not in DESTINATION_ENUMS:
            raise ValueError("unknown mutation destination")
        if event["schema_version"] != "Day7MapMutationEventV1":
            raise ValueError("mutation event schema version mismatch")
        if not event["run_id"]:
            raise ValueError("mutation event run id missing")
        if event["batch_id"] != (
            f"{event['scan_index']}:{event['call_index']}"
        ):
            raise ValueError("mutation event batch identity mismatch")
        if event["event_schema_pass"] != 1:
            raise ValueError("event schema failure")
        if event["diagnostic_internal_error"] != 0:
            raise ValueError("event diagnostic internal error")
        if mutation_event_checksum(event) != event["event_checksum"]:
            raise ValueError("mutation event checksum mismatch")
        result.append(event)
    return result


def load_call_summaries(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    result: list[dict[str, Any]] = []
    for row in rows:
        value: dict[str, Any] = dict(row)
        for name in (
            "scan_index",
            "call_index",
            "input_point_count",
            "map_count_before",
            "map_count_after",
            "event_count",
            "expected_logical_count_delta",
            "observed_logical_count_delta",
            "delta_accounting_pass",
        ):
            value[name] = _integer(row, name)
        result.append(value)
    return result


def materialize_delta_accounting(
    run_dir: Path,
) -> dict[str, Any]:
    calls = load_call_summaries(
        run_dir / "day7_map_mutation_call_summaries.csv"
    )
    failures = [
        row for row in calls
        if row["delta_accounting_pass"] != 1
        or row["expected_logical_count_delta"]
        != row["observed_logical_count_delta"]
    ]
    output_csv = run_dir / "map_mutation_delta_accounting.csv"
    with output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "scan_index",
                "call_index",
                "batch_kind",
                "map_count_before",
                "map_count_after",
                "expected_logical_count_delta",
                "observed_logical_count_delta",
                "delta_accounting_pass",
            ),
        )
        writer.writeheader()
        for row in calls:
            writer.writerow({name: row[name] for name in writer.fieldnames})
    summary = {
        "schema_version": "day7_map_mutation_delta_accounting_v1",
        "call_count": len(calls),
        "failure_count": len(failures),
        "unexplained_map_count_delta_count": len(failures),
        "map_delta_accounting_pass": not failures,
    }
    (run_dir / "map_mutation_delta_accounting_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def validate_run_trace(run_dir: Path) -> dict[str, Any]:
    from .day7_rebuild_logger_analysis import load_logger_events

    mutation = validate_fixed_binary(
        run_dir / "day7_map_mutation_events_v1.bin", MUTATION_MAGIC
    )
    logger = validate_fixed_binary(
        run_dir / "day7_rebuild_logger_events_v1.bin", LOGGER_MAGIC
    )
    events = load_events(run_dir / "day7_map_mutation_event_index.csv")
    calls = load_call_summaries(
        run_dir / "day7_map_mutation_call_summaries.csv"
    )
    snapshots = load_snapshot_sets(
        run_dir / "map_point_identity_snapshot_hashes.csv"
    )
    snapshot_binary = validate_snapshot_binary(
        run_dir / "map_point_identity_snapshots_v1.bin",
        run_dir / "map_point_identity_snapshot_index.csv",
        run_dir / "map_point_identity_snapshot_hashes.csv",
    )
    logger_rows = load_logger_events(
        run_dir / "day7_rebuild_logger_event_index.csv"
    )
    status = json.loads(
        (run_dir / "day7_map_mutation_event_summary.json").read_text(
            encoding="utf-8"
        )
    )
    if mutation["record_count"] != len(events):
        raise ValueError("mutation binary/index count mismatch")
    if logger["record_count"] != len(logger_rows):
        raise ValueError("logger binary/index count mismatch")
    if status.get("event_overflow_count") != 0:
        raise ValueError("mutation event overflow")
    if status.get("unclassified_event_count") != 0:
        raise ValueError("unclassified mutation event")
    if (
        status.get("enabled") is not True
        or status.get("scan_start") != EXPECTED_SCAN_START
        or status.get("scan_end") != EXPECTED_SCAN_END
        or status.get("safe_export_state") is not True
        or status.get("diagnostic_internal_error_count") != 0
        or status.get("event_count") != len(events)
    ):
        raise ValueError("Day 7 final status contract mismatch")
    append_count = sum(row["phase"] == "APPEND" for row in logger_rows)
    apply_count = sum(row["phase"] == "APPLY" for row in logger_rows)
    if (
        status.get("logger_append_count") != append_count
        or status.get("logger_apply_count") != apply_count
    ):
        raise ValueError("Day 7 logger count mismatch")
    with (
        run_dir / "day7_rebuild_commit_summaries.csv"
    ).open(newline="", encoding="utf-8") as stream:
        commit_rows = list(csv.DictReader(stream))
    commit_json = json.loads(
        (
            run_dir / "day7_rebuild_commit_summaries.json"
        ).read_text(encoding="utf-8")
    )
    if (
        commit_json.get("record_count") != len(commit_rows)
        or status.get("rebuild_commit_count") != len(commit_rows)
    ):
        raise ValueError("Day 7 rebuild commit count mismatch")
    immutability = json.loads(
        (
            run_dir / "day7_diagnostic_immutability_summary.json"
        ).read_text(encoding="utf-8")
    )
    if (
        immutability.get("diagnostic_mutation_count") != 0
        or immutability.get("diagnostic_readonly_scope_pass") is not True
        or immutability.get("instrumentation_timing_perturbation_present")
        is not True
    ):
        raise ValueError("Day 7 diagnostic immutability failure")
    if len(snapshots) != 42:
        raise ValueError("map point identity snapshot count mismatch")
    if snapshot_binary["record_count"] != 42:
        raise ValueError("map point identity binary count mismatch")
    delta = materialize_delta_accounting(run_dir)
    return {
        "event_count": len(events),
        "call_count": len(calls),
        "logger_record_count": logger["record_count"],
        "logger_append_count": append_count,
        "logger_apply_count": apply_count,
        "rebuild_commit_count": len(commit_rows),
        "snapshot_count": len(snapshots),
        "event_overflow_count": 0,
        "unclassified_event_count": 0,
        "map_delta_accounting_failure_count": delta["failure_count"],
        "trace_schema_pass": True,
    }
