#!/usr/bin/env python3
"""Validate fixtures and compare all six Day 8 extended-token run pairs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day7_map_update_events import load_events
from fastlio2_adapter.day8_extended_query_root_cause import (
    CLASSIFICATIONS,
    classify_extended_query_difference,
    compare_extended_query_runs,
    extended_query_identity,
)
from fastlio2_adapter.day8_extended_token_window import RUN_IDS
from fastlio2_adapter.day8_extended_traversal_analysis import (
    missing_expected_point_analysis,
)
from fastlio2_adapter.day8_range_query import (
    load_query_summaries,
    load_traversal_tokens,
    load_voxel_snapshots,
    validate_run_query_trace,
)
from fastlio2_adapter.day8_shadow_voxel_replay import (
    replay_run,
    write_comparison,
)
from fastlio2_adapter.day8_token_capture_status import (
    CAPTURED_NONEMPTY,
    NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
    OVERFLOWED,
)
from fastlio2_adapter.day8_token_comparison_v2 import (
    audit_null_token_semantics,
    compare_token_sequences,
)
from fastlio2_adapter.day8_traversal_analysis import (
    group_tokens,
    traversal_signature,
)


def _json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else [
        "left_run_id",
        "right_run_id",
        "aligned_query_index",
        "classification",
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for raw in rows:
            row = dict(raw)
            for key, value in row.items():
                if isinstance(value, (dict, list, tuple)):
                    row[key] = json.dumps(
                        value, sort_keys=True, separators=(",", ":")
                    )
            writer.writerow(row)


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _pairs() -> list[tuple[str, str]]:
    return [
        (left, right)
        for index, left in enumerate(RUN_IDS)
        for right in RUN_IDS[index + 1:]
    ]


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
        "left_child_considered": 1,
        "left_child_visited": 1,
        "right_child_considered": 0,
        "right_child_visited": 0,
        "subtree_flatten_result_count": 0,
        "rebuild_active": 0,
        "rebuild_generation": 0,
        "token_checksum": 1,
    }
    value.update(updates)
    return value


def synthetic_validation(output_dir: Path) -> dict[str, Any]:
    point = "a" * 64
    query = {
        "run_id": "synthetic",
        "scan_index": 162,
        "map_mutation_call_index": 1,
        "batch_id": "1",
        "batch_point_index": 24,
        "candidate_point_sha256": "c" * 64,
        "voxel_identity": "d" * 48,
        "query_box_checksum": 1,
        "no_intersection_prune_count": 0,
    }
    full = {
        "shadow_member_hashes": point,
        "formal_result_hashes": point,
    }
    missing = {
        "shadow_member_hashes": point,
        "formal_result_hashes": "",
    }

    def classify(
        right_token: Mapping[str, Any],
        *,
        right_query: Mapping[str, Any] | None = None,
        right_shadow: Mapping[str, Any] = missing,
    ) -> str:
        return classify_extended_query_difference(
            left_query=query,
            right_query=right_query or query,
            left_shadow=full,
            right_shadow=right_shadow,
            left_status=CAPTURED_NONEMPTY,
            right_status=CAPTURED_NONEMPTY,
            left_tokens=[_token()],
            right_tokens=[right_token],
        )["classification"]

    not_captured = classify_extended_query_difference(
        left_query=query,
        right_query=query,
        left_shadow=full,
        right_shadow=missing,
        left_status=NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        right_status=NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        left_tokens=(),
        right_tokens=(),
    )
    overflow = compare_token_sequences(
        OVERFLOWED, CAPTURED_NONEMPTY, (), [_token()]
    )
    checks = {
        "matched_query_shadow_and_complete_formal":
            classify(_token(), right_shadow=full)
            == "NO_RANGE_SEARCH_DIVERGENCE_REPRODUCED",
        "matched_query_shadow_and_formal_omission":
            classify(_token())
            == "SAME_CAPTURED_QUERY_TRACE_DIFFERENT_RESULT",
        "expected_member_visited_point_deleted":
            classify(_token(point_deleted=1, current_point_returned=0))
            == "DELETION_FLAG_VISIBILITY_DIVERGED",
        "expected_member_visited_tree_deleted":
            classify(_token(tree_deleted=1, current_point_returned=0))
            == "DELETION_FLAG_VISIBILITY_DIVERGED",
        "expected_member_unvisited_child_path":
            classify(
                _token(
                    node_point_sha256="b" * 64,
                    left_child_visited=0,
                    current_point_returned=0,
                )
            ) == "TREE_TRAVERSAL_PRUNING_DIVERGED",
        "expected_member_unvisited_prune_relation":
            classify(
                _token(
                    node_point_sha256="b" * 64,
                    query_relation="NO_INTERSECTION",
                    left_child_visited=0,
                    current_point_inside_query=0,
                    current_point_returned=0,
                ),
                right_query=dict(query, no_intersection_prune_count=1),
            ) == "TREE_TRAVERSAL_PRUNING_DIVERGED",
        "full_cover_flatten_result_difference":
            classify(_token(
                query_relation="FULL_COVER",
                subtree_flatten_result_count=2,
                current_point_returned=0,
            )) == "FULL_COVER_SUBTREE_FLATTEN_RESULT_DIVERGED",
        "tree_shape_diff_formal_complete":
            classify(_token(depth=1), right_shadow=full)
            == "TREE_SHAPE_DIFFERED_BUT_RESULT_COMPLETE",
        "both_not_captured_is_evidence_gap":
            not_captured["classification"] == "EVIDENCE_GAP"
            and not_captured["token_sequence_equal"] is None,
        "same_captured_trace_different_result":
            classify(_token())
            == "SAME_CAPTURED_QUERY_TRACE_DIFFERENT_RESULT",
        "rebuild_context_difference":
            classify(_token(rebuild_active=1, rebuild_generation=2))
            == "REBUILD_SUBTREE_VISIBILITY_DIVERGED",
        "overflow_fails": overflow["capture_gate_pass"] is False,
    }
    value = {
        "schema_version": "day8_extended_synthetic_validation_v1",
        "checks": checks,
        "DAY8_EXTENDED_SYNTHETIC_VALIDATION_PASS": all(checks.values()),
        "FORMAL_IKDTREE_BUG_PROVEN": False,
        "DATA_RACE_PROVEN": False,
        "DAY9_AUTHORIZED": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _json(output_dir / "day8_extended_synthetic_validation.json", value)
    return value


def _status_map(run_dir: Path) -> dict[int, str]:
    rows = _load_csv(
        run_dir / "day8_token_capture_coverage_by_scan.csv"
    )
    return {
        int(row["query_sequence"]): row["token_capture_status"]
        for row in rows
    }


def _cluster(
    schema: str,
    payloads: Mapping[str, Any],
) -> dict[str, Any]:
    per_run = {
        run_id: hashlib.sha256(json.dumps(
            value, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        for run_id, value in payloads.items()
    }
    grouped: dict[str, list[str]] = {}
    for run_id, checksum in per_run.items():
        grouped.setdefault(checksum, []).append(run_id)
    return {
        "schema_version": schema,
        "cluster_count": len(grouped),
        "clusters": [
            {
                "cluster_id": "cluster_%d" % index,
                "trace_checksum": checksum,
                "runs": sorted(runs),
            }
            for index, (checksum, runs) in enumerate(
                sorted(grouped.items()), start=1
            )
        ],
        "per_run_checksum": per_run,
    }


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
            "DAY8_EXTENDED_SYNTHETIC_VALIDATION_PASS"
        ] else 1
    if args.runtime_root is None or args.root_cause_dir is None:
        raise RuntimeError("runtime and root-cause directories are required")
    args.root_cause_dir.mkdir(parents=True, exist_ok=True)

    run_queries: dict[str, list[dict[str, Any]]] = {}
    run_tokens: dict[str, dict[int, list[dict[str, Any]]]] = {}
    run_status: dict[str, dict[int, str]] = {}
    run_shadow: dict[str, list[dict[str, Any]]] = {}
    validations: dict[str, Any] = {}
    all_shadow: list[dict[str, Any]] = []
    for run_id in RUN_IDS:
        run_dir = args.runtime_root / run_id
        validations[run_id] = validate_run_query_trace(run_dir)
        queries = load_query_summaries(
            run_dir / "day8_range_query_summary_index.csv"
        )
        tokens = group_tokens(load_traversal_tokens(
            run_dir / "day8_range_traversal_token_index.csv"
        ))
        shadow = replay_run(
            run_id=run_id,
            snapshots=load_voxel_snapshots(
                run_dir / "map_point_voxel_identity_snapshot_index.csv",
                run_dir / "map_point_voxel_identity_snapshot_pairs.csv",
            ),
            queries=queries,
            events=load_events(
                run_dir / "day7_map_mutation_event_index.csv"
            ),
            tolerate_accounting_failure=False,
        )
        run_queries[run_id] = queries
        run_tokens[run_id] = tokens
        run_status[run_id] = _status_map(run_dir)
        run_shadow[run_id] = shadow
        all_shadow.extend(shadow)
    write_comparison(
        args.output_dir / "day8_shadow_voxel_query_comparison.csv",
        all_shadow,
    )

    comparisons: list[dict[str, Any]] = []
    flat_rows: list[dict[str, Any]] = []
    first_values: list[dict[str, Any]] = []
    for left, right in _pairs():
        value = compare_extended_query_runs(
            left_run_id=left,
            right_run_id=right,
            left_queries=run_queries[left],
            right_queries=run_queries[right],
            left_shadow_rows=run_shadow[left],
            right_shadow_rows=run_shadow[right],
            left_tokens_by_query=run_tokens[left],
            right_tokens_by_query=run_tokens[right],
            left_status_by_query=run_status[left],
            right_status_by_query=run_status[right],
        )
        comparisons.append(value)
        flat_rows.extend(value["rows"])
        first_values.append(value["first_divergence"])
    _csv(
        args.output_dir / "pairwise_extended_range_query_comparison.csv",
        flat_rows,
    )
    first_doc = {
        "schema_version":
            "pairwise_day8_extended_first_query_divergence_v2",
        "pair_count": len(first_values),
        "pairs": first_values,
    }
    _json(
        args.output_dir / "pairwise_extended_first_query_divergence.json",
        first_doc,
    )
    query_payloads = {
        run_id: [
            {
                "identity": extended_query_identity(query),
                "formal_result_members": query["formal_result_members"],
            }
            for query in run_queries[run_id]
        ]
        for run_id in RUN_IDS
    }
    token_payloads = {
        run_id: [
            (sequence, traversal_signature(rows))
            for sequence, rows in sorted(run_tokens[run_id].items())
        ]
        for run_id in RUN_IDS
    }
    _json(
        args.output_dir / "extended_query_result_clusters.json",
        _cluster("extended_query_result_clusters_v1", query_payloads),
    )
    _json(
        args.output_dir / "extended_traversal_trace_clusters.json",
        _cluster("extended_traversal_trace_clusters_v1", token_payloads),
    )

    divergent = [
        item for item in first_values
        if item.get("aligned_query_index") is not None
    ]
    earliest = min(
        divergent,
        key=lambda item: (
            int(item["aligned_query_index"]),
            item["left_run_id"],
            item["right_run_id"],
        ),
    ) if divergent else None
    previous: dict[str, Any] = {
        "schema_version":
            "first_divergent_query_previous_identity_v2",
        "first_divergent_query_reproduced": earliest is not None,
        "previous_query_identity_check_complete": True,
    }
    witnesses: list[dict[str, Any]] = []
    traversal_rows: list[dict[str, Any]] = []
    if earliest is not None:
        left_id = earliest["left_run_id"]
        right_id = earliest["right_run_id"]
        index = int(earliest["aligned_query_index"])
        left_query = run_queries[left_id][index]
        right_query = run_queries[right_id][index]
        left_sequence = int(left_query["query_sequence"])
        right_sequence = int(right_query["query_sequence"])
        traversal_rows = earliest["traversal_difference"]["rows"]
        left_shadow = run_shadow[left_id][index]
        right_shadow = run_shadow[right_id][index]
        missing = sorted(
            set(filter(
                None,
                str(left_shadow["missing_from_formal_result"]).split(";"),
            ))
            | set(filter(
                None,
                str(right_shadow["missing_from_formal_result"]).split(";"),
            ))
            | (
                set(left_query["formal_result_members"])
                ^ set(right_query["formal_result_members"])
            )
        )
        for point in missing:
            witnesses.append(missing_expected_point_analysis(
                point,
                run_tokens[left_id].get(left_sequence, ()),
                run_tokens[right_id].get(right_sequence, ()),
            ))
        if index > 0:
            prior_left = run_queries[left_id][index - 1]
            prior_right = run_queries[right_id][index - 1]
            prior_left_sequence = int(prior_left["query_sequence"])
            prior_right_sequence = int(prior_right["query_sequence"])
            token_comparison = compare_token_sequences(
                run_status[left_id][prior_left_sequence],
                run_status[right_id][prior_right_sequence],
                run_tokens[left_id].get(prior_left_sequence, ()),
                run_tokens[right_id].get(prior_right_sequence, ()),
            )
            previous.update({
                "previous_query_index": index - 1,
                "left_previous_query_identity":
                    extended_query_identity(prior_left),
                "right_previous_query_identity":
                    extended_query_identity(prior_right),
                "previous_query_equal":
                    extended_query_identity(prior_left)
                    == extended_query_identity(prior_right),
                "previous_shadow_state_equal":
                    run_shadow[left_id][index - 1]["shadow_member_hashes"]
                    == run_shadow[right_id][index - 1][
                        "shadow_member_hashes"
                    ],
                "previous_formal_result_equal":
                    run_shadow[left_id][index - 1]["formal_result_hashes"]
                    == run_shadow[right_id][index - 1][
                        "formal_result_hashes"
                    ],
                "previous_traversal_summary_equal":
                    traversal_signature(run_tokens[left_id].get(
                        prior_left_sequence, ()
                    ))
                    == traversal_signature(run_tokens[right_id].get(
                        prior_right_sequence, ()
                    )),
                "previous_token_comparison": token_comparison,
            })
            previous["previous_query_identity_check_complete"] = all((
                previous["previous_query_equal"],
                previous["previous_shadow_state_equal"],
                previous["previous_formal_result_equal"],
                previous["previous_traversal_summary_equal"],
                token_comparison["token_sequence_equal"] is True,
            ))
    _json(
        args.root_cause_dir / "first_divergent_range_query.json",
        {
            "schema_version": "first_divergent_range_query_v2",
            "first_divergent_query_reproduced": earliest is not None,
            "value": earliest,
            "formal_ikdtree_bug_proven": False,
            "day9_authorized": False,
        },
    )
    _json(
        args.root_cause_dir
        / "first_divergent_query_previous_identity.json",
        previous,
    )
    _csv(
        args.root_cause_dir
        / "first_divergent_query_traversal_diff.csv",
        traversal_rows,
    )
    witness_doc = {
        "schema_version": "missing_expected_point_witness_v2",
        "first_divergent_query_reproduced": earliest is not None,
        "witness_count": len(witnesses),
        "witnesses": witnesses,
    }
    _json(
        args.root_cause_dir / "missing_expected_point_witness.json",
        witness_doc,
    )
    classifications = [
        {
            "left_run_id": item["left_run_id"],
            "right_run_id": item["right_run_id"],
            "aligned_query_index": item.get("aligned_query_index"),
            "classification": item["root_cause"]["classification"],
            "reason": item["root_cause"]["reason"],
            "root_cause_classification":
                item["root_cause"].get("root_cause_classification"),
            "left_token_capture_status":
                item["root_cause"].get("left_token_capture_status"),
            "right_token_capture_status":
                item["root_cause"].get("right_token_capture_status"),
            "token_comparison_status":
                item["root_cause"].get("token_comparison_status"),
            "token_sequence_equal":
                item["root_cause"].get("token_sequence_equal"),
            "formal_ikdtree_bug_proven": False,
            "data_race_proven": False,
            "day9_authorized": False,
        }
        for item in first_values
    ]
    pair_root = {
        "schema_version":
            "pairwise_day8_extended_root_cause_classification_v2",
        "pair_count": len(classifications),
        "pairs": classifications,
        "all_classifications_within_fixed_taxonomy": all(
            item["classification"] in CLASSIFICATIONS
            for item in classifications
        ),
        "formal_ikdtree_bug_proven": False,
        "data_race_proven": False,
        "day9_authorized": False,
    }
    _json(
        args.root_cause_dir
        / "pairwise_extended_root_cause_classification.json",
        pair_root,
    )
    shadow_pass = all(
        int(row["shadow_state_accounting_pass"]) == 1
        for row in all_shadow
    )
    completeness_failures = sum(
        int(row["formal_query_completeness_pass"]) == 0
        for row in all_shadow
    )
    first_coverage_pass = all(
        item["root_cause"].get("left_token_capture_status")
        == item["root_cause"].get("right_token_capture_status")
        == CAPTURED_NONEMPTY
        and item["root_cause"].get("token_comparison_status") == "APPLICABLE"
        for item in divergent
    )
    null_audit = audit_null_token_semantics({
        "pairwise_comparison": comparisons,
        "first_query_selector": first_doc,
        "previous_query_identity": previous,
        "root_cause_classifier": pair_root,
    })
    _json(
        args.root_cause_dir / "null_token_semantics_audit.json",
        null_audit,
    )
    summary = {
        "schema_version": "day8_extended_root_cause_summary_v1",
        "run_count": len(RUN_IDS),
        "pair_count": len(classifications),
        "first_divergent_query_localized": earliest is not None,
        "first_divergent_query": earliest,
        "previous_query_identity": previous,
        "classification_counts": {
            value: sum(
                item["classification"] == value
                for item in classifications
            )
            for value in sorted({
                item["classification"] for item in classifications
            })
        },
        "formal_query_completeness_failure_count":
            completeness_failures,
        "shadow_state_accounting_pass": shadow_pass,
        "six_pair_range_query_comparison_pass":
            len(classifications) == 6,
        "previous_query_identity_check_complete":
            previous["previous_query_identity_check_complete"],
        "first_divergent_query_detailed_token_coverage_pass":
            first_coverage_pass,
        "missing_expected_point_witness_pass":
            not divergent or bool(witnesses),
        "root_cause_classification_complete":
            len(classifications) == 6
            and pair_root["all_classifications_within_fixed_taxonomy"],
        "NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS":
            null_audit["NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS"],
        "formal_ikdtree_bug_proven": False,
        "data_race_proven": False,
        "shadow_replay_participates_in_fast_decisions": False,
        "instrumentation_timing_perturbation_present": True,
        "day9_authorized": False,
    }
    _json(
        args.root_cause_dir / "day8_extended_root_cause_summary.json",
        summary,
    )
    _json(
        args.output_dir / "day8_extended_comparison_summary.json",
        {
            "schema_version": "day8_extended_comparison_summary_v1",
            "run_validations": validations,
            "shadow_query_row_count": len(all_shadow),
            "shadow_state_accounting_pass": shadow_pass,
            "formal_query_completeness_failure_count":
                completeness_failures,
            "pair_count": len(comparisons),
            "six_pair_range_query_comparison_pass":
                len(comparisons) == 6,
        },
    )
    return 0 if all((
        len(comparisons) == 6,
        shadow_pass,
        first_coverage_pass,
        previous["previous_query_identity_check_complete"],
        null_audit["NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS"],
    )) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        raise SystemExit(1)
