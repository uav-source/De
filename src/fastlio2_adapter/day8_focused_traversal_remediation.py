"""Frozen offline helpers for the Day 8 focused traversal remediation."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
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
DETAILED_TOKEN_SCAN_END = 158
RUN_IDS = tuple(
    f"multihyp_day8_focused_traversal_r{index}" for index in range(1, 5)
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
            query, tokens,
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
    scan157 = [row for row in rows if row["scan_index"] == 157]
    fatal = sum(
        row["token_capture_status"] in FATAL_CAPTURE_STATUSES for row in rows
    )
    summary = {
        "schema_version": "day8_token_capture_coverage_summary_v1",
        "query_count": len(rows),
        "query_with_summary_count": len(rows),
        "query_with_detailed_token_count": sum(row["token_count"] > 0 for row in rows),
        "token_capture_status_counts": status_counts(
            [row["token_capture_status"] for row in rows]
        ),
        "scan157_query_count": len(scan157),
        "scan157_query_with_summary_count": len(scan157),
        "scan157_query_with_detailed_token_count":
            sum(row["token_count"] > 0 for row in scan157),
        "scan157_token_capture_status_counts": status_counts(
            [row["token_capture_status"] for row in scan157]
        ),
        "scan157_token_coverage_pass": bool(scan157) and all(
            row["token_capture_status"] == CAPTURED_NONEMPTY for row in scan157
        ),
        "token_capture_failure_count": fatal,
        "unclassified_token_count": 0,
    }
    return rows, summary


def write_coverage(
    run_dir: Path,
    rows: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> None:
    with (run_dir / "day8_token_capture_coverage.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (run_dir / "day8_token_capture_coverage_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def evaluate_focused_gate(
    *,
    authorization_pass: bool,
    shadow_adjudication_pass: bool,
    targeted_test_pass: bool,
    full_test_pass: bool,
    fast_source_lock_pass: bool,
    fast_binary_lock_pass: bool,
    formal_logic_unchanged_pass: bool,
    synthetic_pass: bool,
    run_complete_pass: bool,
    scan157_coverage_pass: bool,
    shadow_accounting_pass: bool,
    six_pair_pass: bool,
    previous_identity_pass: bool,
    first_divergence_coverage_pass: bool,
    witness_pass: bool,
    classification_complete: bool,
    offline_analysis_lock_pass: bool,
    immutable_pass: bool,
    no_tap_drop_pass: bool,
    no_writer_error_pass: bool,
    no_gt_pass: bool,
    diff_scope_pass: bool,
    audit_scope_pass: bool,
) -> dict[str, Any]:
    checks = dict(locals())
    execution_pass = all(checks.values())
    return {
        "schema_version": "day8_focused_traversal_final_gate_v1",
        "checks": checks,
        "DAY8_FOCUSED_TRAVERSAL_EXECUTION_PASS": execution_pass,
        "FORMAL_IKDTREE_BUG_PROVEN": False,
        "DATA_RACE_PROVEN": False,
        "DAY9_AUTHORIZED": False,
        "STAGE3_START_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
    }
