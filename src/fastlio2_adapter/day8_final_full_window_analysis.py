"""Frozen analysis and gate helpers for the final Day 8 replay batch."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .day8_strict_query_identity_v2 import (
    STRICT_QUERY_IDENTITY_SCHEMA_VERSION,
    align_strict_query_streams,
    compare_formal_members,
    identity_document,
    identity_sha256,
    member_multiset,
    public_alignment,
    strict_query_identity,
)
from .day8_token_capture_status import (
    CAPTURED_EMPTY_FORMAL_QUERY,
    CAPTURED_NONEMPTY,
    FATAL_CAPTURE_STATUSES,
    resolve_token_capture_status,
    status_counts,
)
from .day8_token_semantics_v3 import (
    TOKEN_CAPTURE_SEMANTICS_VERSION,
    compare_token_sequences,
)


QUERY_SUMMARY_SCAN_START = 155
QUERY_SUMMARY_SCAN_END = 165
DETAILED_TOKEN_SCAN_START = 155
DETAILED_TOKEN_SCAN_END = 165
MAIN_RUN_ID = "multihyp_day8_final_full_window_reproduction_v1"
RUN_IDS = tuple(
    f"multihyp_day8_final_full_window_r{index}" for index in range(1, 5)
)
ROS_MASTER_PORTS = {
    run_id: 20911 + index for index, run_id in enumerate(RUN_IDS)
}
PAIR_NAMES = tuple(
    (RUN_IDS[left], RUN_IDS[right])
    for left in range(len(RUN_IDS))
    for right in range(left + 1, len(RUN_IDS))
)


def token_capture_coverage(
    queries: Sequence[Mapping[str, Any]],
    tokens_by_query: Mapping[int, Sequence[Mapping[str, Any]]],
    *,
    trace_enabled: bool = True,
    capture_failure_count: int = 0,
    overflow_count: int = 0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query in queries:
        sequence = int(query["query_sequence"])
        tokens = tokens_by_query.get(sequence, ())
        status = resolve_token_capture_status(
            query,
            tokens,
            trace_enabled=trace_enabled,
            detailed_scan_start=DETAILED_TOKEN_SCAN_START,
            detailed_scan_end=DETAILED_TOKEN_SCAN_END,
            capture_failed=capture_failure_count > 0,
            overflowed=overflow_count > 0,
        )
        rows.append({
            "run_id": query["run_id"],
            "query_sequence": sequence,
            "scan_index": int(query["scan_index"]),
            "call_index": int(query["map_mutation_call_index"]),
            "batch_id": str(query["batch_id"]),
            "batch_point_index": int(query["batch_point_index"]),
            "candidate_point_sha256": query["candidate_point_sha256"],
            "voxel_identity": query["voxel_identity"],
            "query_box_checksum": int(query["query_box_checksum"]),
            "visited_node_count": int(query["visited_node_count"]),
            "token_count": len(tokens),
            "token_capture_status": status,
        })
    per_scan: dict[str, Any] = {}
    for scan in range(QUERY_SUMMARY_SCAN_START, QUERY_SUMMARY_SCAN_END + 1):
        selected = [row for row in rows if row["scan_index"] == scan]
        captured = sum(
            row["token_capture_status"] in {
                CAPTURED_NONEMPTY, CAPTURED_EMPTY_FORMAL_QUERY
            }
            for row in selected
        )
        per_scan[str(scan)] = {
            "query_count": len(selected),
            "query_with_summary_count": len(selected),
            "query_with_detailed_token_count": captured,
            "token_capture_status_counts": status_counts(
                [row["token_capture_status"] for row in selected]
            ),
            "token_coverage_pass": bool(selected) and captured == len(selected),
        }
    fatal_count = sum(
        row["token_capture_status"] in FATAL_CAPTURE_STATUSES for row in rows
    )
    full_pass = (
        all(value["token_coverage_pass"] for value in per_scan.values())
        and fatal_count == 0
    )
    summary = {
        "schema_version": "day8_final_full_window_token_coverage_v1",
        "token_semantics_version": TOKEN_CAPTURE_SEMANTICS_VERSION,
        "query_summary_window": [
            QUERY_SUMMARY_SCAN_START, QUERY_SUMMARY_SCAN_END
        ],
        "detailed_token_window": [
            DETAILED_TOKEN_SCAN_START, DETAILED_TOKEN_SCAN_END
        ],
        "query_count": len(rows),
        "query_with_summary_count": len(rows),
        "query_with_detailed_token_count": sum(
            row["token_capture_status"] in {
                CAPTURED_NONEMPTY, CAPTURED_EMPTY_FORMAL_QUERY
            }
            for row in rows
        ),
        "token_capture_status_counts": status_counts(
            [row["token_capture_status"] for row in rows]
        ),
        "per_scan": per_scan,
        "token_capture_failure_count": fatal_count,
        "unclassified_token_count": 0,
        "FULL_WINDOW_QUERY_SUMMARY_COVERAGE_PASS": full_pass,
        "FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS": full_pass,
    }
    return rows, summary


def write_coverage(
    run_dir: Path,
    rows: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> None:
    if not rows:
        raise ValueError("refusing empty full-window coverage output")
    with (run_dir / "day8_token_capture_coverage_by_scan.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (run_dir / "day8_token_capture_coverage_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _shadow_by_identity(
    queries: Sequence[Mapping[str, Any]],
    shadow_rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[Any, ...], Mapping[str, Any]]:
    by_sequence = {
        int(row["query_sequence"]): row for row in shadow_rows
    }
    return {
        strict_query_identity(query): by_sequence[int(query["query_sequence"])]
        for query in queries
    }


def _shadow_members(row: Mapping[str, Any]) -> tuple[str, ...]:
    return member_multiset(row, "shadow_member_hashes")


def _formal_members(row: Mapping[str, Any]) -> tuple[str, ...]:
    return member_multiset(row, "formal_result_hashes")


def compare_strict_pair(
    *,
    left_run_id: str,
    right_run_id: str,
    left_queries: Sequence[Mapping[str, Any]],
    right_queries: Sequence[Mapping[str, Any]],
    left_shadow_rows: Sequence[Mapping[str, Any]],
    right_shadow_rows: Sequence[Mapping[str, Any]],
    left_tokens_by_query: Mapping[int, Sequence[Mapping[str, Any]]],
    right_tokens_by_query: Mapping[int, Sequence[Mapping[str, Any]]],
    left_status_by_query: Mapping[int, str],
    right_status_by_query: Mapping[int, str],
) -> dict[str, Any]:
    alignment = align_strict_query_streams(left_queries, right_queries)
    left_index = alignment["_left_index"]
    right_index = alignment["_right_index"]
    left_shadow = _shadow_by_identity(left_queries, left_shadow_rows)
    right_shadow = _shadow_by_identity(right_queries, right_shadow_rows)
    rows: list[dict[str, Any]] = []
    first_valid: dict[str, Any] | None = None
    left_stream = alignment["_left_stream"]
    right_stream = alignment["_right_stream"]
    for identity in alignment["_common_identities"]:
        left = left_index[identity]
        right = right_index[identity]
        left_sequence = int(left["query_sequence"])
        right_sequence = int(right["query_sequence"])
        token = compare_token_sequences(
            left_status_by_query[left_sequence],
            right_status_by_query[right_sequence],
            left_tokens_by_query.get(left_sequence, ()),
            right_tokens_by_query.get(right_sequence, ()),
        )
        formal = compare_formal_members(left, right)
        shadow_equal = (
            _shadow_members(left_shadow[identity])
            == _shadow_members(right_shadow[identity])
        )
        if not shadow_equal:
            classification = "SHADOW_LOGICAL_VOXEL_MEMBERSHIP_DIVERGED"
        elif token["token_comparison_status"] != "APPLICABLE":
            classification = "EVIDENCE_GAP"
        elif not formal["formal_member_multiset_equal"]:
            classification = "STRICT_IDENTITY_FORMAL_MEMBER_SET_DIVERGED"
        elif not formal["formal_result_order_equal"]:
            classification = "FORMAL_RESULT_ORDER_DIVERGED_SET_EQUAL"
        elif token["token_sequence_equal"] is False:
            classification = "TREE_SHAPE_DIFFERED_BUT_RESULT_COMPLETE"
        else:
            classification = (
                "NO_STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED"
            )
        left_position = left_stream.index(identity)
        right_position = right_stream.index(identity)
        unexplained_before = not (
            left_position == right_position
            and left_stream[:left_position] == right_stream[:right_position]
        )
        row = {
            "left_run_id": left_run_id,
            "right_run_id": right_run_id,
            "strict_identity_sha256": identity_sha256(identity),
            **identity_document(identity),
            "left_query_sequence": left_sequence,
            "right_query_sequence": right_sequence,
            "left_stream_position": left_position,
            "right_stream_position": right_position,
            "identity_stream_diverged_before_query": unexplained_before,
            "shadow_member_multiset_equal": shadow_equal,
            "left_shadow_member_count": len(_shadow_members(left_shadow[identity])),
            "right_shadow_member_count": len(
                _shadow_members(right_shadow[identity])
            ),
            **formal,
            **token,
            "classification": (
                token["classification"]
                if token["classification"] == "EVIDENCE_GAP"
                else classification
            ),
        }
        rows.append(row)
        if (
            first_valid is None
            and classification == "STRICT_IDENTITY_FORMAL_MEMBER_SET_DIVERGED"
            and shadow_equal
            and token["token_comparison_status"] == "APPLICABLE"
            and not unexplained_before
        ):
            first_valid = {
                **row,
                "identity": identity_document(identity),
                "left_query": dict(left),
                "right_query": dict(right),
                "left_shadow_members": list(_shadow_members(left_shadow[identity])),
                "right_shadow_members": list(
                    _shadow_members(right_shadow[identity])
                ),
                "left_formal_members": list(_formal_members(left_shadow[identity])),
                "right_formal_members": list(
                    _formal_members(right_shadow[identity])
                ),
            }
    strict_count = sum(
        row["classification"] == "STRICT_IDENTITY_FORMAL_MEMBER_SET_DIVERGED"
        for row in rows
    )
    order_count = sum(
        row["classification"] == "FORMAL_RESULT_ORDER_DIVERGED_SET_EQUAL"
        for row in rows
    )
    if alignment["common_identity_count"] == 0:
        root = "NO_STRICT_QUERY_IDENTITY_OVERLAP"
    elif first_valid is not None:
        root = "FORMAL_RANGE_SEARCH_RESULT_INCOMPLETE_WITH_MATCHED_LOGICAL_MEMBERSHIP"
    elif not alignment["identity_stream_equal"]:
        root = "QUERY_STREAM_IDENTITY_DIVERGED"
    else:
        root = "NO_STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED"
    return {
        "schema_version": "day8_final_strict_pair_comparison_v1",
        "strict_identity_schema_version": STRICT_QUERY_IDENTITY_SCHEMA_VERSION,
        "token_semantics_version": TOKEN_CAPTURE_SEMANTICS_VERSION,
        "left_run_id": left_run_id,
        "right_run_id": right_run_id,
        "identity_stream_summary": public_alignment(alignment),
        "strict_identity_formal_member_set_divergence_count": strict_count,
        "formal_result_order_only_divergence_count": order_count,
        "first_strict_formal_member_set_divergence": first_valid,
        "root_cause_classification": root,
        "rows": rows,
    }


FINAL_GATE_REQUIRED = {
    "authorization_pass",
    "strict_query_identity_v2_pass",
    "null_token_semantics_v3_pass",
    "null_token_semantics_fully_propagated_pass",
    "plot_input_contract_pass",
    "targeted_test_pass",
    "full_test_pass",
    "synthetic_validation_pass",
    "fast_source_lock_pass",
    "fast_binary_lock_pass",
    "formal_range_search_logic_unchanged_pass",
    "fast_source_unmodified_pass",
    "fast_build_not_run_pass",
    "four_replay_runs_complete_pass",
    "observation_binary_integrity_pass",
    "map_snapshot_coherence_pass",
    "day7_mutation_trace_reuse_pass",
    "full_window_query_summary_coverage_pass",
    "full_window_detailed_token_coverage_pass",
    "query_trace_overflow_pass",
    "query_trace_schema_pass",
    "shadow_logical_voxel_replay_pass",
    "shadow_state_accounting_pass",
    "six_pair_strict_identity_comparison_pass",
    "previous_query_identity_check_complete",
    "root_cause_classification_complete",
    "offline_analysis_lock_pass",
    "offline_analysis_code_unchanged_after_runtime_lock_pass",
    "diagnostic_immutability_pass",
    "no_tap_drop_pass",
    "no_writer_error_pass",
    "no_gt_pass",
    "diff_scope_pass",
    "audit_package_scope_pass",
}


def evaluate_final_gate(**checks: bool) -> dict[str, Any]:
    missing = sorted(FINAL_GATE_REQUIRED - set(checks))
    extra = sorted(set(checks) - FINAL_GATE_REQUIRED)
    if missing or extra:
        raise ValueError(f"final gate fields mismatch: missing={missing} extra={extra}")
    execution_pass = all(checks.values())
    return {
        "schema_version": "day8_final_full_window_gate_v1",
        "checks": dict(sorted(checks.items())),
        "DAY8_FINAL_FULL_WINDOW_EXECUTION_PASS": execution_pass,
        "FORMAL_IKDTREE_BUG_PROVEN": False,
        "DATA_RACE_PROVEN": False,
        "DAY9_AUTHORIZED": False,
        "STAGE3_START_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
    }


__all__ = [
    "DETAILED_TOKEN_SCAN_END",
    "DETAILED_TOKEN_SCAN_START",
    "FINAL_GATE_REQUIRED",
    "MAIN_RUN_ID",
    "PAIR_NAMES",
    "QUERY_SUMMARY_SCAN_END",
    "QUERY_SUMMARY_SCAN_START",
    "ROS_MASTER_PORTS",
    "RUN_IDS",
    "compare_strict_pair",
    "evaluate_final_gate",
    "token_capture_coverage",
    "write_coverage",
]
