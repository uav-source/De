"""Fail-closed six-pair analysis for bounded formal branch reproduction."""

from __future__ import annotations

import csv
import json
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping, Sequence

from .day6_semantic_observation import compare_semantic_pair
from .experiment_a_map_snapshot_coherence import pair_coherence_gate
from .experiment_a_stage_classifier import IDENTITY_GROUPS, load_records


RUN_COUNT = 4
EXPECTED_PAIR_COUNT = 6
FORMAL_STAGE_GROUPS = {
    "prior_state",
    "prior_covariance",
    "map_content_before",
    "correspondence",
    "post_update_state",
    "insertion_batch",
    "map_content_after",
}
TRAVERSAL_STAGE_GROUPS = {
    "map_traversal_before",
    "map_traversal_after",
}
CLASSIFICATIONS = {
    "INPUT_STAGE_DIVERGED",
    "UNDISTORTION_OR_IMU_PROCESSING_STAGE_DIVERGED",
    "MAP_STATE_ALREADY_DIVERGED",
    "CORRESPONDENCE_CONSTRUCTION_DIVERGED_WITH_MATCHED_INPUT_AND_MAP_CONTENT",
    "IKDTREE_TRAVERSAL_ORDER_ASSOCIATED_CORRESPONDENCE_DIVERGENCE",
    "FILTER_UPDATE_STAGE_DIVERGED",
    "MAP_INSERTION_STAGE_DIVERGED",
    "NO_FORMAL_DIVERGENCE",
    "EVIDENCE_GAP",
}


class BoundedBranchError(ValueError):
    """Bounded branch inputs do not satisfy the frozen comparison contract."""


def pair_names(run_ids: Sequence[str]) -> list[tuple[str, str, str]]:
    if len(run_ids) != RUN_COUNT or len(set(run_ids)) != RUN_COUNT:
        raise BoundedBranchError("exactly four unique run ids are required")
    return [
        (left, right, f"{left}-{right}")
        for left, right in combinations(run_ids, 2)
    ]


def _same(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    fields: Sequence[str],
) -> bool:
    return all(left[field] == right[field] for field in fields)


def _classification(
    rows: Sequence[Mapping[str, Any]],
    first_formal_scan: int | None,
    first_formal_stage: str | None,
) -> str:
    if first_formal_scan is None or first_formal_stage is None:
        return "NO_FORMAL_DIVERGENCE"
    prior_rows = [
        row
        for row in rows
        if int(row["scan_index"]) <= first_formal_scan
    ]
    for name in ("raw_lidar", "imu_bundle"):
        if any(not bool(row[f"{name}_identity"]) for row in prior_rows):
            return "INPUT_STAGE_DIVERGED"
    if any(
        not bool(row["undistorted_cloud_identity"]) for row in prior_rows
    ):
        return "UNDISTORTION_OR_IMU_PROCESSING_STAGE_DIVERGED"
    if first_formal_stage in {
        "prior_state",
        "prior_covariance",
        "map_content_before",
    }:
        return "MAP_STATE_ALREADY_DIVERGED"
    if first_formal_stage == "correspondence":
        same_scan = next(
            row
            for row in rows
            if int(row["scan_index"]) == first_formal_scan
        )
        if not bool(same_scan["map_traversal_before_identity"]):
            return (
                "IKDTREE_TRAVERSAL_ORDER_ASSOCIATED_"
                "CORRESPONDENCE_DIVERGENCE"
            )
        return (
            "CORRESPONDENCE_CONSTRUCTION_DIVERGED_WITH_"
            "MATCHED_INPUT_AND_MAP_CONTENT"
        )
    if first_formal_stage == "post_update_state":
        return "FILTER_UPDATE_STAGE_DIVERGED"
    if first_formal_stage in {"insertion_batch", "map_content_after"}:
        return "MAP_INSERTION_STAGE_DIVERGED"
    return "EVIDENCE_GAP"


