"""Coherence and continuity gates for Experiment A map snapshots.

The runtime exports compact snapshot metadata and digests only.  No point
payload, accepted-index array, neighbor set, plane array, or detector output is
materialized by this module.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .experiment_a_stage_hash import (
    EXPECTED_RECORD_COUNT,
    SCAN_END,
    SCAN_START,
    SNAPSHOT_METHOD,
    SNAPSHOT_REQUIRED_SUFFIXES,
    SNAPSHOT_SCHEMA_VERSION,
)


COHERENT_STATUS = "COHERENT_SYNCHRONIZED_COPY"
ALLOWED_STATUSES = {
    COHERENT_STATUS,
    "RETRY_EXHAUSTED",
    "LOCK_PROTOCOL_ERROR",
    "VALIDNUM_MISMATCH",
    "GENERATION_CHANGED",
    "MUTATION_COUNTER_CHANGED",
    "INTERNAL_ERROR",
    "NOT_CAPTURED",
}
EXPECTED_SNAPSHOTS_PER_RUN = 52
EXPECTED_TOTAL_SNAPSHOTS = 104


class MapSnapshotCoherenceError(ValueError):
    """Raised when compact snapshot evidence violates the V2 contract."""


def snapshot_from_record(
    record: Mapping[str, Any], prefix: str
) -> dict[str, Any]:
    if prefix not in {"map_before", "map_after"}:
        raise MapSnapshotCoherenceError(f"invalid snapshot prefix: {prefix}")
    result = {
        suffix: record[f"{prefix}_{suffix}"]
        for suffix in SNAPSHOT_REQUIRED_SUFFIXES
    }
    result["scan_index"] = int(record["scan_index"])
    result["record_prefix"] = prefix
    result["map_content_multiset_checksum"] = int(
        result.pop("content_checksum")
    )
    result["map_traversal_order_checksum"] = int(
        result.pop("traversal_checksum")
    )
    result["bbox_min_x"] = result.pop("bbox_min_x")
    result["bbox_min_y"] = result.pop("bbox_min_y")
    result["bbox_min_z"] = result.pop("bbox_min_z")
    result["bbox_max_x"] = result.pop("bbox_max_x")
    result["bbox_max_y"] = result.pop("bbox_max_y")
    result["bbox_max_z"] = result.pop("bbox_max_z")
    return result


def validate_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    status = str(snapshot.get("snapshot_status", ""))
    if status not in ALLOWED_STATUSES:
        raise MapSnapshotCoherenceError(f"unknown snapshot status: {status}")
    if snapshot.get("snapshot_schema_version") != SNAPSHOT_SCHEMA_VERSION:
        raise MapSnapshotCoherenceError("snapshot schema mismatch")
    if snapshot.get("snapshot_method") != SNAPSHOT_METHOD:
        raise MapSnapshotCoherenceError("snapshot method mismatch")
    if status != COHERENT_STATUS:
        raise MapSnapshotCoherenceError(f"snapshot not coherent: {status}")
    if snapshot.get("snapshot_coherence_pass") is not True:
        raise MapSnapshotCoherenceError("snapshot coherence flag false")
    if snapshot.get("snapshot_error") is not None:
        raise MapSnapshotCoherenceError("coherent snapshot has error")
    attempts = int(snapshot.get("snapshot_attempt_count", 0))
    if not 1 <= attempts <= 3:
        raise MapSnapshotCoherenceError("snapshot attempt count invalid")
    before = int(snapshot["validnum_before"])
    after = int(snapshot["validnum_after"])
    count = int(snapshot["snapshot_point_count"])
    if before != after or before != count:
        raise MapSnapshotCoherenceError("snapshot validnum/count mismatch")
    if int(snapshot["rebuild_generation_before"]) != int(
        snapshot["rebuild_generation_after"]
    ):
        raise MapSnapshotCoherenceError("snapshot generation changed")
    if int(snapshot["mutation_counter_before"]) != int(
        snapshot["mutation_counter_after"]
    ):
        raise MapSnapshotCoherenceError("snapshot mutation counter changed")
    if int(snapshot["snapshot_nonfinite_point_count"]) != 0:
        raise MapSnapshotCoherenceError("snapshot contains nonfinite point")
    return dict(snapshot)


def records_to_snapshots(
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for record in records:
        snapshots.append(snapshot_from_record(record, "map_before"))
        snapshots.append(snapshot_from_record(record, "map_after"))
    return snapshots


def _delta(current: int, previous: int, label: str) -> int:
    if current < previous:
        raise MapSnapshotCoherenceError(f"{label} counter regressed")
    return current - previous


def cross_scan_continuity(
    records: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ordered = sorted(records, key=lambda row: int(row["scan_index"]))
    rows: list[dict[str, Any]] = []
    for previous, current in zip(ordered, ordered[1:]):
        previous_after = snapshot_from_record(previous, "map_after")
        current_before = snapshot_from_record(current, "map_before")
        add_delta = _delta(
            int(current_before["logical_add_call_count_total"]),
            int(previous_after["logical_add_call_count_total"]),
            "add",
        )
        delete_delta = _delta(
            int(current_before["logical_delete_call_count_total"]),
            int(previous_after["logical_delete_call_count_total"]),
            "delete",
        )
        previous_count = int(previous_after["snapshot_point_count"])
        current_count = int(current_before["snapshot_point_count"])
        previous_content = int(
            previous_after["map_content_multiset_checksum"]
        )
        current_content = int(current_before["map_content_multiset_checksum"])
        if add_delta == 0 and delete_delta == 0:
            rule = "NO_ADD_NO_DELETE_REQUIRES_COUNT_AND_CONTENT_IDENTITY"
            passed = (
                previous_count == current_count
                and previous_content == current_content
            )
        elif add_delta == 0:
            rule = "DELETE_ONLY_FORBIDS_COUNT_INCREASE"
            passed = current_count <= previous_count
        else:
            rule = "ADD_PRESENT_PERMITS_COUNT_INCREASE"
            passed = True
        if add_delta == 0 and current_count > previous_count:
            passed = False
            rule = "NO_ADD_FORBIDS_COUNT_INCREASE"
        rows.append(
            {
                "previous_scan": int(previous["scan_index"]),
                "current_scan": int(current["scan_index"]),
                "previous_after_count": previous_count,
                "current_before_count": current_count,
                "previous_after_content_checksum": previous_content,
                "current_before_content_checksum": current_content,
                "previous_after_traversal_checksum": int(
                    previous_after["map_traversal_order_checksum"]
                ),
                "current_before_traversal_checksum": int(
                    current_before["map_traversal_order_checksum"]
                ),
                "add_call_delta": add_delta,
                "delete_call_delta": delete_delta,
                "rebuild_generation_delta": (
                    int(current_before["rebuild_generation_before"])
                    - int(previous_after["rebuild_generation_after"])
                ),
                "continuity_rule": rule,
                "continuity_pass": passed,
                "notes": (
                    "traversal may change under pure rebuild"
                    if passed
                    else "logical-map continuity invariant violated"
                ),
            }
        )
    violation_count = sum(not row["continuity_pass"] for row in rows)
    summary = {
        "schema_version": "map_snapshot_cross_scan_continuity_summary_v1",
        "transition_count": len(rows),
        "violation_count": violation_count,
        "map_snapshot_cross_scan_coherence_pass": violation_count == 0,
    }
    return rows, summary


def summarize_snapshots(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    snapshots = records_to_snapshots(records)
    coherent = 0
    errors: list[str] = []
    for snapshot in snapshots:
        try:
            validate_snapshot(snapshot)
            coherent += 1
        except MapSnapshotCoherenceError as error:
            errors.append(
                f"scan={snapshot['scan_index']} "
                f"stage={snapshot['snapshot_stage']}: {error}"
            )
    before_count = sum(
        snapshot["record_prefix"] == "map_before" for snapshot in snapshots
    )
    after_count = sum(
        snapshot["record_prefix"] == "map_after" for snapshot in snapshots
    )
    lock_wait = [int(snapshot["lock_wait_ns"]) for snapshot in snapshots]
    copy_cost = [int(snapshot["locked_copy_ns"]) for snapshot in snapshots]
    return {
        "schema_version": "coherent_map_snapshot_summary_v1",
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "snapshot_method": SNAPSHOT_METHOD,
        "map_before_snapshot_count": before_count,
        "map_after_snapshot_count": after_count,
        "snapshot_count": len(snapshots),
        "coherent_snapshot_count": coherent,
        "incoherent_snapshot_count": len(snapshots) - coherent,
        "map_snapshot_coherence_pass": (
            len(records) == EXPECTED_RECORD_COUNT
            and len(snapshots) == EXPECTED_SNAPSHOTS_PER_RUN
            and coherent == EXPECTED_SNAPSHOTS_PER_RUN
        ),
        "lock_wait_ns": _statistics(lock_wait),
        "locked_copy_ns": _statistics(copy_cost),
        "errors": errors,
    }


def pair_coherence_gate(
    run_1: Sequence[Mapping[str, Any]],
    run_2: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    summaries = [summarize_snapshots(run_1), summarize_snapshots(run_2)]
    continuity = [
        cross_scan_continuity(run_1)[1],
        cross_scan_continuity(run_2)[1],
    ]
    return {
        "expected_total_snapshot_count": EXPECTED_TOTAL_SNAPSHOTS,
        "actual_total_snapshot_count": sum(
            int(summary["snapshot_count"]) for summary in summaries
        ),
        "coherent_snapshot_count": sum(
            int(summary["coherent_snapshot_count"]) for summary in summaries
        ),
        "incoherent_snapshot_count": sum(
            int(summary["incoherent_snapshot_count"]) for summary in summaries
        ),
        "map_snapshot_coherence_pass": all(
            summary["map_snapshot_coherence_pass"] for summary in summaries
        ),
        "map_snapshot_cross_scan_coherence_pass": all(
            summary["map_snapshot_cross_scan_coherence_pass"]
            for summary in continuity
        ),
        "per_run_snapshot_summaries": summaries,
        "per_run_continuity_summaries": continuity,
    }


def materialize_snapshot_evidence(
    records: Sequence[Mapping[str, Any]], output_dir: Path
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshots = records_to_snapshots(records)
    summary = summarize_snapshots(records)
    continuity_rows, continuity_summary = cross_scan_continuity(records)
    _write_json(output_dir / "coherent_map_snapshot_records.json", snapshots)
    _write_csv(output_dir / "coherent_map_snapshot_records.csv", snapshots)
    _write_json(output_dir / "coherent_map_snapshot_summary.json", summary)
    _write_csv(
        output_dir / "map_snapshot_cross_scan_continuity.csv",
        continuity_rows,
    )
    _write_json(
        output_dir / "map_snapshot_cross_scan_continuity_summary.json",
        continuity_summary,
    )
    mutation_rows = [
        {
            "scan_index": int(record["scan_index"]),
            "map_mutation_counter_before_measurement": int(
                record["map_mutation_counter_before_measurement"]
            ),
            "map_mutation_counter_after_insertion": int(
                record["map_mutation_counter_after_insertion"]
            ),
            "logical_add_call_count": int(
                record["logical_add_call_count"]
            ),
            "logical_delete_call_count": int(
                record["logical_delete_call_count"]
            ),
            "logical_add_input_point_count": int(
                record["logical_add_input_point_count"]
            ),
            "logical_delete_box_count": int(
                record["logical_delete_box_count"]
            ),
        }
        for record in records
    ]
    _write_csv(
        output_dir / "logical_map_mutation_counters.csv", mutation_rows
    )
    return {
        **summary,
        "cross_scan_continuity_violation_count": int(
            continuity_summary["violation_count"]
        ),
        "map_snapshot_cross_scan_coherence_pass": bool(
            continuity_summary["map_snapshot_cross_scan_coherence_pass"]
        ),
    }


def _statistics(values: Sequence[int]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "min": 0, "max": 0, "mean": 0.0}
    return {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        path.write_text("empty\n", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
