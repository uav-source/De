"""Strict two-run stage comparison for Day 6 Experiment A."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .experiment_a_stage_hash import (
    EXPECTED_RECORD_COUNT,
    SCAN_END,
    SCAN_START,
    ExperimentAStageHashError,
    validate_record,
)
from .experiment_a_map_snapshot_coherence import pair_coherence_gate


CLASSIFICATIONS = {
    "INPUT_STAGE_DIVERGED",
    "UNDISTORTION_OR_IMU_PROCESSING_STAGE_DIVERGED",
    "MAP_STATE_ALREADY_DIVERGED",
    "MAP_STORAGE_ORDER_DIFFERED_WITH_MATCHED_CONTENT",
    "CORRESPONDENCE_CONSTRUCTION_DIVERGED_WITH_MATCHED_INPUT_AND_MAP_CONTENT",
    "FILTER_UPDATE_STAGE_DIVERGED",
    "MAP_INSERTION_STAGE_DIVERGED",
    "NO_DIVERGENCE_IN_DIAGNOSTIC_PAIR",
    "EVIDENCE_GAP_MAP_SNAPSHOT_NOT_COHERENT",
}

IDENTITY_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("timestamp", ("timestamp_begin", "timestamp_end")),
    ("raw_lidar", ("raw_lidar_payload_checksum",)),
    ("imu_bundle", ("imu_bundle_checksum",)),
    ("undistorted_cloud", ("undistorted_cloud_checksum",)),
    ("prior_state", ("prior_state_checksum",)),
    ("prior_covariance", ("prior_covariance_checksum",)),
    ("map_content_before", ("map_content_before_measurement",)),
    ("map_traversal_before", ("map_traversal_before_measurement",)),
    (
        "correspondence",
        (
            "valid_correspondence_count",
            "accepted_index_checksum",
            "formal_correspondence_checksum",
            "formal_native_jacobian_checksum",
            "detector_jacobian_checksum",
            "formal_innovation_checksum",
            "geometric_residual_checksum",
        ),
    ),
    (
        "post_update_state",
        ("post_update_state_checksum", "post_update_covariance_checksum"),
    ),
    (
        "insertion_batch",
        (
            "map_insertion_executed",
            "map_insertion_batch_ordered_checksum",
            "map_insertion_batch_multiset_checksum",
            "map_insertion_batch_point_count",
        ),
    ),
    ("map_content_after", ("map_content_after_insertion",)),
    ("map_traversal_after", ("map_traversal_after_insertion",)),
)


class ExperimentAClassificationError(ValueError):
    """Raised when stage evidence cannot be aligned or classified."""


def load_records(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ExperimentAClassificationError("stage record file must be a list")
    return [validate_record(record) for record in value]


def _validate_pair(
    run_1: Sequence[Mapping[str, Any]],
    run_2: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        first = [validate_record(record) for record in run_1]
        second = [validate_record(record) for record in run_2]
    except ExperimentAStageHashError as error:
        raise ExperimentAClassificationError(str(error)) from error
    expected = list(range(SCAN_START, SCAN_END + 1))
    for label, records in (("run_1", first), ("run_2", second)):
        scans = [int(record["scan_index"]) for record in records]
        if len(records) != EXPECTED_RECORD_COUNT or scans != expected:
            raise ExperimentAClassificationError(
                f"{label} stage window incomplete: {scans}"
            )
    return first, second


def _same(
    left: Mapping[str, Any], right: Mapping[str, Any], fields: Sequence[str]
) -> bool:
    return all(left[field] == right[field] for field in fields)


def _classification_for_stage(stage: str) -> str:
    if stage in {"raw_lidar", "imu_bundle"}:
        return "INPUT_STAGE_DIVERGED"
    if stage == "undistorted_cloud":
        return "UNDISTORTION_OR_IMU_PROCESSING_STAGE_DIVERGED"
    if stage == "map_content_before":
        return "MAP_STATE_ALREADY_DIVERGED"
    if stage in {"map_traversal_before", "map_traversal_after"}:
        return "MAP_STORAGE_ORDER_DIFFERED_WITH_MATCHED_CONTENT"
    if stage == "correspondence":
        return (
            "CORRESPONDENCE_CONSTRUCTION_DIVERGED_WITH_"
            "MATCHED_INPUT_AND_MAP_CONTENT"
        )
    if stage == "post_update_state":
        return "FILTER_UPDATE_STAGE_DIVERGED"
    if stage in {"insertion_batch", "map_content_after"}:
        return "MAP_INSERTION_STAGE_DIVERGED"
    return "EVIDENCE_GAP_MAP_SNAPSHOT_NOT_COHERENT"


def compare_pair(
    run_1: Sequence[Mapping[str, Any]],
    run_2: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    try:
        first, second = _validate_pair(run_1, run_2)
    except ExperimentAClassificationError as error:
        return {
            "comparison_pass": False,
            "stage_classification_complete": False,
            "stage_classification":
                "EVIDENCE_GAP_MAP_SNAPSHOT_NOT_COHERENT",
            "first_divergence_scan": None,
            "first_divergence_stage":
                "EVIDENCE_GAP_MAP_SNAPSHOT_NOT_COHERENT",
            "evidence_gap": True,
            "error": str(error),
            "rows": [],
        }

    coherence = pair_coherence_gate(first, second)
    if not (
        coherence["map_snapshot_coherence_pass"]
        and coherence["map_snapshot_cross_scan_coherence_pass"]
    ):
        return {
            "comparison_pass": False,
            "stage_classification_complete": False,
            "stage_classification":
                "EVIDENCE_GAP_MAP_SNAPSHOT_NOT_COHERENT",
            "first_divergence_scan": None,
            "first_divergence_stage":
                "EVIDENCE_GAP_MAP_SNAPSHOT_NOT_COHERENT",
            "branch_reproduced": False,
            "evidence_gap": True,
            **coherence,
            "rows": [],
        }

    rows: list[dict[str, Any]] = []
    first_divergence_scan: int | None = None
    first_divergence_stage: str | None = None
    for left, right in zip(first, second):
        row: dict[str, Any] = {
            "scan_index": int(left["scan_index"]),
            "timestamp_begin_run_1": left["timestamp_begin"],
            "timestamp_begin_run_2": right["timestamp_begin"],
            "timestamp_end_run_1": left["timestamp_end"],
            "timestamp_end_run_2": right["timestamp_end"],
        }
        for name, fields in IDENTITY_GROUPS:
            row[f"{name}_identity"] = _same(left, right, fields)
        differing = [
            name
            for name, _fields in IDENTITY_GROUPS
            if not bool(row[f"{name}_identity"])
        ]
        row["first_differing_stage_in_scan"] = (
            differing[0] if differing else ""
        )
        if first_divergence_scan is None and differing:
            first_divergence_scan = int(left["scan_index"])
            first_divergence_stage = differing[0]
        rows.append(row)

    classification = (
        "NO_DIVERGENCE_IN_DIAGNOSTIC_PAIR"
        if first_divergence_stage is None
        else _classification_for_stage(first_divergence_stage)
    )
    evidence_gap = classification == (
        "EVIDENCE_GAP_MAP_SNAPSHOT_NOT_COHERENT"
    )
    identity_status: dict[str, str] = {}
    for name, _fields in IDENTITY_GROUPS:
        identity_status[name] = (
            "MATCHED_BY_CANONICAL_CHECKSUM"
            if all(bool(row[f"{name}_identity"]) for row in rows)
            else "DIVERGED"
        )
    branch_reproduced = classification not in {
        "NO_DIVERGENCE_IN_DIAGNOSTIC_PAIR",
        "EVIDENCE_GAP_MAP_SNAPSHOT_NOT_COHERENT",
    }
    stage_localization_pass = branch_reproduced
    day7_recommended = False
    day7_scope = "NONE"
    input_remediation = False
    if classification in {
        "INPUT_STAGE_DIVERGED",
        "UNDISTORTION_OR_IMU_PROCESSING_STAGE_DIVERGED",
    }:
        input_remediation = True
    elif classification == "MAP_STATE_ALREADY_DIVERGED":
        day7_recommended = True
        day7_scope = "MAP_MUTATION_AND_IKDTREE_REBUILD_DIAGNOSTICS"
    elif classification == (
        "CORRESPONDENCE_CONSTRUCTION_DIVERGED_WITH_"
        "MATCHED_INPUT_AND_MAP_CONTENT"
    ):
        day7_recommended = True
        day7_scope = "FINE_GRAIN_CORRESPONDENCE_AND_THREAD_ORDER_DIAGNOSTICS"
    elif classification == (
        "MAP_STORAGE_ORDER_DIFFERED_WITH_MATCHED_CONTENT"
    ):
        first_row = next(
            row
            for row in rows
            if row["scan_index"] == first_divergence_scan
        )
        if not first_row["correspondence_identity"]:
            day7_recommended = True
            day7_scope = (
                "IKDTREE_TRAVERSAL_ORDER_AND_CORRESPONDENCE_SENSITIVITY"
            )
    additional_replay_recommended = classification == (
        "NO_DIVERGENCE_IN_DIAGNOSTIC_PAIR"
    )
    return {
        "comparison_pass": not evidence_gap,
        "stage_classification_complete": not evidence_gap,
        "stage_classification": classification,
        "first_divergence_scan": first_divergence_scan,
        "first_divergence_stage": (
            first_divergence_stage or "NONE"
        ),
        "branch_reproduced": branch_reproduced,
        "evidence_gap": evidence_gap,
        "identity_status": identity_status,
        "experiment_a_stage_localization_pass": stage_localization_pass,
        "experiment_a_pass": stage_localization_pass,
        "day7_recommended": day7_recommended,
        "day7_recommended_scope": day7_scope,
        "day7_authorized": False,
        "input_replay_or_preprocessing_remediation_recommended":
            input_remediation,
        "additional_replay_recommended": additional_replay_recommended,
        "additional_replay_authorized": False,
        "checksum_collision_limitation_disclosed": True,
        "checksum_interpretation": "MATCHED_BY_CANONICAL_CHECKSUM",
        **coherence,
        "rows": rows,
    }


def write_comparison(result: Mapping[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = list(result.get("rows", []))
    csv_path = (
        output_dir / "experiment_a_map_snapshot_pairwise_comparison.csv"
    )
    if rows:
        with csv_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("scan_index,error\n", encoding="utf-8")
    first = {
        "schema_version": "experiment_a_map_snapshot_first_divergence_v1",
        "first_divergence_scan": result.get("first_divergence_scan"),
        "first_divergence_stage": result.get("first_divergence_stage"),
        "branch_reproduced": result.get("branch_reproduced", False),
        "evidence_gap": result.get("evidence_gap", True),
    }
    classification = {
        key: value
        for key, value in result.items()
        if key not in {"rows", "identity_status"}
    }
    classification["schema_version"] = (
        "experiment_a_map_snapshot_stage_classification_v1"
    )
    identity = {
        "schema_version": "experiment_a_map_snapshot_identity_summary_v1",
        "identity_status": result.get("identity_status", {}),
        "checksum_interpretation": "MATCHED_BY_CANONICAL_CHECKSUM",
        "checksum_collision_limitation_disclosed": True,
    }
    for filename, value in (
        ("experiment_a_map_snapshot_first_divergence.json", first),
        (
            "experiment_a_map_snapshot_stage_classification.json",
            classification,
        ),
        ("experiment_a_map_snapshot_identity_summary.json", identity),
    ):
        (output_dir / filename).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