def compare_stage_pair(
    *,
    pair: str,
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare one stage pair while excluding traversal-only differences."""

    coherence = pair_coherence_gate(left, right)
    if not (
        coherence["map_snapshot_coherence_pass"]
        and coherence["map_snapshot_cross_scan_coherence_pass"]
    ):
        return {
            "pair": pair,
            "comparison_pass": False,
            "evidence_gap": True,
            "stage_classification_complete": False,
            "stage_classification": "EVIDENCE_GAP",
            "formal_branch_reproduced": False,
            "first_any_divergence_scan": None,
            "first_any_divergence_stage": "EVIDENCE_GAP",
            "first_formal_divergence_scan": None,
            "first_formal_divergence_stage": "EVIDENCE_GAP",
            "rows": [],
            **coherence,
        }
    if len(left) != 26 or len(right) != 26:
        raise BoundedBranchError("each stage run must contain 26 records")
    rows: list[dict[str, Any]] = []
    first_any_scan: int | None = None
    first_any_stage: str | None = None
    first_formal_scan: int | None = None
    first_formal_stage: str | None = None
    for left_record, right_record in zip(left, right):
        if int(left_record["scan_index"]) != int(right_record["scan_index"]):
            raise BoundedBranchError("stage scan alignment mismatch")
        row: dict[str, Any] = {
            "pair": pair,
            "scan_index": int(left_record["scan_index"]),
        }
        for name, fields in IDENTITY_GROUPS:
            row[f"{name}_identity"] = _same(
                left_record, right_record, fields
            )
        differences = [
            name
            for name, _fields in IDENTITY_GROUPS
            if not bool(row[f"{name}_identity"])
        ]
        formal = [name for name in differences if name in FORMAL_STAGE_GROUPS]
        traversal = [
            name for name in differences if name in TRAVERSAL_STAGE_GROUPS
        ]
        row["first_differing_stage_in_scan"] = (
            differences[0] if differences else ""
        )
        row["first_formal_differing_stage_in_scan"] = (
            formal[0] if formal else ""
        )
        row["formal_divergence_in_scan"] = bool(formal)
        row["traversal_only_difference_in_scan"] = bool(
            traversal and not formal and len(differences) == len(traversal)
        )
        if first_any_scan is None and differences:
            first_any_scan = int(row["scan_index"])
            first_any_stage = differences[0]
        if first_formal_scan is None and formal:
            first_formal_scan = int(row["scan_index"])
            first_formal_stage = formal[0]
        rows.append(row)
    classification = _classification(
        rows, first_formal_scan, first_formal_stage
    )
    if classification not in CLASSIFICATIONS:
        raise BoundedBranchError("unsupported stage classification")
    identity_status = {
        name: (
            "MATCHED_BY_CANONICAL_CHECKSUM"
            if all(bool(row[f"{name}_identity"]) for row in rows)
            else "DIVERGED"
        )
        for name, _fields in IDENTITY_GROUPS
    }
    return {
        "pair": pair,
        "comparison_pass": True,
        "evidence_gap": False,
        "stage_classification_complete": True,
        "stage_classification": classification,
        "formal_branch_reproduced": first_formal_scan is not None,
        "first_any_divergence_scan": first_any_scan,
        "first_any_divergence_stage": first_any_stage or "NONE",
        "first_formal_divergence_scan": first_formal_scan,
        "first_formal_divergence_stage": first_formal_stage or "NONE",
        "traversal_difference_observed": any(
            not bool(row["map_traversal_before_identity"])
            or not bool(row["map_traversal_after_identity"])
            for row in rows
        ),
        "identity_status": identity_status,
        "rows": rows,
        **coherence,
    }


def _continuous_divergence(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    spans: list[tuple[int, int]] = []
    start: int | None = None
    previous: int | None = None
    for row in rows:
        index = int(row["record_index"])
        if not bool(row["semantic_equal"]):
            if start is None:
                start = index
            previous = index
        elif start is not None and previous is not None:
            spans.append((start, previous))
            start = None
            previous = None
    if start is not None and previous is not None:
        spans.append((start, previous))
    if not spans:
        return {"start_record": None, "end_record": None, "record_count": 0}
    longest = max(spans, key=lambda value: value[1] - value[0] + 1)
    return {
        "start_record": longest[0],
        "end_record": longest[1],
        "record_count": longest[1] - longest[0] + 1,
    }


def summarize_semantic_pair(
    pair: str,
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    mismatches = [row for row in rows if not bool(row["semantic_equal"])]
    correspondence_fields = {
        "valid_correspondence_count",
        "detector_pose_jacobian_rows",
        "formal_filter_innovation_h",
        "formal_native_jacobian_checksum",
        "detector_jacobian_checksum",
        "formal_innovation_checksum",
        "geometric_residual_checksum",
        "accepted_index_checksum",
        "formal_correspondence_checksum",
    }
    state_fields = {
        "prior_position_world",
        "prior_orientation_world_from_imu_xyzw",
        "prior_covariance_detector_order_raw",
        "prior_covariance_detector_order_symmetric",
    }
    first = mismatches[0] if mismatches else None
    last = mismatches[-1] if mismatches else None
    return {
        "pair": pair,
        "semantic_mismatch_count": len(mismatches),
        "first_semantic_divergence_record": (
            int(first["record_index"]) if first else None
        ),
        "first_semantic_divergence_scan": (
            int(first["scan_index"]) if first else None
        ),
        "last_semantic_divergence_record": (
            int(last["record_index"]) if last else None
        ),
        "continuous_divergence_span": _continuous_divergence(rows),
        "formal_correspondence_mismatch_count": sum(
            bool(set(row["all_differing_fields"]) & correspondence_fields)
            for row in rows
        ),
        "formal_state_mismatch_count": sum(
            bool(set(row["all_differing_fields"]) & state_fields)
            for row in rows
        ),
    }


def compare_all(
    *,
    run_ids: Sequence[str],
    observations: Mapping[str, Sequence[Mapping[str, Any]]],
    stage_records: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    semantic_rows: list[dict[str, Any]] = []
    semantic_summaries: list[dict[str, Any]] = []
    stage_rows: list[dict[str, Any]] = []
    stage_summaries: list[dict[str, Any]] = []
    for left_id, right_id, pair in pair_names(run_ids):
        pair_semantic_rows = compare_semantic_pair(
            pair=pair,
            left=observations[left_id],
            right=observations[right_id],
        )
        semantic_rows.extend(pair_semantic_rows)
        semantic_summaries.append(
            summarize_semantic_pair(pair, pair_semantic_rows)
        )
        stage = compare_stage_pair(
            pair=pair,
            left=stage_records[left_id],
            right=stage_records[right_id],
        )
        stage_rows.extend(stage["rows"])
        stage_summaries.append(
            {key: value for key, value in stage.items() if key != "rows"}
        )
    return {
        "semantic_rows": semantic_rows,
        "semantic_summaries": semantic_summaries,
        "stage_rows": stage_rows,
        "stage_summaries": stage_summaries,
    }


def branch_gate(
    *,
    run_complete: Sequence[bool],
    semantic_summaries: Sequence[Mapping[str, Any]],
    stage_summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    six_semantic = (
        len(semantic_summaries) == EXPECTED_PAIR_COUNT
        and all(
            int(row["semantic_mismatch_count"]) >= 0
            for row in semantic_summaries
        )
    )
    six_stage = (
        len(stage_summaries) == EXPECTED_PAIR_COUNT
        and all(bool(row["comparison_pass"]) for row in stage_summaries)
        and all(
            bool(row["stage_classification_complete"])
            for row in stage_summaries
        )
    )
    complete = len(run_complete) == RUN_COUNT and all(run_complete)
    semantic_pairs = {
        row["pair"]
        for row in semantic_summaries
        if int(row["semantic_mismatch_count"]) > 0
    }
    localized_pairs = {
        row["pair"]
        for row in stage_summaries
        if bool(row["formal_branch_reproduced"])
        and row["first_formal_divergence_stage"] != "NONE"
        and not bool(row["evidence_gap"])
    }
    formal = bool(
        complete
        and six_semantic
        and six_stage
        and semantic_pairs
        and semantic_pairs.issubset(localized_pairs)
    )
    execution = complete and six_semantic and six_stage
    return {
        "four_replay_runs_complete_pass": complete,
        "six_pair_semantic_comparison_pass": six_semantic,
        "six_pair_stage_comparison_pass": six_stage,
        "stage_classification_complete": six_stage,
        "formal_branch_reproduced": formal,
        "formal_branch_stage_localized": formal,
        "bounded_branch_reproduction_execution_pass": execution,
        "branch_reproduction_status": (
            "FORMAL_BRANCH_REPRODUCED_AND_STAGE_LOCALIZED"
            if formal
            else (
                "NOT_OBSERVED_IN_FOUR_FIXED_RUNS"
                if execution and not semantic_pairs
                else "EVIDENCE_GAP"
            )
        ),
        "additional_replay_recommended": False,
        "additional_replay_authorized": False,
    }


def run_completeness(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate one fixed replay without weakening any runtime gate."""

    checks = {
        "wrapper_exit_code_pass":
            int(summary.get("wrapper_exit_code", -1)) == 0,
        "callbacks_pass": (
            int(summary.get("lidar_callback_count", -1)) == 491
            and int(summary.get("imu_callback_count", -1)) == 9953
        ),
        "runtime_scans_pass":
            int(summary.get("runtime_scan_count", -1)) == 490,
        "observation_count_pass":
            int(summary.get("observation_record_count", -1)) == 487,
        "stage_records_pass": (
            int(summary.get("stage_hash_record_count", -1)) == 26
            and int(summary.get("stage_hash_first_scan", -1)) == 135
            and int(summary.get("stage_hash_last_scan", -1)) == 160
        ),
        "snapshot_count_pass": (
            int(summary.get("map_before_snapshot_count", -1)) == 26
            and int(summary.get("map_after_snapshot_count", -1)) == 26
            and int(summary.get("coherent_snapshot_count", -1)) == 52
            and int(summary.get("incoherent_snapshot_count", -1)) == 0
        ),
        "cross_scan_coherence_pass": (
            int(summary.get("cross_scan_continuity_violation_count", -1))
            == 0
            and summary.get("map_snapshot_cross_scan_coherence_pass")
            is True
        ),
        "tap_and_writer_pass": (
            int(summary.get("tap_drop_count", -1)) == 0
            and int(summary.get("writer_error_count", -1)) == 0
        ),
        "binary_integrity_pass": (
            int(summary.get("binary_checksum_failure_count", -1)) == 0
            and int(summary.get("truncated_record_count", -1)) == 0
            and int(summary.get("extra_trailing_bytes", -1)) == 0
        ),
        "immutability_pass": (
            int(summary.get("in_call_mutation_count", -1)) == 0
            and int(summary.get("diagnostic_mutation_count", -1)) == 0
        ),
        "schema_and_gt_pass": (
            int(summary.get("schema_rejected_record_count", -1)) == 0
            and int(summary.get("GT_TOPIC_CONSUMED_COUNT", -1)) == 0
        ),
        "lifecycle_pass": all(
            summary.get(name) is True
            for name in (
                "end_of_stream_drain_pass",
                "normal_shutdown_pass",
                "runtime_product_pass",
                "adjudicated_tail_handoff_pass",
            )
        ),
    }
    return {
        **checks,
        "run_completeness_pass": (
            summary.get("complete") is True and all(checks.values())
        ),
    }


def write_comparison(result: Mapping[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        output_dir / "pairwise_semantic_observation_comparison.csv",
        result["semantic_rows"],
    )
    _write_json(
        output_dir / "pairwise_semantic_observation_summary.json",
        {
            "schema_version":
                "bounded_pairwise_semantic_observation_summary_v1",
            "pair_count": len(result["semantic_summaries"]),
            "pairs": result["semantic_summaries"],
        },
    )
    _write_csv(
        output_dir / "pairwise_stage_hash_comparison.csv",
        result["stage_rows"],
    )
    first = [
        {
            "pair": row["pair"],
            "first_any_divergence_scan":
                row["first_any_divergence_scan"],
            "first_any_divergence_stage":
                row["first_any_divergence_stage"],
            "first_formal_divergence_scan":
                row["first_formal_divergence_scan"],
            "first_formal_divergence_stage":
                row["first_formal_divergence_stage"],
        }
        for row in result["stage_summaries"]
    ]
    _write_json(
        output_dir / "pairwise_first_divergence.json",
        {
            "schema_version":
                "bounded_pairwise_first_formal_divergence_v1",
            "pair_count": len(first),
            "pairs": first,
        },
    )
    _write_json(
        output_dir / "pairwise_stage_classification.json",
        {
            "schema_version": "bounded_pairwise_stage_classification_v1",
            "pair_count": len(result["stage_summaries"]),
            "pairs": result["stage_summaries"],
        },
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise BoundedBranchError(f"refusing empty comparison CSV: {path.name}")
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            value = dict(row)
            for key, item in value.items():
                if isinstance(item, (list, dict)):
                    value[key] = json.dumps(item, sort_keys=True)
            writer.writerow(value)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
