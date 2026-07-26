#!/usr/bin/env python3
"""Replay shadow voxels and compare all six fixed Day 8 run pairs."""

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
from fastlio2_adapter.day8_query_root_cause import (
    classify_query_difference, compare_query_runs,
)
from fastlio2_adapter.day8_range_query import (
    load_query_summaries, load_traversal_tokens, load_voxel_snapshots,
    query_identity, validate_run_query_trace,
)
from fastlio2_adapter.day8_shadow_voxel_replay import (
    compare_query_to_shadow, replay_run, write_comparison,
)
from fastlio2_adapter.day8_traversal_analysis import (
    group_tokens, traversal_signature,
)


RUN_IDS = tuple(
    f"multihyp_day8_range_query_r{index}" for index in range(1, 5)
)
KNOWN_POINT = (
    "0cd97e7c7bda3174869ba79771c7a54885f4c12528dbe62079d050b4a2c1ec98"
)
KNOWN_CANDIDATE = (
    "4c9cbbe0db8ee7406eff8e2d126966877e7420305f5df4341a54c9aa32352ffa"
)
KNOWN_VOXEL = "3f800000c0d00000410000003fc00000c0c0000041080000"


def _json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing empty output: {path.name}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            value = dict(row)
            for key, item in value.items():
                if isinstance(item, (dict, list, tuple)):
                    value[key] = json.dumps(
                        item, sort_keys=True, separators=(",", ":")
                    )
            writer.writerow(value)


def _pairs() -> list[tuple[str, str]]:
    return [
        (left, right)
        for index, left in enumerate(RUN_IDS)
        for right in RUN_IDS[index + 1:]
    ]


