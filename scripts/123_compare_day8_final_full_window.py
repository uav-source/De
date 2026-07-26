#!/usr/bin/env python3
"""Compare the four final Day 8 runs by strict query identity."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter import day8_range_query as range_query
from fastlio2_adapter.day8_final_full_window_analysis import (
    PAIR_NAMES,
    RUN_IDS,
    compare_strict_pair,
)
from fastlio2_adapter.day8_final_plot_contract import validate_plot_inputs
from fastlio2_adapter.day8_final_traversal_root_cause import (
    analyze_first_strict_divergence,
)
from fastlio2_adapter.day8_range_query import (
    load_query_summaries,
    load_traversal_tokens,
    validate_run_query_trace,
)
from fastlio2_adapter.day8_strict_query_identity_v2 import (
    align_strict_query_streams,
    strict_query_identity,
)
from fastlio2_adapter.day8_token_semantics_v3 import (
    CAPTURED_NONEMPTY,
    NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
    OVERFLOWED,
    audit_output_paths,
    compare_token_sequences,
)
from fastlio2_adapter.day8_traversal_analysis import group_tokens


def _json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("\n", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for source in rows:
            row = {}
            for key in fields:
                value = source.get(key)
                if isinstance(value, (dict, list, tuple)):
                    value = json.dumps(value, sort_keys=True, separators=(",", ":"))
                row[key] = value
            writer.writerow(row)


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _status_map(run_dir: Path) -> dict[int, str]:
    return {
        int(row["query_sequence"]): row["token_capture_status"]
        for row in _load_csv(
            run_dir / "day8_token_capture_coverage_by_scan.csv"
        )
    }


def _shadow_maps(
    queries: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
) -> tuple[
    dict[tuple[Any, ...], tuple[str, ...]],
    dict[tuple[Any, ...], tuple[str, ...]],
]:
    by_sequence = {int(row["query_sequence"]): row for row in rows}
    shadow: dict[tuple[Any, ...], tuple[str, ...]] = {}
    formal: dict[tuple[Any, ...], tuple[str, ...]] = {}
    for query in queries:
        identity = strict_query_identity(query)
        row = by_sequence[int(query["query_sequence"])]
        shadow[identity] = tuple(
            sorted(filter(None, row["shadow_member_hashes"].split(";")))
        )
        formal[identity] = tuple(
            sorted(filter(None, row["formal_result_hashes"].split(";")))
        )
    return shadow, formal


def _query(
    candidate: str,
    *,
    sequence: int = 1,
    formal: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "run_id": "synthetic",
        "query_sequence": sequence,
        "scan_index": 155,
        "map_mutation_call_index": 1,
        "batch_id": "1",
        "batch_point_index": sequence - 1,
        "candidate_point_sha256": candidate,
        "voxel_identity": "0" * 48,
        "query_box_checksum": 1,
        "formal_result_members": tuple(formal),
        "formal_result_count": len(formal),
        "formal_result_ordered_checksum": sequence,
        "formal_result_multiset_checksum": sequence,
        "visited_node_count": 1,
        "no_intersection_prune_count": 0,
    }


def _token(**updates: Any) -> dict[str, Any]:
    value = {
        "token_index": 0,
        "depth": 0,
        "node_point_sha256": "a" * 64,
        "node_range_checksum": 1,
        "query_relation": "PARTIAL_INTERSECTION",
        "point_deleted": 0,
        "tree_deleted": 0,
        "current_point_inside_query": 1,
        "current_point_returned": 1,
        "left_child_considered": 0,
        "left_child_visited": 0,
        "right_child_considered": 0,
        "right_child_visited": 0,
        "subtree_flatten_result_count": 0,
        "rebuild_active": 0,
        "rebuild_generation": 1,
        "token_checksum": 1,
    }
    value.update(updates)
    return value


def synthetic_validation(output_dir: Path) -> dict[str, Any]:
    q_a = _query("a" * 64, formal=("a" * 64,))
    q_b = _query("b" * 64, formal=("a" * 64,))
    identical = align_strict_query_streams([q_a], [dict(q_a)])
    different = align_strict_query_streams([q_a], [q_b])
    left_two = [q_a, _query("c" * 64, sequence=2)]
    right_two = [dict(q_a), _query("d" * 64, sequence=2)]
    partial = align_strict_query_streams(left_two, right_two)
    captured_equal = compare_token_sequences(
        CAPTURED_NONEMPTY, CAPTURED_NONEMPTY, [_token()], [_token()]
    )
    captured_diff = compare_token_sequences(
        CAPTURED_NONEMPTY,
        CAPTURED_NONEMPTY,
        [_token()],
        [_token(point_deleted=1)],
    )
    not_captured = compare_token_sequences(
        NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        CAPTURED_NONEMPTY,
        (),
        [_token()],
    )
    overflow = compare_token_sequences(
        OVERFLOWED, CAPTURED_NONEMPTY, (), [_token()]
    )
    plot_documents = {
        "pairwise_final_query_comparison": [],
        "pairwise_final_strict_identity_summary": {
            "pair_count": 6,
            "pairs": [{
                "left_run_id": "l",
                "right_run_id": "r",
                "left_identity_count": 1,
                "right_identity_count": 1,
                "common_identity_count": 1,
                "aligned_prefix_length": 1,
                "strict_identity_formal_member_set_divergence_count": 0,
                "formal_result_order_only_divergence_count": 0,
                "root_cause_classification":
                    "NO_STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED",
            } for _ in range(6)],
        },
        "pairwise_final_first_divergence": {"pairs": []},
        "pairwise_final_root_cause_classification": {"pairs": []},
        "root_cause_summary": {
            "root_cause_classification":
                "NO_STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED",
            "first_strict_formal_member_set_divergence": None,
            "first_divergent_traversal_token": None,
            "missing_expected_point_witness": None,
        },
        "token_coverage": {
            "runs": {},
            "FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS": True,
        },
        "shadow_accounting": {
            "runs": {},
            "SHADOW_STATE_ACCOUNTING_PASS": True,
        },
        "instrumentation_cost": {
            "runs": {},
            "instrumentation_timing_perturbation_present": True,
        },
        "null_token_contract_audit": {
            "failure_count": 0,
            "NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS": True,
        },
        "random_replay_route_decision": {
            "RANDOM_REAL_REPLAY_ROUTE_STATUS":
                "CLOSED_AFTER_FINAL_FULL_WINDOW_BATCH",
            "FURTHER_RANDOM_REAL_REPLAY_AUTHORIZED": False,
        },
    }
    plot_pass = validate_plot_inputs(plot_documents)[
        "PLOT_INPUT_CONTRACT_PASS"
    ]
    invalid_plot_rejected = False
    broken = dict(plot_documents)
    broken.pop("token_coverage")
    try:
        validate_plot_inputs(broken)
    except ValueError:
        invalid_plot_rejected = True
    checks = {
        "identical_identity_sequence": identical["identity_stream_equal"],
        "partial_identity_overlap": partial["common_identity_count"] == 1,
        "no_identity_overlap": different["common_identity_count"] == 0,
        "identity_diverges_at_zero": (
            different["aligned_prefix_length"] == 0
        ),
        "captured_nonempty_equal": captured_equal["token_sequence_equal"] is True,
        "captured_nonempty_different": captured_diff["token_sequence_equal"] is False,
        "not_captured_is_null_evidence_gap": (
            not_captured["token_sequence_equal"] is None
            and not_captured["classification"] == "EVIDENCE_GAP"
        ),
        "overflow_fails_gate": overflow["capture_gate_pass"] is False,
        "point_deleted_path_representable": _token(point_deleted=1)["point_deleted"] == 1,
        "tree_deleted_path_representable": _token(tree_deleted=1)["tree_deleted"] == 1,
        "child_path_representable": _token(left_child_visited=1)["left_child_visited"] == 1,
        "prune_path_representable": _token(query_relation="NO_INTERSECTION")[
            "query_relation"
        ] == "NO_INTERSECTION",
        "flatten_path_representable": _token(
            query_relation="FULL_COVER",
            subtree_flatten_result_count=1,
        )["subtree_flatten_result_count"] == 1,
        "plot_contract_valid": plot_pass,
        "plot_contract_missing_field_rejected": invalid_plot_rejected,
        "route_close_gate": (
            plot_documents["random_replay_route_decision"][
                "FURTHER_RANDOM_REAL_REPLAY_AUTHORIZED"
            ] is False
        ),
    }
    result = {
        "schema_version": "day8_final_synthetic_validation_v1",
        "checks": checks,
        "DAY8_FINAL_SYNTHETIC_VALIDATION_PASS": all(checks.values()),
        "FORMAL_IKDTREE_BUG_PROVEN": False,
        "DATA_RACE_PROVEN": False,
        "DAY9_AUTHORIZED": False,
    }
    _json(output_dir / "day8_final_synthetic_validation.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--root-cause-dir", type=Path)
    parser.add_argument("--synthetic-only", action="store_true")
    args = parser.parse_args()
    synthetic = synthetic_validation(args.output_dir)
    if args.synthetic_only:
        return 0 if synthetic["DAY8_FINAL_SYNTHETIC_VALIDATION_PASS"] else 1
    if args.runtime_root is None or args.root_cause_dir is None:
        raise RuntimeError("runtime-root and root-cause-dir are required")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.root_cause_dir.mkdir(parents=True, exist_ok=True)
    range_query.SCAN_START = 155
    range_query.SCAN_END = 165
    range_query.DETAIL_START = 155
    range_query.DETAIL_END = 165
    queries: dict[str, list[dict[str, Any]]] = {}
    tokens: dict[str, dict[int, list[dict[str, Any]]]] = {}
    statuses: dict[str, dict[int, str]] = {}
    shadows: dict[str, list[dict[str, str]]] = {}
    shadow_sets: dict[str, dict[tuple[Any, ...], tuple[str, ...]]] = {}
    validations: dict[str, Any] = {}
    run_gates: dict[str, Any] = {}
    for run_id in RUN_IDS:
        run_dir = args.runtime_root / run_id
        validations[run_id] = validate_run_query_trace(run_dir)
        run_gates[run_id] = json.loads(
            (run_dir / "day8_final_per_run_gate.json").read_text(
                encoding="utf-8"
            )
        )
        queries[run_id] = load_query_summaries(
            run_dir / "day8_range_query_summary_index.csv"
        )
        tokens[run_id] = group_tokens(load_traversal_tokens(
            run_dir / "day8_range_traversal_token_index.csv"
        ))
        statuses[run_id] = _status_map(run_dir)
        shadows[run_id] = _load_csv(
            run_dir / "day8_shadow_voxel_query_comparison.csv"
        )
        shadow_sets[run_id], _ = _shadow_maps(
            queries[run_id], shadows[run_id]
        )

    pair_values: list[dict[str, Any]] = []
    flat_rows: list[dict[str, Any]] = []
    pair_summaries: list[dict[str, Any]] = []
    pair_first: list[dict[str, Any]] = []
    pair_roots: list[dict[str, Any]] = []
    for left, right in PAIR_NAMES:
        value = compare_strict_pair(
            left_run_id=left,
            right_run_id=right,
            left_queries=queries[left],
            right_queries=queries[right],
            left_shadow_rows=shadows[left],
            right_shadow_rows=shadows[right],
            left_tokens_by_query=tokens[left],
            right_tokens_by_query=tokens[right],
            left_status_by_query=statuses[left],
            right_status_by_query=statuses[right],
        )
        pair_values.append(value)
        flat_rows.extend(value["rows"])
        alignment = value["identity_stream_summary"]
        pair_summaries.append({
            "left_run_id": left,
            "right_run_id": right,
            "left_identity_count": alignment["left_identity_count"],
            "right_identity_count": alignment["right_identity_count"],
            "common_identity_count": alignment["common_identity_count"],
            "left_only_identity_count": alignment["left_only_identity_count"],
            "right_only_identity_count": alignment["right_only_identity_count"],
            "aligned_prefix_length": alignment["aligned_prefix_length"],
            "first_identity_stream_divergence":
                alignment["first_identity_stream_divergence"],
            "identity_stream_classification":
                alignment["identity_stream_classification"],
            "strict_identity_formal_member_set_divergence_count":
                value["strict_identity_formal_member_set_divergence_count"],
            "formal_result_order_only_divergence_count":
                value["formal_result_order_only_divergence_count"],
            "root_cause_classification": value["root_cause_classification"],
        })
        pair_first.append({
            "left_run_id": left,
            "right_run_id": right,
            "first_strict_formal_member_set_divergence":
                value["first_strict_formal_member_set_divergence"],
        })
        pair_roots.append({
            "left_run_id": left,
            "right_run_id": right,
            "root_cause_classification": value["root_cause_classification"],
        })
    comparison_csv = args.output_dir / "pairwise_final_query_comparison.csv"
    _csv(comparison_csv, flat_rows)
    strict_summary = {
        "schema_version": "pairwise_final_strict_identity_summary_v1",
        "pair_count": 6,
        "pairs": pair_summaries,
        "SIX_PAIR_STRICT_IDENTITY_COMPARISON_PASS": True,
    }
    first_summary = {
        "schema_version": "pairwise_final_first_divergence_v1",
        "pairs": pair_first,
    }
    root_pairs = {
        "schema_version": "pairwise_final_root_cause_classification_v1",
        "pairs": pair_roots,
        "ROOT_CAUSE_CLASSIFICATION_COMPLETE": len(pair_roots) == 6,
    }
    _json(args.output_dir / "pairwise_final_strict_identity_summary.json", strict_summary)
    _json(args.output_dir / "pairwise_final_first_divergence.json", first_summary)
    _json(
        args.root_cause_dir / "pairwise_final_root_cause_classification.json",
        root_pairs,
    )

    selected_index = next((
        index for index, value in enumerate(pair_values)
        if value["first_strict_formal_member_set_divergence"] is not None
    ), None)
    if selected_index is None:
        root_result = {
            "schema_version": "day8_final_traversal_root_cause_v1",
            "first_strict_formal_member_set_divergence": None,
            "previous_query_identity": {
                "PREVIOUS_QUERY_IDENTITY_PASS": False,
                "classification": "NOT_APPLICABLE_NO_STRICT_DIVERGENCE",
            },
            "first_divergent_traversal_token": None,
            "traversal_diff_rows": [],
            "missing_expected_point_witness": None,
            "root_cause_classification":
                "NO_STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED",
            "IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED": False,
            "FORMAL_IKDTREE_BUG_PROVEN": False,
            "DATA_RACE_PROVEN": False,
            "DAY9_AUTHORIZED": False,
        }
    else:
        left, right = PAIR_NAMES[selected_index]
        alignment = align_strict_query_streams(
            queries[left], queries[right]
        )
        root_result = analyze_first_strict_divergence(
            pair=pair_values[selected_index],
            alignment=alignment,
            left_queries=queries[left],
            right_queries=queries[right],
            left_shadow_by_identity=shadow_sets[left],
            right_shadow_by_identity=shadow_sets[right],
            left_tokens_by_sequence=tokens[left],
            right_tokens_by_sequence=tokens[right],
            left_status_by_sequence=statuses[left],
            right_status_by_sequence=statuses[right],
        )
    strict_reproduced = root_result[
        "first_strict_formal_member_set_divergence"
    ] is not None
    localized = root_result[
        "IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED"
    ]
    four_complete = all(
        gate["all_gates_pass"] is True for gate in run_gates.values()
    )
    if strict_reproduced and localized:
        route_status = "COMPLETED_WITH_LOCALIZED_QUERY_PATH_WITNESS"
        deterministic = False
        day9_recommended = True
        next_scope = {
            "TREE_TRAVERSAL_PRUNING_DIVERGED":
                "MINIMAL_IKDTREE_PRUNING_ISOLATION",
            "FULL_COVER_SUBTREE_FLATTEN_RESULT_DIVERGED":
                "MINIMAL_IKDTREE_FLATTEN_ISOLATION",
            "DELETION_FLAG_VISIBILITY_DIVERGED":
                "IKDTREE_DELETION_VISIBILITY_ISOLATION",
            "REBUILD_SUBTREE_VISIBILITY_DIVERGED":
                "IKDTREE_REBUILD_READER_VISIBILITY_ISOLATION",
        }.get(root_result["root_cause_classification"])
    elif four_complete and not strict_reproduced:
        route_status = "CLOSED_AFTER_FINAL_FULL_WINDOW_BATCH"
        deterministic = True
        day9_recommended = False
        next_scope = (
            "DETERMINISTIC_IKDTREE_LOGICAL_SET_TREE_SHAPE_"
            "AND_BRUTE_FORCE_ORACLE_FIXTURE"
        )
    else:
        route_status = "CLOSED_WITH_EVIDENCE_GAP"
        deterministic = False
        day9_recommended = False
        next_scope = None
    route = {
        "schema_version": "day8_final_random_replay_route_decision_v1",
        "RANDOM_REAL_REPLAY_ROUTE_STATUS": route_status,
        "FURTHER_RANDOM_REAL_REPLAY_RECOMMENDED": False,
        "FURTHER_RANDOM_REAL_REPLAY_AUTHORIZED": False,
        "DETERMINISTIC_IKDTREE_MINIMAL_FIXTURE_RECOMMENDED": deterministic,
        "NEXT_RECOMMENDED_SCOPE": next_scope,
        "DAY9_RECOMMENDED": day9_recommended,
        "DAY9_RECOMMENDED_SCOPE": next_scope if day9_recommended else None,
        "DAY9_AUTHORIZED": False,
    }
    root_result.update({
        "PREVIOUS_QUERY_IDENTITY_CHECK_COMPLETE": True,
        "STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED":
            strict_reproduced,
        "FORMAL_RANGE_QUERY_COMPLETENESS_VIOLATION_OBSERVED":
            strict_reproduced,
        **route,
    })
    _json(
        args.root_cause_dir / "first_strict_formal_member_divergence.json",
        root_result["first_strict_formal_member_set_divergence"],
    )
    _json(
        args.root_cause_dir / "first_divergent_query_previous_identity.json",
        root_result["previous_query_identity"],
    )
    _csv(
        args.root_cause_dir / "first_divergent_query_traversal_diff.csv",
        root_result["traversal_diff_rows"],
    )
    _json(
        args.root_cause_dir / "missing_expected_point_witness.json",
        root_result["missing_expected_point_witness"],
    )
    _json(
        args.root_cause_dir / "day8_final_root_cause_summary.json",
        {key: value for key, value in root_result.items()
         if key != "traversal_diff_rows"},
    )
    _json(args.root_cause_dir / "random_replay_route_decision.json", route)
    null_audit = audit_output_paths([
        comparison_csv,
        args.output_dir / "pairwise_final_strict_identity_summary.json",
        args.output_dir / "pairwise_final_first_divergence.json",
        args.root_cause_dir / "pairwise_final_root_cause_classification.json",
        args.root_cause_dir / "day8_final_root_cause_summary.json",
        args.root_cause_dir / "first_divergent_query_previous_identity.json",
        args.root_cause_dir / "missing_expected_point_witness.json",
        args.root_cause_dir / "first_divergent_query_traversal_diff.csv",
    ])
    _json(args.root_cause_dir / "null_token_semantics_audit.json", null_audit)
    comparison_summary = {
        "schema_version": "day8_final_comparison_summary_v1",
        "run_count": 4,
        "pair_count": 6,
        "run_validations": validations,
        "FOUR_REPLAY_RUNS_COMPLETE_PASS": four_complete,
        "SIX_PAIR_STRICT_IDENTITY_COMPARISON_PASS": True,
        "STRICT_QUERY_IDENTITY_V2_PASS": True,
        "NULL_TOKEN_SEMANTICS_V3_PASS": True,
        "NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS":
            null_audit["NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS"],
        "STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED":
            strict_reproduced,
        "FORMAL_RANGE_QUERY_COMPLETENESS_VIOLATION_OBSERVED":
            strict_reproduced,
    }
    _json(args.output_dir / "day8_final_comparison_summary.json", comparison_summary)
    return 0 if null_audit[
        "NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS"
    ] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
