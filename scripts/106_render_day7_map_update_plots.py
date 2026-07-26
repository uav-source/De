#!/usr/bin/env python3
"""Render the sixteen fixed Day 7 evidence figures."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


RUN_IDS = tuple(
    f"multihyp_day7_map_update_r{index}" for index in range(1, 5)
)
PLOTS = (
    "day7_formal_trajectory_clusters.png",
    "day7_map_update_trace_clusters.png",
    "day7_first_divergent_scan_by_pair.png",
    "day7_map_count_timeline.png",
    "day7_map_content_identity_timeline.png",
    "day7_rebuild_generation_timeline.png",
    "day7_rebuild_active_timeline.png",
    "day7_mutation_outcome_counts.png",
    "day7_direct_vs_logger_routing.png",
    "day7_logger_append_apply_timeline.png",
    "day7_first_divergent_call_events.png",
    "day7_first_divergent_voxel_events.png",
    "day7_map_after_symmetric_difference.png",
    "day7_map_delta_accounting.png",
    "day7_root_cause_classification_summary.png",
    "day7_diagnostic_event_cost.png",
)


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(path: Path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _bar(path: Path, title: str, labels, values, ylabel="count"):
    fig, axis = plt.subplots(figsize=(10, 5))
    axis.bar(range(len(values)), values, color="#355f8a")
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.set_xticks(range(len(labels)), labels, rotation=24, ha="right")
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _lines(path: Path, title: str, series, ylabel: str):
    fig, axis = plt.subplots(figsize=(10, 5))
    for label, x, y in series:
        axis.plot(x, y, marker=".", linewidth=1.2, label=label)
    axis.set_title(title)
    axis.set_xlabel("scan")
    axis.set_ylabel(ylabel)
    axis.grid(alpha=0.25)
    if series:
        axis.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--root-cause-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    formal = _json(args.comparison_dir / "formal_trajectory_clusters.json")
    trace = _json(args.comparison_dir / "map_update_trace_clusters.json")
    first = _json(
        args.comparison_dir / "pairwise_day7_first_divergence.json"
    )["pairs"]
    root = _json(args.root_cause_dir / "root_cause_summary.json")
    _bar(
        args.output_dir / PLOTS[0],
        "Formal trajectory cluster sizes",
        [row["cluster_id"] for row in formal["clusters"]],
        [row["size"] for row in formal["clusters"]],
        "runs",
    )
    _bar(
        args.output_dir / PLOTS[1],
        "Map-update trace cluster sizes",
        [row["cluster_id"] for row in trace["clusters"]],
        [row["size"] for row in trace["clusters"]],
        "runs",
    )
    _bar(
        args.output_dir / PLOTS[2],
        "First map-after divergence scan by pair",
        [row["run_pair"] for row in first],
        [row["scan_index"] or 0 for row in first],
        "scan (0 means none)",
    )

    call_series = []
    generation_series = []
    active_series = []
    outcome_counts = Counter()
    routing_counts = Counter()
    logger_counts = {}
    event_volume = {}
    identity_by_scan = defaultdict(set)
    for run_id in RUN_IDS:
        run = args.runtime_root / run_id
        calls = _rows(run / "day7_map_mutation_call_summaries.csv")
        events = _rows(run / "day7_map_mutation_event_index.csv")
        logger = _rows(run / "day7_rebuild_logger_event_index.csv")
        snapshots = _rows(run / "map_point_identity_snapshot_index.csv")
        call_series.append((
            run_id,
            [int(row["scan_index"]) for row in calls],
            [int(row["map_count_after"]) for row in calls],
        ))
        generation_series.append((
            run_id,
            [int(row["scan_index"]) for row in snapshots],
            [int(row["rebuild_generation"]) for row in snapshots],
        ))
        by_scan = defaultdict(list)
        for row in events:
            scan = int(row["scan_index"])
            by_scan[scan].append(int(row["rebuild_active_at_decision"]))
            outcome_counts[row["formal_outcome"]] += 1
            routing_counts[row["mutation_destination"]] += 1
        active_series.append((
            run_id,
            sorted(by_scan),
            [
                sum(by_scan[scan]) / len(by_scan[scan])
                for scan in sorted(by_scan)
            ],
        ))
        logger_counts[run_id] = (
            sum(row["phase"] == "APPEND" for row in logger),
            sum(row["phase"] == "APPLY" for row in logger),
        )
        event_volume[run_id] = len(events)
        hashes = _rows(run / "map_point_identity_snapshot_hashes.csv")
        for row in hashes:
            if row["snapshot_stage"] == "MAP_AFTER":
                identity_by_scan[int(row["scan_index"])].add(
                    row["point_sha256"]
                )

    _lines(
        args.output_dir / PLOTS[3],
        "Logical map count after each mutation call",
        call_series,
        "logical point count",
    )
    _bar(
        args.output_dir / PLOTS[4],
        "Unique map-after point identities across four runs",
        [str(scan) for scan in sorted(identity_by_scan)],
        [len(identity_by_scan[scan]) for scan in sorted(identity_by_scan)],
        "unique SHA-256 identities",
    )
    _lines(
        args.output_dir / PLOTS[5],
        "Rebuild generation in coherent map snapshots",
        generation_series,
        "generation",
    )
    _lines(
        args.output_dir / PLOTS[6],
        "Fraction of mutation events observed during rebuild",
        active_series,
        "active fraction",
    )
    _bar(
        args.output_dir / PLOTS[7],
        "Map-mutation formal outcome counts",
        list(outcome_counts),
        list(outcome_counts.values()),
    )
    _bar(
        args.output_dir / PLOTS[8],
        "Mutation destination counts",
        list(routing_counts),
        list(routing_counts.values()),
    )
    logger_labels = [
        f"{run_id}:{phase}"
        for run_id in RUN_IDS for phase in ("append", "apply")
    ]
    logger_values = [
        value
        for run_id in RUN_IDS for value in logger_counts[run_id]
    ]
    _bar(
        args.output_dir / PLOTS[9],
        "Rebuild logger append and apply record counts",
        logger_labels,
        logger_values,
    )

    event = _json(
        args.root_cause_dir / "first_divergent_map_mutation_event.json"
    )
    event_labels = [
        "run A outcome",
        "run B outcome",
        "run A destination",
        "run B destination",
    ]
    event_values = [
        int(event.get(name) is not None)
        for name in (
            "run_a_outcome",
            "run_b_outcome",
            "run_a_destination",
            "run_b_destination",
        )
    ]
    title = "First divergent mutation event fields captured"
    if event.get("scan_index") is None:
        title += " — NO_MAP_UPDATE_DIVERGENCE_REPRODUCED"
    _bar(
        args.output_dir / PLOTS[10],
        title,
        event_labels,
        event_values,
        "field present",
    )
    _bar(
        args.output_dir / PLOTS[11],
        "First divergent candidate and voxel identity capture",
        ["candidate SHA-256", "voxel identity"],
        [
            int(bool(event.get("candidate_point_sha256"))),
            int(bool(event.get("voxel_identity"))),
        ],
        "field present",
    )
    symmetric = _rows(
        args.root_cause_dir / "map_after_symmetric_difference.csv"
    )
    side_counts = Counter(row.get("side", "NONE") for row in symmetric)
    _bar(
        args.output_dir / PLOTS[12],
        "Map-after point-set symmetric difference",
        list(side_counts) or ["NONE"],
        list(side_counts.values()) or [0],
        "point identities",
    )
    delta = _rows(
        args.root_cause_dir / "map_mutation_delta_accounting.csv"
    )
    _bar(
        args.output_dir / PLOTS[13],
        "Map-mutation delta accounting failures",
        [row["run_id"] for row in delta],
        [int(row["failure_count"]) for row in delta],
        "failed calls",
    )
    classes = Counter(
        row["root_cause_classification"]
        for row in first
    )
    _bar(
        args.output_dir / PLOTS[14],
        "Pairwise map-update root-cause classifications",
        list(classes),
        list(classes.values()),
        "pairs",
    )
    _bar(
        args.output_dir / PLOTS[15],
        "Diagnostic mutation event volume by run",
        list(event_volume),
        list(event_volume.values()),
        "captured events (cost proxy)",
    )
    if len(list(args.output_dir.glob("day7_*.png"))) != 16:
        raise RuntimeError("Day 7 plot count mismatch")
    if root["instrumentation_timing_perturbation_present"] is not True:
        raise RuntimeError("instrumentation perturbation disclosure missing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