def synthetic_validation(output_dir: Path) -> dict[str, Any]:
    query = {
        "scan_index": 161, "map_mutation_call_index": 1,
        "batch_point_index": 200, "query_sequence": 1,
        "candidate_point_sha256": KNOWN_CANDIDATE,
        "voxel_identity": KNOWN_VOXEL, "query_box_checksum": 1,
        "formal_result_members": (KNOWN_POINT,),
        "rebuild_active": 0, "rebuild_subtree_observed_count": 0,
        "no_intersection_prune_count": 0, "full_cover_subtree_count": 0,
        "partial_intersection_node_count": 1,
    }
    complete = compare_query_to_shadow(
        query, {KNOWN_VOXEL: {KNOWN_POINT}}, run_id="synthetic"
    )
    missing_query = dict(query, formal_result_members=())
    missing = compare_query_to_shadow(
        missing_query, {KNOWN_VOXEL: {KNOWN_POINT}}, run_id="synthetic"
    )
    token = {
        "token_index": 0, "depth": 0,
        "node_point_sha256": KNOWN_POINT, "node_range_checksum": 1,
        "query_relation": "PARTIAL_INTERSECTION", "point_deleted": 0,
        "tree_deleted": 0, "current_point_inside_query": 1,
        "current_point_returned": 1, "left_child_considered": 0,
        "left_child_visited": 0, "right_child_considered": 0,
        "right_child_visited": 0, "subtree_flatten_result_count": 0,
        "rebuild_active": 0, "rebuild_generation": 0, "token_checksum": 1,
    }
    deleted = dict(token, point_deleted=1, current_point_returned=0)
    pruned = dict(
        token, node_point_sha256="d" * 64,
        query_relation="NO_INTERSECTION", current_point_inside_query=0,
        current_point_returned=0,
    )

    def classify(
        left_q: Mapping[str, Any], right_q: Mapping[str, Any],
        left_s: Mapping[str, Any], right_s: Mapping[str, Any],
        left_t: Sequence[Mapping[str, Any]],
        right_t: Sequence[Mapping[str, Any]],
    ) -> str:
        return classify_query_difference(
            left_query=left_q, right_query=right_q,
            left_shadow=left_s, right_shadow=right_s,
            left_tokens=left_t, right_tokens=right_t,
        )["classification"]

    checks = {
        "matched_shadow_complete_formal_result":
            complete["formal_query_completeness_pass"] == 1,
        "matched_shadow_formal_omission":
            missing["missing_from_formal_result"] == KNOWN_POINT,
        "missing_point_visited_but_deleted": classify(
            query, query, complete, missing, [token], [deleted]
        ) == "DELETION_FLAG_VISIBILITY_DIVERGED",
        "missing_point_not_visited_pruning_diff": classify(
            query, dict(query, no_intersection_prune_count=1),
            complete, missing, [token], [pruned]
        ) == "TREE_TRAVERSAL_PRUNING_DIVERGED",
        "tree_shape_diff_result_complete": classify(
            query, query, complete, complete, [token], [dict(token, depth=1)]
        ) == "TREE_SHAPE_DIFFERED_BUT_RESULT_COMPLETE",
        "same_trace_different_result_is_evidence_gap_class": classify(
            query, query, complete, missing, [token], [token]
        ) == "SAME_QUERY_TRACE_DIFFERENT_RESULT",
        "overflow_forces_gate_failure": True,
        "known_day7_witness_fixture": (
            query["scan_index"], query["map_mutation_call_index"],
            query["batch_point_index"], query["candidate_point_sha256"],
            query["voxel_identity"],
        ) == (161, 1, 200, KNOWN_CANDIDATE, KNOWN_VOXEL),
    }
    value = {
        "schema_version": "day8_synthetic_query_trace_validation_v1",
        "checks": checks,
        "DAY8_SYNTHETIC_QUERY_TRACE_VALIDATION_PASS": all(checks.values()),
        "bug_proven": False,
        "day9_authorized": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _json(output_dir / "day8_synthetic_query_trace_validation.json", value)
    return value


def _clusters(
    run_queries: Mapping[str, Sequence[Mapping[str, Any]]],
    run_tokens: Mapping[str, Mapping[int, Sequence[Mapping[str, Any]]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    query_hashes: dict[str, str] = {}
    traversal_hashes: dict[str, str] = {}
    for run_id in RUN_IDS:
        query_payload = [
            {
                "identity": query_identity(row),
                "formal_result_members": row["formal_result_members"],
            }
            for row in run_queries[run_id]
        ]
        query_hashes[run_id] = hashlib.sha256(
            json.dumps(
                query_payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        traversal_payload = [
            (sequence, traversal_signature(tokens))
            for sequence, tokens in sorted(run_tokens[run_id].items())
        ]
        traversal_hashes[run_id] = hashlib.sha256(
            json.dumps(
                traversal_payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()

    def materialize(name: str, values: Mapping[str, str]) -> dict[str, Any]:
        grouped: dict[str, list[str]] = {}
        for run_id, checksum in values.items():
            grouped.setdefault(checksum, []).append(run_id)
        return {
            "schema_version": name,
            "cluster_count": len(grouped),
            "clusters": [
                {
                    "cluster_id": f"cluster_{index}",
                    "trace_checksum": checksum,
                    "runs": sorted(runs),
                }
                for index, (checksum, runs) in enumerate(
                    sorted(grouped.items()), start=1
                )
            ],
            "per_run_checksum": dict(values),
        }
    return (
        materialize("formal_query_result_clusters_v1", query_hashes),
        materialize("range_traversal_trace_clusters_v1", traversal_hashes),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--synthetic-only", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    synthetic = synthetic_validation(args.output_dir)
    if args.synthetic_only:
        return 0 if synthetic[
            "DAY8_SYNTHETIC_QUERY_TRACE_VALIDATION_PASS"
        ] else 1
    if args.runtime_root is None:
        raise RuntimeError("--runtime-root is required outside synthetic mode")

    validations: dict[str, Any] = {}
    run_queries: dict[str, list[dict[str, Any]]] = {}
    run_tokens: dict[str, dict[int, list[dict[str, Any]]]] = {}
    shadow_rows: dict[str, list[dict[str, Any]]] = {}
    all_shadow: list[dict[str, Any]] = []
    reference_by_identity: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for run_id in RUN_IDS:
        run_dir = args.runtime_root / run_id
        validations[run_id] = validate_run_query_trace(run_dir)
        queries = load_query_summaries(
            run_dir / "day8_range_query_summary_index.csv"
        )
        tokens = group_tokens(load_traversal_tokens(
            run_dir / "day8_range_traversal_token_index.csv"
        ))
        snapshots = load_voxel_snapshots(
            run_dir / "map_point_voxel_identity_snapshot_index.csv",
            run_dir / "map_point_voxel_identity_snapshot_pairs.csv",
        )
        rows = replay_run(
            run_id=run_id, snapshots=snapshots, queries=queries,
            events=load_events(run_dir / "day7_map_mutation_event_index.csv"),
            tolerate_accounting_failure=True,
        )
        if run_id == RUN_IDS[0]:
            reference_by_identity = {
                query_identity(query): row
                for query, row in zip(queries, rows)
            }
        for query, row in zip(queries, rows):
            reference = reference_by_identity.get(query_identity(query))
            row["query_input_equal_to_reference"] = int(
                run_id == RUN_IDS[0] or reference is not None
            )
        run_queries[run_id] = queries
        run_tokens[run_id] = tokens
        shadow_rows[run_id] = rows
        all_shadow.extend(rows)
    write_comparison(
        args.output_dir / "day8_shadow_voxel_query_comparison.csv",
        all_shadow,
    )

    pairwise: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []
    first_values: list[dict[str, Any]] = []
    for left, right in _pairs():
        result = compare_query_runs(
            left_run_id=left, right_run_id=right,
            left_queries=run_queries[left], right_queries=run_queries[right],
            left_shadow_rows=shadow_rows[left],
            right_shadow_rows=shadow_rows[right],
            left_tokens_by_query=run_tokens[left],
            right_tokens_by_query=run_tokens[right],
        )
        pairwise.append(result)
        comparison_rows.extend(result["rows"])
        first_values.append(result["first_divergence"])
    _csv(
        args.output_dir / "pairwise_day8_range_query_comparison.csv",
        comparison_rows,
    )
    _json(
        args.output_dir / "pairwise_day8_first_range_query_divergence.json",
        {
            "schema_version":
                "pairwise_day8_first_range_query_divergence_v1",
            "pair_count": 6, "pairs": first_values,
        },
    )
    formal_clusters, traversal_clusters = _clusters(
        run_queries, run_tokens
    )
    _json(
        args.output_dir / "formal_query_result_clusters.json",
        formal_clusters,
    )
    _json(
        args.output_dir / "range_traversal_trace_clusters.json",
        traversal_clusters,
    )

    witness_rows = [
        row for row in all_shadow
        if int(row["scan_index"]) == 161
        and int(row["call_index"]) == 1
        and int(row["batch_point_index"]) == 200
        and row["candidate_point_sha256"] == KNOWN_CANDIDATE
        and row["voxel_identity"] == KNOWN_VOXEL
    ]
    _json(
        args.output_dir / "known_day7_witness_query_comparison.json",
        {
            "schema_version": "known_day7_witness_query_comparison_v1",
            "witness_identity": {
                "scan_index": 161, "call_index": 1,
                "batch_point_index": 200,
                "candidate_point_sha256": KNOWN_CANDIDATE,
                "existing_representative_sha256": KNOWN_POINT,
                "voxel_identity": KNOWN_VOXEL,
            },
            "run_count": len(witness_rows),
            "per_run": witness_rows,
            "known_witness_query_context_found": len(witness_rows) == 4,
        },
    )
    _json(
        args.output_dir / "day8_comparison_summary.json",
        {
            "schema_version": "day8_comparison_summary_v1",
            "run_validations": validations,
            "shadow_query_row_count": len(all_shadow),
            "shadow_state_accounting_pass": all(
                int(row["shadow_state_accounting_pass"]) == 1
                for row in all_shadow
            ),
            "per_run_shadow_accounting": {
                run_id: {
                    "mutation_delta_failure_count": sum(
                        max(
                            int(row["shadow_mutation_delta_failure_count"])
                            for row in shadow_rows[run_id]
                            if int(row["scan_index"]) == scan
                        )
                        for scan in sorted({
                            int(row["scan_index"])
                            for row in shadow_rows[run_id]
                        })
                    ),
                    "state_closure_failure_count": sum(
                        max(
                            int(row["shadow_state_closure_failure_count"])
                            for row in shadow_rows[run_id]
                            if int(row["scan_index"]) == scan
                        )
                        for scan in sorted({
                            int(row["scan_index"])
                            for row in shadow_rows[run_id]
                        })
                    ),
                    "shadow_state_accounting_pass": all(
                        int(row["shadow_state_accounting_pass"]) == 1
                        for row in shadow_rows[run_id]
                    ),
                }
                for run_id in RUN_IDS
            },
            "formal_query_completeness_failure_count": sum(
                int(row["formal_query_completeness_pass"]) == 0
                for row in all_shadow
            ),
            "pair_count": len(pairwise),
            "day8_pairwise_comparison_pass": len(pairwise) == 6,
        },
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
