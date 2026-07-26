"""Frozen constants, coverage, and gates for Day 8 extended token capture."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .day8_token_capture_status import (
    CAPTURED_NONEMPTY,
    FATAL_CAPTURE_STATUSES,
    resolve_token_capture_status,
    status_counts,
)


QUERY_SUMMARY_SCAN_START = 155
QUERY_SUMMARY_SCAN_END = 165
DETAILED_TOKEN_SCAN_START = 156
DETAILED_TOKEN_SCAN_END = 163
MAIN_RUN_ID = "multihyp_day8_extended_detailed_token_window_v1"
RUN_IDS = tuple(
    "multihyp_day8_extended_token_r%d" % index
    for index in range(1, 5)
)
ROS_MASTER_PORTS = {
    run_id: 20811 + index for index, run_id in enumerate(RUN_IDS)
}


def in_detailed_window(scan_index: int) -> bool:
    return DETAILED_TOKEN_SCAN_START <= scan_index <= DETAILED_TOKEN_SCAN_END


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
            "batch_id": query["batch_id"],
            "batch_point_index": int(query["batch_point_index"]),
            "candidate_point_sha256": query["candidate_point_sha256"],
            "voxel_identity": query["voxel_identity"],
            "query_box_checksum": int(query["query_box_checksum"]),
            "visited_node_count": int(query["visited_node_count"]),
            "token_count": len(tokens),
            "token_capture_status": status,
        })

    def scan_summary(scan: int) -> dict[str, Any]:
        selected = [row for row in rows if row["scan_index"] == scan]
        captured = sum(
            row["token_capture_status"] == CAPTURED_NONEMPTY
            for row in selected
        )
        return {
            "query_count": len(selected),
            "query_with_summary_count": len(selected),
            "query_with_detailed_token_count": captured,
            "token_capture_status_counts": status_counts([
                row["token_capture_status"] for row in selected
            ]),
            "token_coverage_pass": bool(selected) and captured == len(selected),
        }

    scan157 = scan_summary(157)
    scan162 = scan_summary(162)
    fatal = sum(
        row["token_capture_status"] in FATAL_CAPTURE_STATUSES for row in rows
    )
    summary = {
        "schema_version": "day8_extended_token_capture_coverage_summary_v2",
        "token_semantics_version": "TOKEN_CAPTURE_SEMANTICS_V2",
        "query_count": len(rows),
        "query_with_summary_count": len(rows),
        "query_with_detailed_token_count": sum(
            row["token_capture_status"] == CAPTURED_NONEMPTY for row in rows
        ),
        "token_capture_status_counts": status_counts([
            row["token_capture_status"] for row in rows
        ]),
        "scan157_query_count": scan157["query_count"],
        "scan157_query_with_summary_count":
            scan157["query_with_summary_count"],
        "scan157_query_with_detailed_token_count":
            scan157["query_with_detailed_token_count"],
        "scan157_token_capture_status_counts":
            scan157["token_capture_status_counts"],
        "scan157_token_coverage_pass": scan157["token_coverage_pass"],
        "scan162_query_count": scan162["query_count"],
        "scan162_query_with_summary_count":
            scan162["query_with_summary_count"],
        "scan162_query_with_detailed_token_count":
            scan162["query_with_detailed_token_count"],
        "scan162_token_capture_status_counts":
            scan162["token_capture_status_counts"],
        "scan162_token_coverage_pass": scan162["token_coverage_pass"],
        "token_capture_failure_count": fatal,
        "unclassified_token_count": 0,
    }
    return rows, summary


def write_coverage(
    run_dir: Path,
    rows: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> None:
    if not rows:
        raise ValueError("refusing empty token coverage output")
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


def evaluate_extended_gate(**checks: bool) -> dict[str, Any]:
    required = {
        "authorization_pass",
        "targeted_test_pass",
        "full_test_pass",
        "synthetic_pass",
        "fast_source_lock_pass",
        "fast_binary_lock_pass",
        "formal_logic_unchanged_pass",
        "four_replay_runs_complete_pass",
        "observation_binary_integrity_pass",
        "map_snapshot_coherence_pass",
        "day7_mutation_trace_reuse_pass",
        "range_query_summary_capture_pass",
        "range_traversal_token_capture_pass",
        "scan157_token_coverage_pass",
        "scan162_token_coverage_pass",
        "query_trace_overflow_pass",
        "query_trace_schema_pass",
        "shadow_logical_voxel_replay_pass",
        "shadow_state_accounting_pass",
        "six_pair_range_query_comparison_pass",
        "previous_query_identity_check_complete",
        "first_divergent_query_detailed_token_coverage_pass",
        "missing_expected_point_witness_pass",
        "root_cause_classification_complete",
        "null_token_semantics_fully_propagated_pass",
        "offline_analysis_lock_pass",
        "diagnostic_immutability_pass",
        "no_tap_drop_pass",
        "no_writer_error_pass",
        "no_gt_pass",
        "diff_scope_pass",
        "audit_package_scope_pass",
    }
    missing = sorted(required - set(checks))
    extra = sorted(set(checks) - required)
    if missing or extra:
        raise ValueError(
            "extended gate fields mismatch: missing=%r extra=%r"
            % (missing, extra)
        )
    execution_pass = all(checks.values())
    return {
        "schema_version": "day8_extended_token_window_final_gate_v1",
        "checks": dict(sorted(checks.items())),
        "DAY8_EXTENDED_TOKEN_WINDOW_EXECUTION_PASS": execution_pass,
        "FORMAL_IKDTREE_BUG_PROVEN": False,
        "DATA_RACE_PROVEN": False,
        "DAY9_AUTHORIZED": False,
        "STAGE3_START_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
    }


__all__ = [
    "DETAILED_TOKEN_SCAN_END",
    "DETAILED_TOKEN_SCAN_START",
    "MAIN_RUN_ID",
    "QUERY_SUMMARY_SCAN_END",
    "QUERY_SUMMARY_SCAN_START",
    "ROS_MASTER_PORTS",
    "RUN_IDS",
    "evaluate_extended_gate",
    "in_detailed_window",
    "token_capture_coverage",
    "write_coverage",
]
