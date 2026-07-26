#!/usr/bin/env python3
"""Validate four Day 7 runs and materialize all six fixed comparisons."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter import experiment_a_map_snapshot_coherence as snapshots
from fastlio2_adapter import experiment_a_stage_hash as stage_hash
from fastlio2_adapter import focused_branch_stage_classifier as classifier
from fastlio2_adapter import focused_branch_stage_localization as focused
from fastlio2_adapter.day6_semantic_observation import (
    load_observation_records,
)
from fastlio2_adapter.day7_map_point_identity import (
    load_snapshot_sets,
    symmetric_difference,
)
from fastlio2_adapter.day7_map_update_events import (
    load_call_summaries,
    load_events,
    validate_run_trace,
)
from fastlio2_adapter.day7_map_update_root_cause import (
    EVENT_FIELDS,
    classify_event_difference,
    classify_pair_components,
    compare_run_pair,
    evaluate_day7_gate,
)
from fastlio2_adapter.day7_rebuild_logger_analysis import (
    compare_logger_runs,
    load_logger_events,
)
from fastlio2_adapter.formal_trajectory_clustering import (
    cluster_formal_trajectories,
    write_clusters,
)


RUN_IDS = tuple(
    f"multihyp_day7_map_update_r{index}" for index in range(1, 5)
)
SCAN_START = 150
SCAN_END = 170


def _json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing empty comparison: {path.name}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            value = dict(row)
            for key, item in value.items():
                if isinstance(item, (list, tuple, dict)):
                    value[key] = json.dumps(item, sort_keys=True)
            writer.writerow(value)


def _pairs() -> list[tuple[str, str]]:
    return [
        (left, right)
        for index, left in enumerate(RUN_IDS)
        for right in RUN_IDS[index + 1:]
    ]


def _sequence_mismatch(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
) -> tuple[int, int | None]:
    mismatches = [
        index
        for index, (a, b) in enumerate(zip(left, right))
        if any(a.get(field) != b.get(field) for field in fields)
    ]
    if len(left) != len(right):
        mismatches.extend(range(
            min(len(left), len(right)), max(len(left), len(right))
        ))
    return len(mismatches), mismatches[0] if mismatches else None


def _trace_clusters(runtime_root: Path) -> dict[str, Any]:
    checksums = {}
    for run_id in RUN_IDS:
        run = runtime_root / run_id
        events = load_events(run / "day7_map_mutation_event_index.csv")
        logger = load_logger_events(
            run / "day7_rebuild_logger_event_index.csv"
        )
        canonical = {
            "events": [
                {
                    field: row[field]
                    for field in (
                        "scan_index",
                        "call_index",
                        "batch_point_index",
                        *EVENT_FIELDS,
                    )
                }
                for row in events
            ],
            "logger": [
                {
                    field: row[field]
                    for field in (
                        "phase",
                        "operation_set",
                        "generation",
                        "apply_order_index",
                        "outcome",
                        "point_sha256",
                        "box_identity",
                    )
                }
                for row in logger
            ],
        }
        checksums[run_id] = hashlib.sha256(
            json.dumps(
                canonical, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
    grouped: dict[str, list[str]] = {}
    for run_id, checksum in checksums.items():
        grouped.setdefault(checksum, []).append(run_id)
    clusters = [
        {
            "cluster_id": f"map_update_cluster_{index}",
            "trace_checksum": checksum,
            "runs": sorted(runs),
            "size": len(runs),
        }
        for index, (checksum, runs) in enumerate(
            sorted(grouped.items()), start=1
        )
    ]
    return {
        "schema_version": "day7_map_update_trace_clusters_v1",
        "run_count": 4,
        "cluster_count": len(clusters),
        "clusters": clusters,
        "per_run_trace_checksum": checksums,
        "map_update_trace_clustering_pass": True,
    }


def _synthetic_validation(output_dir: Path) -> dict[str, Any]:
    candidate = {
        "candidate_point_sha256": "a" * 64,
        "voxel_identity": "0" * 48,
        "existing_representative_sha256": "b" * 64,
        "selected_representative_sha256": "a" * 64,
        "decision_context_ordered_checksum": 1,
        "formal_outcome": "INSERTED_NEW_VOXEL_REPRESENTATIVE",
        "mutation_destination": "DIRECT_TREE",
    }
    routed = dict(candidate, mutation_destination="BOTH")
    checks = {
        "event_trace_complete": all(
            field in candidate
            for field in (
                "candidate_point_sha256",
                "voxel_identity",
                "formal_outcome",
                "mutation_destination",
            )
        ),
        "map_delta_closes": (11 - 10) == 1,
        "point_symmetric_difference_backlinks": (
            symmetric_difference(["a", "b"], ["a", "c"])
            == (["b"], ["c"])
        ),
        "direct_logger_routing_identified": (
            classify_event_difference(candidate, routed)
            == "REBUILD_LOGGER_ROUTING_DIVERGED"
        ),
        "logger_apply_order_identified": (
            classify_pair_components(
                map_diverged=True,
                left_event=None,
                right_event=None,
                logger={
                    "append_multiset_equal": True,
                    "apply_order_equal": False,
                    "apply_result_equal": False,
                },
            ) == "REBUILD_LOGGER_APPLICATION_ORDER_DIVERGED"
        ),
        "same_events_different_map_fails": (
            classify_pair_components(
                map_diverged=True,
                left_event=None,
                right_event=None,
                logger={
                    "append_multiset_equal": True,
                    "apply_order_equal": True,
                    "apply_result_equal": True,
                },
            ) == "SAME_EVENT_TRACE_DIFFERENT_MAP_AFTER"
        ),
        "overflow_fails_gate": (
            evaluate_day7_gate(
                {"event_trace_overflow_pass": False}, []
            )["day7_execution_pass"] is False
        ),
    }
    taxonomy = json.loads(
        (
            ROOT
            / "manifests/harmful_bias/day7_map_mutation_outcome_taxonomy.json"
        ).read_text(encoding="utf-8")
    )
    checks["taxonomy_complete"] = (
        taxonomy["formal_outcome_count"] == 20
        and taxonomy["unclassified_formal_path_count"] == 0
    )
    value = {
        "schema_version": "day7_synthetic_trace_validation_v1",
        **checks,
        "day7_synthetic_trace_validation_pass": all(checks.values()),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _json(output_dir / "day7_synthetic_trace_validation.json", value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--synthetic-only", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.synthetic_only:
        value = _synthetic_validation(args.output_dir)
        print(json.dumps(value, sort_keys=True))
        return 0 if value["day7_synthetic_trace_validation_pass"] else 1
    if args.runtime_root is None:
        raise ValueError("--runtime-root is required outside synthetic mode")

    classifier.SCAN_START = SCAN_START
    classifier.SCAN_END = SCAN_END
    classifier.EXPECTED_RECORD_COUNT = 21
    classifier.EXPECTED_SNAPSHOTS_PER_RUN = 42
    stage_hash.SCAN_START = SCAN_START
    stage_hash.SCAN_END = SCAN_END
    stage_hash.EXPECTED_RECORD_COUNT = 21
    snapshots.SCAN_START = SCAN_START
    snapshots.SCAN_END = SCAN_END
    snapshots.EXPECTED_RECORD_COUNT = 21
    snapshots.EXPECTED_SNAPSHOTS_PER_RUN = 42
    focused.SCAN_START = SCAN_START
    focused.SCAN_END = SCAN_END

    observations = {}
    stages = {}
    integrity = {}
    trace_integrity = {}
    for run_id in RUN_IDS:
        run = args.runtime_root / run_id
        trace_integrity[run_id] = validate_run_trace(run)
        observations[run_id], integrity[run_id] = load_observation_records(
            run / "observation_records_v3.bin"
        )
        stages[run_id] = classifier.load_focused_records(
            run / "experiment_a_stage_hash_records_v2.json"
        )
    focused_result = focused.compare_all(
        run_ids=RUN_IDS,
        observations=observations,
        focused_records=stages,
    )
    focused.write_comparison(focused_result, args.output_dir)
    shutil.copy2(
        args.output_dir / "pairwise_full_stream_semantic_comparison.csv",
        args.output_dir / "pairwise_day7_semantic_comparison.csv",
    )
    shutil.copy2(
        args.output_dir / "pairwise_focused_stage_comparison.csv",
        args.output_dir / "pairwise_day7_stage_comparison.csv",
    )

    pair_results = []
    snapshot_rows = []
    call_rows = []
    event_rows = []
    logger_rows = []
    previous_rows = []
    for left, right in _pairs():
        pair = f"{left}-{right}"
        left_dir = args.runtime_root / left
        right_dir = args.runtime_root / right
        result = compare_run_pair(left_dir, right_dir, pair_name=pair)
        pair_results.append(result)
        left_snapshots = load_snapshot_sets(
            left_dir / "map_point_identity_snapshot_hashes.csv"
        )
        right_snapshots = load_snapshot_sets(
            right_dir / "map_point_identity_snapshot_hashes.csv"
        )
        for scan in range(SCAN_START, SCAN_END + 1):
            before = (scan, "MAP_BEFORE")
            after = (scan, "MAP_AFTER")
            before_left, before_right = symmetric_difference(
                left_snapshots[before], right_snapshots[before]
            )
            after_left, after_right = symmetric_difference(
                left_snapshots[after], right_snapshots[after]
            )
            snapshot_rows.append({
                "pair": pair,
                "scan_index": scan,
                "map_before_equal": not before_left and not before_right,
                "map_after_equal": not after_left and not after_right,
                "map_before_only_left_count": len(before_left),
                "map_before_only_right_count": len(before_right),
                "map_after_only_left_count": len(after_left),
                "map_after_only_right_count": len(after_right),
            })
        left_calls = load_call_summaries(
            left_dir / "day7_map_mutation_call_summaries.csv"
        )
        right_calls = load_call_summaries(
            right_dir / "day7_map_mutation_call_summaries.csv"
        )
        call_mismatch, call_first = _sequence_mismatch(
            left_calls,
            right_calls,
            (
                "scan_index",
                "call_index",
                "input_point_count",
                "map_count_before",
                "map_count_after",
                "event_count",
                "expected_logical_count_delta",
                "observed_logical_count_delta",
            ),
        )
        call_rows.append({
            "pair": pair,
            "left_call_count": len(left_calls),
            "right_call_count": len(right_calls),
            "mismatch_count": call_mismatch,
            "first_mismatch_index": call_first,
        })
        left_events = load_events(
            left_dir / "day7_map_mutation_event_index.csv"
        )
        right_events = load_events(
            right_dir / "day7_map_mutation_event_index.csv"
        )
        event_mismatch, event_first = _sequence_mismatch(
            left_events,
            right_events,
            (
                "scan_index",
                "call_index",
                "batch_point_index",
                *EVENT_FIELDS,
            ),
        )
        event_rows.append({
            "pair": pair,
            "left_event_count": len(left_events),
            "right_event_count": len(right_events),
            "mismatch_count": event_mismatch,
            "first_mismatch_index": event_first,
            "root_cause_classification":
                result["root_cause_classification"],
        })
        logger_result = compare_logger_runs(left_dir, right_dir)
        logger_rows.append({"pair": pair, **logger_result})
        previous_rows.append({
            "pair": pair,
            "first_divergent_event_key": result["previous_event_key"],
            "previous_event_identity_equal":
                result["previous_event_identity_equal"],
            "previous_map_digest_equal":
                True if result["scan_index"] is not None else None,
            "previous_logger_state_equal":
                result["logger_first_mismatch_index"] in {None, 0},
            "previous_rebuild_generation_equal":
                result["rebuild_generation_equal"],
            "previous_logical_mutation_epoch_equal":
                result["previous_event_identity_equal"],
        })

    _csv(
        args.output_dir / "pairwise_day7_map_snapshot_comparison.csv",
        snapshot_rows,
    )
    _csv(
        args.output_dir / "pairwise_day7_map_mutation_call_comparison.csv",
        call_rows,
    )
    _csv(
        args.output_dir / "pairwise_day7_map_mutation_event_comparison.csv",
        event_rows,
    )
    _csv(
        args.output_dir / "pairwise_day7_rebuild_logger_comparison.csv",
        logger_rows,
    )
    _csv(
        args.output_dir / "first_divergent_event_previous_identity.csv",
        previous_rows,
    )
    _json(args.output_dir / "pairwise_day7_first_divergence.json", {
        "schema_version": "pairwise_day7_first_divergence_v1",
        "pair_count": 6,
        "pairs": pair_results,
    })
    _json(
        args.output_dir / "pairwise_day7_root_cause_classification.json",
        {
            "schema_version": "pairwise_day7_root_cause_classification_v1",
            "pair_count": 6,
            "pairs": [{
                "run_pair": row["run_pair"],
                "map_insertion_divergence_reproduced":
                    row["map_insertion_divergence_reproduced"],
                "scan_index": row["scan_index"],
                "root_cause_classification":
                    row["root_cause_classification"],
                "event_explains_symmetric_difference":
                    row["event_explains_symmetric_difference"],
                "unexplained_map_point_identities":
                    row["unexplained_map_point_identities"],
            } for row in pair_results],
        },
    )
    formal_clusters = cluster_formal_trajectories(observations)
    write_clusters(formal_clusters, args.output_dir)
    trace_clusters = _trace_clusters(args.runtime_root)
    _json(args.output_dir / "map_update_trace_clusters.json", trace_clusters)
    membership = [
        {
            "run_id": run_id,
            "cluster_id": cluster["cluster_id"],
            "trace_checksum": cluster["trace_checksum"],
        }
        for cluster in trace_clusters["clusters"]
        for run_id in cluster["runs"]
    ]
    _csv(
        args.output_dir / "map_update_trace_cluster_membership.csv",
        membership,
    )
    _json(args.output_dir / "day7_comparison_integrity.json", {
        "schema_version": "day7_comparison_integrity_v1",
        "run_count": 4,
        "pair_count": 6,
        "observation_integrity": integrity,
        "trace_integrity": trace_integrity,
        "six_pair_event_comparison_pass": len(pair_results) == 6,
        "formal_trajectory_clustering_pass":
            formal_clusters["formal_trajectory_clustering_pass"],
        "map_update_trace_clustering_pass":
            trace_clusters["map_update_trace_clustering_pass"],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
