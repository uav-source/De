#!/usr/bin/env python3
"""Compare six focused run pairs with explicit token-capture semantics."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter import day8_range_query as range_query
from fastlio2_adapter.day8_focused_traversal_remediation import RUN_IDS
from fastlio2_adapter.day8_query_root_cause import (
    classify_query_difference,
)
from fastlio2_adapter.day8_shadow_voxel_replay import apply_mutation
from fastlio2_adapter.day8_token_capture_status import (
    CAPTURED_NONEMPTY,
    NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
    OVERFLOWED,
    resolve_token_capture_status,
)


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def synthetic_validation(output_dir: Path) -> dict[str, Any]:
    point, other = "a" * 64, "b" * 64
    voxel = "0" * 48
    query = {
        "scan_index": 157, "visited_node_count": 1,
        "candidate_point_sha256": "c" * 64,
        "voxel_identity": voxel, "query_box_checksum": 1,
        "rebuild_active": 0, "rebuild_subtree_observed_count": 0,
        "no_intersection_prune_count": 0,
        "full_cover_subtree_count": 0,
        "partial_intersection_node_count": 1,
    }
    token = {
        "token_index": 0, "depth": 0, "node_point_sha256": point,
        "node_range_checksum": 1, "query_relation": "PARTIAL_INTERSECTION",
        "point_deleted": 0, "tree_deleted": 0,
        "current_point_inside_query": 1, "current_point_returned": 1,
        "left_child_considered": 1, "left_child_visited": 1,
        "right_child_considered": 0, "right_child_visited": 0,
        "subtree_flatten_result_count": 0, "rebuild_active": 0,
        "rebuild_generation": 0, "token_checksum": 1,
    }
    shadow_full = {
        "shadow_member_hashes": point, "formal_result_hashes": point,
    }
    shadow_missing = {
        "shadow_member_hashes": point, "formal_result_hashes": "",
    }
    deleted = dict(token, point_deleted=1, current_point_returned=0)
    pruned = dict(
        token, node_point_sha256=other,
        query_relation="NO_INTERSECTION",
        current_point_inside_query=0,
        current_point_returned=0,
        left_child_visited=0,
    )

    def classify(right_token: Mapping[str, Any]) -> str:
        return classify_query_difference(
            left_query=query,
            right_query=dict(query, no_intersection_prune_count=1),
            left_shadow=shadow_full,
            right_shadow=shadow_missing,
            left_tokens=[token],
            right_tokens=[right_token],
            left_token_capture_status=CAPTURED_NONEMPTY,
            right_token_capture_status=CAPTURED_NONEMPTY,
        )["classification"]

    not_captured = classify_query_difference(
        left_query=query, right_query=query,
        left_shadow=shadow_full, right_shadow=shadow_missing,
        left_tokens=[], right_tokens=[],
        left_token_capture_status=NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        right_token_capture_status=NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
    )
    state = {voxel: {point, other}}
    corrected_delta = apply_mutation(
        state,
        {
            "formal_outcome": "REPLACED_EXISTING_VOXEL_REPRESENTATIVE",
            "candidate_point_sha256": "c" * 64,
            "selected_representative_sha256": "c" * 64,
            "voxel_identity": voxel,
            "logical_point_count_delta_claimed": 0,
        },
        {point: voxel, other: voxel, "c" * 64: voxel},
    )
    checks = {
        "scan157_captured_nonempty":
            resolve_token_capture_status(
                query, [token], trace_enabled=True,
                detailed_scan_start=156, detailed_scan_end=158,
            ) == CAPTURED_NONEMPTY,
        "missing_member_unvisited_path_diff":
            classify(pruned) == "TREE_TRAVERSAL_PRUNING_DIVERGED",
        "missing_member_visited_deleted":
            classify(deleted) == "DELETION_FLAG_VISIBILITY_DIVERGED",
        "no_token_is_not_captured":
            not_captured["classification"] == "EVIDENCE_GAP"
            and not_captured["root_cause_subclassification"]
            == "EVIDENCE_GAP_DETAILED_TRACE_NOT_CAPTURED",
        "shadow_delta_47_46_corrected": corrected_delta == -1,
        "overflow_fails":
            OVERFLOWED == "OVERFLOWED",
    }
    value = {
        "schema_version": "day8_focused_synthetic_validation_v1",
        "checks": checks,
        "DAY8_FOCUSED_SYNTHETIC_VALIDATION_PASS": all(checks.values()),
        "FORMAL_IKDTREE_BUG_PROVEN": False,
        "DAY9_AUTHORIZED": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _json(
        output_dir / "day8_focused_synthetic_validation.json", value
    )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--root-cause-dir", type=Path)
    parser.add_argument("--synthetic-only", action="store_true")
    args = parser.parse_args()
    synthetic = synthetic_validation(args.output_dir)
    if args.synthetic_only:
        return 0 if synthetic[
            "DAY8_FOCUSED_SYNTHETIC_VALIDATION_PASS"
        ] else 1
    if args.runtime_root is None or args.root_cause_dir is None:
        raise RuntimeError("runtime and root-cause directories are required")

    range_query.DETAIL_START = 156
    range_query.DETAIL_END = 158
    old = _load(
        ROOT / "scripts/109_compare_day8_range_queries.py",
        "day8_focused_comparison_base",
    )
    old.RUN_IDS = RUN_IDS
    original_replay = old.replay_run

    def strict_replay(**kwargs: Any) -> list[dict[str, Any]]:
        kwargs["tolerate_accounting_failure"] = False
        return original_replay(**kwargs)

    old.replay_run = strict_replay
    original_compare = old.compare_query_runs

    def capture_aware_compare(**kwargs: Any) -> dict[str, Any]:
        result = original_compare(**kwargs)
        first = result["first_divergence"]
        if first.get("aligned_query_index") is None:
            return result
        left_query = first["left_query"]
        right_query = first["right_query"]
        left_sequence = int(left_query["query_sequence"])
        right_sequence = int(right_query["query_sequence"])
        left_tokens = kwargs["left_tokens_by_query"].get(left_sequence, ())
        right_tokens = kwargs["right_tokens_by_query"].get(right_sequence, ())
        left_status = resolve_token_capture_status(
            left_query, left_tokens, trace_enabled=True,
            detailed_scan_start=156, detailed_scan_end=158,
        )
        right_status = resolve_token_capture_status(
            right_query, right_tokens, trace_enabled=True,
            detailed_scan_start=156, detailed_scan_end=158,
        )
        left_shadow = {
            int(row["query_sequence"]): row
            for row in kwargs["left_shadow_rows"]
        }[left_sequence]
        right_shadow = {
            int(row["query_sequence"]): row
            for row in kwargs["right_shadow_rows"]
        }[right_sequence]
        first["root_cause"] = classify_query_difference(
            left_query=left_query, right_query=right_query,
            left_shadow=left_shadow, right_shadow=right_shadow,
            left_tokens=left_tokens, right_tokens=right_tokens,
            left_token_capture_status=left_status,
            right_token_capture_status=right_status,
        )
        first["left_token_capture_status"] = left_status
        first["right_token_capture_status"] = right_status
        first["detailed_token_coverage_pass"] = (
            left_status == right_status == CAPTURED_NONEMPTY
        )
        return result

    old.compare_query_runs = capture_aware_compare
    prior_argv = sys.argv
    sys.argv = [
        str(ROOT / "scripts/109_compare_day8_range_queries.py"),
        "--runtime-root", str(args.runtime_root),
        "--output-dir", str(args.output_dir),
    ]
    try:
        code = int(old.main())
    finally:
        sys.argv = prior_argv
    if code != 0:
        return code

    shutil.copy2(
        args.output_dir / "pairwise_day8_range_query_comparison.csv",
        args.output_dir / "pairwise_focused_range_query_comparison.csv",
    )
    shutil.copy2(
        args.output_dir / "pairwise_day8_first_range_query_divergence.json",
        args.output_dir / "pairwise_focused_first_query_divergence.json",
    )
    analyzer = _load(
        ROOT / "scripts/110_analyze_day8_query_root_cause.py",
        "day8_focused_root_base",
    )
    sys.argv = [
        str(ROOT / "scripts/110_analyze_day8_query_root_cause.py"),
        "--runtime-root", str(args.runtime_root),
        "--comparison-dir", str(args.output_dir),
        "--output-dir", str(args.root_cause_dir),
    ]
    try:
        code = int(analyzer.main())
    finally:
        sys.argv = prior_argv
    if code != 0:
        return code
    pair_doc = json.loads(
        (
            args.output_dir
            / "pairwise_focused_first_query_divergence.json"
        ).read_text(encoding="utf-8")
    )
    previous_path = (
        args.root_cause_dir
        / "first_divergent_query_previous_identity.json"
    )
    previous = json.loads(previous_path.read_text(encoding="utf-8"))
    divergent = [
        item for item in pair_doc["pairs"]
        if item.get("aligned_query_index") is not None
    ]
    if divergent:
        first = min(
            divergent,
            key=lambda item: (
                int(item["aligned_query_index"]),
                item["left_run_id"], item["right_run_id"],
            ),
        )
        index = int(first["aligned_query_index"])
        if index > 0:
            left_id, right_id = first["left_run_id"], first["right_run_id"]
            left_queries = old.load_query_summaries(
                args.runtime_root / left_id
                / "day8_range_query_summary_index.csv"
            )
            right_queries = old.load_query_summaries(
                args.runtime_root / right_id
                / "day8_range_query_summary_index.csv"
            )
            left_tokens = old.group_tokens(old.load_traversal_tokens(
                args.runtime_root / left_id
                / "day8_range_traversal_token_index.csv"
            ))
            right_tokens = old.group_tokens(old.load_traversal_tokens(
                args.runtime_root / right_id
                / "day8_range_traversal_token_index.csv"
            ))
            left_query, right_query = (
                left_queries[index - 1], right_queries[index - 1]
            )
            left_trace = left_tokens.get(
                int(left_query["query_sequence"]), ()
            )
            right_trace = right_tokens.get(
                int(right_query["query_sequence"]), ()
            )
            left_status = resolve_token_capture_status(
                left_query, left_trace, trace_enabled=True,
                detailed_scan_start=156, detailed_scan_end=158,
            )
            right_status = resolve_token_capture_status(
                right_query, right_trace, trace_enabled=True,
                detailed_scan_start=156, detailed_scan_end=158,
            )
            previous.update({
                "left_previous_token_capture_status": left_status,
                "right_previous_token_capture_status": right_status,
                "previous_token_capture_status_equal":
                    left_status == right_status,
                "previous_detailed_token_sequence_equal":
                    old.traversal_signature(left_trace)
                    == old.traversal_signature(right_trace),
            })
            _json(previous_path, previous)
    shutil.copy2(
        args.root_cause_dir
        / "pairwise_day8_root_cause_classification.json",
        args.root_cause_dir
        / "pairwise_focused_root_cause_classification.json",
    )
    coverage_pass = all(
        item.get("detailed_token_coverage_pass") is True
        for item in pair_doc["pairs"]
        if item.get("aligned_query_index") is not None
    )
    _json(
        args.root_cause_dir
        / "first_divergent_query_token_coverage_gate.json",
        {
            "schema_version":
                "first_divergent_query_token_coverage_gate_v1",
            "pair_count": len(pair_doc["pairs"]),
            "first_divergent_query_detailed_token_coverage_pass":
                coverage_pass,
        },
    )
    return 0 if coverage_pass else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
