"""Full-stream and focused-window comparison for four fixed replays."""

from __future__ import annotations

import csv
import json
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping, Sequence

from .day6_semantic_observation import compare_semantic_pair
from .focused_branch_stage_classifier import compare_focused_pair


RUN_COUNT = 4
PAIR_COUNT = 6


def _first(rows: Sequence[Mapping[str, Any]], fields: set[str]) -> Any:
    for row in rows:
        if set(row["all_differing_fields"]) & fields:
            return {
                "record_index": int(row["record_index"]),
                "scan_index": int(row["scan_index"]),
            }
    return None


def _spans(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, int]]:
    spans = []
    start = previous = None
    for row in rows:
        index = int(row["record_index"])
        if not row["semantic_equal"]:
            if start is None:
                start = index
            previous = index
        elif start is not None:
            spans.append({
                "start_record": start,
                "end_record": previous,
                "record_count": previous - start + 1,
            })
            start = previous = None
    if start is not None:
        spans.append({
            "start_record": start,
            "end_record": previous,
            "record_count": previous - start + 1,
        })
    return spans


def summarize_full_stream(
    pair: str, rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    mismatches = [row for row in rows if not row["semantic_equal"]]
    first = mismatches[0] if mismatches else None
    last = mismatches[-1] if mismatches else None
    return {
        "pair": pair,
        "semantic_mismatch_count": len(mismatches),
        "first_divergence_record": (
            int(first["record_index"]) if first else None
        ),
        "first_divergence_scan": (
            int(first["scan_index"]) if first else None
        ),
        "last_divergence_record": (
            int(last["record_index"]) if last else None
        ),
        "continuous_divergence_spans": _spans(rows),
        "first_prior_state_divergence": _first(rows, {
            "prior_position_world",
            "prior_orientation_world_from_imu_xyzw",
        }),
        "first_prior_covariance_divergence": _first(rows, {
            "prior_covariance_detector_order_raw",
            "prior_covariance_detector_order_symmetric",
        }),
        "first_correspondence_divergence": _first(rows, {
            "valid_correspondence_count",
            "accepted_index_checksum",
            "formal_correspondence_checksum",
        }),
        "first_jacobian_divergence": _first(rows, {
            "detector_pose_jacobian_rows",
            "formal_native_jacobian_checksum",
            "detector_jacobian_checksum",
        }),
        "first_innovation_divergence": _first(rows, {
            "formal_filter_innovation_h",
            "formal_innovation_checksum",
        }),
        "first_residual_divergence": _first(
            rows, {"geometric_residual_checksum"}
        ),
        "first_post_update_divergence": None,
        "post_update_observed_in_semantic_schema": False,
    }


def compare_all(
    *,
    run_ids: Sequence[str],
    observations: Mapping[str, Sequence[Mapping[str, Any]]],
    focused_records: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    if len(run_ids) != RUN_COUNT or len(set(run_ids)) != RUN_COUNT:
        raise ValueError("exactly four unique runs are required")
    semantic_rows = []
    semantic_summary = []
    stage_rows = []
    stage_summary = []
    previous_rows = []
    for left, right in combinations(run_ids, 2):
        pair = f"{left}-{right}"
        full_rows = compare_semantic_pair(
            pair=pair, left=observations[left], right=observations[right]
        )
        semantic_rows.extend(full_rows)
        semantic_summary.append(summarize_full_stream(pair, full_rows))
        focused = compare_focused_pair(
            pair=pair,
            left=focused_records[left],
            right=focused_records[right],
        )
        stage_rows.extend(focused["rows"])
        previous_rows.append(focused["previous_scan_identity"])
        stage_summary.append({
            key: value for key, value in focused.items()
            if key not in {"rows", "previous_scan_identity"}
        })
    return {
        "semantic_rows": semantic_rows,
        "semantic_summary": semantic_summary,
        "stage_rows": stage_rows,
        "stage_summary": stage_summary,
        "previous_rows": previous_rows,
    }


def localization_gate(
    *,
    run_complete: Sequence[bool],
    semantic: Sequence[Mapping[str, Any]],
    stage: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    full_pairs = {
        row["pair"]: row for row in semantic
        if int(row["semantic_mismatch_count"]) > 0
    }
    stage_pairs = {
        row["pair"]: row for row in stage
        if row["formal_branch_reproduced"]
    }
    all_inside = all(
        155 <= int(row["first_divergence_scan"]) <= 205
        for row in full_pairs.values()
    )
    matched = (
        set(full_pairs) == set(stage_pairs)
        and all(
            int(full_pairs[pair]["first_divergence_scan"])
            == int(stage_pairs[pair]["first_formal_divergence_scan"])
            for pair in full_pairs
        )
    )
    stage_complete = (
        len(stage) == PAIR_COUNT
        and all(row["comparison_pass"] for row in stage)
        and all(row["stage_classification_complete"] for row in stage)
        and all(row["previous_scan_identity_pass"] for row in stage)
    )
    execution = (
        len(run_complete) == RUN_COUNT
        and all(run_complete)
        and len(semantic) == PAIR_COUNT
        and stage_complete
    )
    reproduced = bool(
        execution and full_pairs and all_inside and matched
    )
    classifications = sorted({
        row["stage_classification"] for row in stage
        if row["formal_branch_reproduced"]
    })
    scopes = {
        "MAP_STATE_ALREADY_DIVERGED":
            "MAP_MUTATION_REBUILD_AND_IKDTREE_STATE_DIAGNOSTICS",
        "CORRESPONDENCE_CONSTRUCTION_DIVERGED_WITH_MATCHED_INPUT_AND_MAP_CONTENT":
            "FINE_GRAIN_CORRESPONDENCE_AND_THREAD_ORDER_DIAGNOSTICS",
        "IKDTREE_TRAVERSAL_ORDER_ASSOCIATED_CORRESPONDENCE_DIVERGENCE":
            "IKDTREE_TRAVERSAL_ORDER_AND_CORRESPONDENCE_SENSITIVITY",
        "FILTER_UPDATE_STAGE_DIVERGED":
            "FILTER_UPDATE_NUMERICAL_ORDER_DIAGNOSTICS",
    }
    recommended_scopes = [
        scopes[name] for name in classifications if name in scopes
    ]
    input_mode = any(name in {
        "INPUT_STAGE_DIVERGED",
        "UNDISTORTION_OR_IMU_PROCESSING_STAGE_DIVERGED",
    } for name in classifications)
    day7 = reproduced and bool(recommended_scopes) and not input_mode
    return {
        "focused_formal_branch_localization_execution_pass": execution,
        "four_replay_runs_complete_pass": (
            len(run_complete) == RUN_COUNT and all(run_complete)
        ),
        "six_pair_full_stream_semantic_comparison_pass":
            len(semantic) == PAIR_COUNT,
        "six_pair_focused_stage_comparison_pass":
            len(stage) == PAIR_COUNT
            and all(row["comparison_pass"] for row in stage),
        "stage_classification_complete": stage_complete,
        "previous_scan_identity_check_complete":
            len(stage) == PAIR_COUNT
            and all(row["previous_scan_identity_pass"] for row in stage),
        "formal_branch_reproduced": reproduced,
        "formal_branch_stage_localized": reproduced,
        "multiple_localized_divergence_modes":
            reproduced and len(classifications) > 1,
        "localized_classifications": classifications,
        "experiment_a_pass": day7,
        "day7_recommended": day7,
        "day7_recommended_scope": (
            recommended_scopes[0]
            if len(set(recommended_scopes)) == 1
            else (
                recommended_scopes
                if recommended_scopes else "NONE"
            )
        ),
        "day7_authorized": False,
        "input_pipeline_remediation_recommended":
            reproduced and input_mode,
        "focused_branch_status": (
            "FORMAL_BRANCH_STAGE_LOCALIZED"
            if reproduced
            else (
                "NOT_OBSERVED_IN_FOUR_FIXED_RUNS"
                if execution and not full_pairs
                else (
                    "FORMAL_BRANCH_OUTSIDE_FOCUSED_STAGE_WINDOW"
                    if full_pairs and not all_inside
                    else "EVIDENCE_GAP"
                )
            )
        ),
        "additional_replay_recommended": False,
        "additional_replay_authorized": False,
    }


def focused_run_completeness(summary: Mapping[str, Any]) -> dict[str, Any]:
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
        "focused_stage_records_pass": (
            int(summary.get("stage_hash_record_count", -1)) == 51
            and int(summary.get("stage_hash_first_scan", -1)) == 155
            and int(summary.get("stage_hash_last_scan", -1)) == 205
        ),
        "focused_snapshot_count_pass": (
            int(summary.get("map_before_snapshot_count", -1)) == 51
            and int(summary.get("map_after_snapshot_count", -1)) == 51
            and int(summary.get("coherent_snapshot_count", -1)) == 102
            and int(summary.get("incoherent_snapshot_count", -1)) == 0
        ),
        "cross_scan_coherence_pass": (
            int(summary.get("cross_scan_continuity_violation_count", -1))
            == 0
            and summary.get("map_snapshot_cross_scan_coherence_pass")
            is True
        ),
        "tap_writer_binary_pass": all(
            int(summary.get(name, -1)) == 0
            for name in (
                "tap_drop_count",
                "writer_error_count",
                "binary_checksum_failure_count",
                "truncated_record_count",
                "extra_trailing_bytes",
            )
        ),
        "immutability_pass": (
            int(summary.get("in_call_mutation_count", -1)) == 0
            and int(summary.get("diagnostic_mutation_count", -1)) == 0
        ),
        "schema_gt_pass": (
            int(summary.get("schema_rejected_record_count", -1)) == 0
            and int(summary.get("GT_TOPIC_CONSUMED_COUNT", -1)) == 0
        ),
        "lifecycle_pass": all(
            summary.get(name) is True for name in (
                "end_of_stream_drain_pass",
                "normal_shutdown_pass",
                "runtime_product_pass",
                "adjudicated_tail_handoff_pass",
            )
        ),
    }
    return {
        **checks,
        "run_completeness_pass":
            summary.get("complete") is True and all(checks.values()),
    }


def write_comparison(result: Mapping[str, Any], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    _csv(output / "pairwise_full_stream_semantic_comparison.csv",
         result["semantic_rows"])
    _json(output / "pairwise_full_stream_semantic_summary.json", {
        "schema_version": "focused_full_stream_semantic_summary_v1",
        "pair_count": len(result["semantic_summary"]),
        "pairs": result["semantic_summary"],
    })
    _csv(output / "pairwise_focused_stage_comparison.csv",
         result["stage_rows"])
    _json(output / "pairwise_focused_first_divergence.json", {
        "schema_version": "focused_first_divergence_v1",
        "pairs": [{
            "pair": row["pair"],
            "first_formal_divergence_scan":
                row["first_formal_divergence_scan"],
            "first_formal_divergence_stage":
                row["first_formal_divergence_stage"],
        } for row in result["stage_summary"]],
    })
    _json(output / "pairwise_focused_stage_classification.json", {
        "schema_version": "focused_stage_classification_v1",
        "pair_count": len(result["stage_summary"]),
        "pairs": result["stage_summary"],
    })
    _csv(output / "focused_divergence_previous_scan_identity.csv",
         result["previous_rows"])


def _json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("refusing empty focused comparison")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            value = dict(row)
            for key, item in value.items():
                if isinstance(item, (list, dict)):
                    value[key] = json.dumps(item, sort_keys=True)
            writer.writerow(value)
