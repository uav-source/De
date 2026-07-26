"""Rebuild logger append/apply comparison for Day 7."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any

from .day7_map_update_events import (
    FNV_OFFSET,
    _fnv_append,
    _identity_bytes,
    _u32,
    _u64,
    _voxel_words,
)


LOGGER_OUTCOME_ENUMS = {
    "LOGGER_APPEND_ADD_POINT": 8,
    "LOGGER_APPEND_DELETE_POINT": 9,
    "LOGGER_APPEND_DELETE_BOX": 10,
    "LOGGER_APPEND_ADD_BOX": 11,
    "LOGGER_APPEND_DOWNSAMPLE_DELETE": 12,
    "LOGGER_APPEND_PUSH_DOWN": 13,
    "REBUILD_LOG_ADD_POINT_APPLIED": 14,
    "REBUILD_LOG_DELETE_POINT_APPLIED": 15,
    "REBUILD_LOG_DELETE_BOX_APPLIED": 16,
    "REBUILD_LOG_ADD_BOX_APPLIED": 17,
    "REBUILD_LOG_DOWNSAMPLE_DELETE_APPLIED": 18,
    "REBUILD_LOG_PUSH_DOWN_APPLIED": 19,
}


def logger_event_checksum(row: dict[str, Any]) -> int:
    checksum = FNV_OFFSET
    checksum = _fnv_append(checksum, _u64(row["logger_sequence_id"]))
    checksum = _fnv_append(checksum, _u64(row["scan_index"]))
    checksum = _fnv_append(checksum, _u32(row["call_index"]))
    checksum = _fnv_append(checksum, _u32(row["batch_point_index"]))
    checksum = _fnv_append(checksum, _u64(row["generation"]))
    checksum = _fnv_append(checksum, _u64(row["apply_order_index"]))
    checksum = _fnv_append(
        checksum, _u64(row["ordered_logger_checksum_after_append"])
    )
    checksum = _fnv_append(
        checksum, _identity_bytes(row["point_sha256"])
    )
    for word in _voxel_words(row["box_identity"]):
        checksum = _fnv_append(checksum, _u32(word))
    if row["outcome"] not in LOGGER_OUTCOME_ENUMS:
        raise ValueError("unknown rebuild logger outcome")
    phase = 1 if row["phase"] == "APPEND" else 2
    return _fnv_append(
        checksum,
        bytes((
            row["operation_set"],
            phase,
            LOGGER_OUTCOME_ENUMS[row["outcome"]],
        )),
    )


def load_logger_events(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    result: list[dict[str, Any]] = []
    for row in rows:
        value: dict[str, Any] = dict(row)
        for name in (
            "event_sequence",
            "logger_sequence_id",
            "operation_set",
            "scan_index",
            "call_index",
            "batch_point_index",
            "generation",
            "apply_order_index",
            "ordered_logger_checksum_after_append",
            "logical_count_before",
            "logical_count_after",
            "event_checksum",
        ):
            value[name] = int(row[name])
        if value["phase"] not in {"APPEND", "APPLY"}:
            raise ValueError("unknown logger phase")
        if logger_event_checksum(value) != value["event_checksum"]:
            raise ValueError("rebuild logger event checksum mismatch")
        result.append(value)
    return result


def compare_logger_runs(left: Path, right: Path) -> dict[str, Any]:
    left_rows = load_logger_events(
        left / "day7_rebuild_logger_event_index.csv"
    )
    right_rows = load_logger_events(
        right / "day7_rebuild_logger_event_index.csv"
    )
    fields = (
        "phase",
        "operation_set",
        "generation",
        "apply_order_index",
        "outcome",
        "point_sha256",
        "box_identity",
    )
    mismatch_indexes = [
        index
        for index, (a, b) in enumerate(zip(left_rows, right_rows))
        if any(a[field] != b[field] for field in fields)
    ]
    if len(left_rows) != len(right_rows):
        mismatch_indexes.extend(
            range(min(len(left_rows), len(right_rows)),
                  max(len(left_rows), len(right_rows)))
        )
    left_append = [row for row in left_rows if row["phase"] == "APPEND"]
    right_append = [row for row in right_rows if row["phase"] == "APPEND"]
    left_apply = [row for row in left_rows if row["phase"] == "APPLY"]
    right_apply = [row for row in right_rows if row["phase"] == "APPLY"]

    def entry_signature(row: dict[str, Any]) -> tuple[Any, ...]:
        return (
            row["operation_set"],
            row["point_sha256"],
            row["box_identity"],
        )

    def result_signature(row: dict[str, Any]) -> tuple[Any, ...]:
        return entry_signature(row) + (
            row["outcome"],
            row["logical_count_before"],
            row["logical_count_after"],
        )

    left_append_signatures = [
        entry_signature(row) for row in left_append
    ]
    right_append_signatures = [
        entry_signature(row) for row in right_append
    ]
    left_apply_signatures = [
        entry_signature(row) for row in left_apply
    ]
    right_apply_signatures = [
        entry_signature(row) for row in right_apply
    ]
    left_apply_results = [
        result_signature(row) for row in left_apply
    ]
    right_apply_results = [
        result_signature(row) for row in right_apply
    ]
    return {
        "left_record_count": len(left_rows),
        "right_record_count": len(right_rows),
        "left_append_count": len(left_append),
        "right_append_count": len(right_append),
        "left_apply_count": len(left_apply),
        "right_apply_count": len(right_apply),
        "mismatch_count": len(mismatch_indexes),
        "first_mismatch_index":
            mismatch_indexes[0] if mismatch_indexes else None,
        "logger_trace_equal": not mismatch_indexes,
        "append_multiset_equal": (
            Counter(left_append_signatures)
            == Counter(right_append_signatures)
        ),
        "append_order_equal": (
            left_append_signatures == right_append_signatures
        ),
        "apply_entry_multiset_equal": (
            Counter(left_apply_signatures)
            == Counter(right_apply_signatures)
        ),
        "apply_order_equal": (
            left_apply_signatures == right_apply_signatures
        ),
        "apply_result_equal": (
            left_apply_results == right_apply_results
        ),
    }
