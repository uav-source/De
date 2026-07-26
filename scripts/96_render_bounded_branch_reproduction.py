#!/usr/bin/env python3
"""Render the twelve fixed bounded-branch audit figures."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


PLOTS = (
    "four_run_formal_trajectory_cluster_summary.png",
    "pairwise_semantic_mismatch_counts.png",
    "first_formal_divergence_by_pair.png",
    "stage_identity_timeline_all_runs.png",
    "map_content_identity_all_runs.png",
    "map_traversal_identity_all_runs.png",
    "correspondence_identity_all_runs.png",
    "post_update_state_identity_all_runs.png",
    "rebuild_generation_all_runs.png",
    "formal_divergence_window.png",
    "run_pair_stage_classification.png",
    "snapshot_coherence_summary.png",
)


def _save_bar(
    path: Path,
    title: str,
    labels: list[str],
    values: list[float],
    *,
    ylabel: str = "count",
) -> None:
    fig, axis = plt.subplots(figsize=(10, 5))
    axis.bar(range(len(values)), values, color="#35618f")
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.set_xticks(range(len(labels)), labels, rotation=25, ha="right")
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    semantic = _read_json(
        args.comparison_dir / "pairwise_semantic_observation_summary.json"
    )["pairs"]
    stage = _read_json(
        args.comparison_dir / "pairwise_stage_classification.json"
    )["pairs"]
    clusters = _read_json(
        args.comparison_dir / "formal_trajectory_clusters.json"
    )
    labels = [row["pair"] for row in semantic]
    _save_bar(
        output / PLOTS[0],
        "Four-run formal trajectory clusters",
        [row["cluster_id"] for row in clusters["clusters"]],
        [row["size"] for row in clusters["clusters"]],
        ylabel="runs",
    )
    _save_bar(
        output / PLOTS[1],
        "Pairwise semantic observation mismatches",
        labels,
        [row["semantic_mismatch_count"] for row in semantic],
    )
    _save_bar(
        output / PLOTS[2],
        "First formal divergence scan by pair",
        labels,
        [
            next(
                item["first_formal_divergence_scan"]
                for item in stage
                if item["pair"] == row["pair"]
            )
            or 0
            for row in semantic
        ],
        ylabel="scan (0 means none)",
    )
    identity_fields = (
        ("stage_identity_timeline_all_runs.png", "formal_branch_reproduced"),
        ("map_content_identity_all_runs.png", "map_content_before"),
        ("map_traversal_identity_all_runs.png", "map_traversal_before"),
        ("correspondence_identity_all_runs.png", "correspondence"),
        ("post_update_state_identity_all_runs.png", "post_update_state"),
    )
    for filename, field in identity_fields:
        values = []
        for row in stage:
            if field == "formal_branch_reproduced":
                values.append(int(bool(row[field])))
            else:
                values.append(
                    int(row["identity_status"][field] == "DIVERGED")
                )
        _save_bar(
            output / filename,
            f"{field.replace('_', ' ').title()} differences by pair",
            labels,
            values,
            ylabel="difference observed",
        )
    stage_rows = []
    with (
        args.comparison_dir / "pairwise_stage_hash_comparison.csv"
    ).open(encoding="utf-8", newline="") as stream:
        stage_rows = list(csv.DictReader(stream))
    rebuild_values = []
    for pair in labels:
        pair_rows = [row for row in stage_rows if row["pair"] == pair]
        rebuild_values.append(
            sum(
                row.get("map_traversal_before_identity") == "False"
                or row.get("map_traversal_after_identity") == "False"
                for row in pair_rows
            )
        )
    _save_bar(
        output / PLOTS[8],
        "Rebuild-associated traversal identity differences",
        labels,
        rebuild_values,
    )
    formal_count = sum(row["semantic_mismatch_count"] for row in semantic)
    title = (
        "Formal divergence window"
        if formal_count
        else "NO_FORMAL_DIVERGENCE_OBSERVED"
    )
    _save_bar(
        output / PLOTS[9],
        title,
        labels,
        [row["semantic_mismatch_count"] for row in semantic],
    )
    classes = sorted({row["stage_classification"] for row in stage})
    _save_bar(
        output / PLOTS[10],
        "Run-pair stage classification",
        classes,
        [
            sum(row["stage_classification"] == value for row in stage)
            for value in classes
        ],
        ylabel="pairs",
    )
    run_summaries = [
        _read_json(path)
        for path in sorted(args.runtime_root.glob("*/run_summary.json"))
    ]
    _save_bar(
        output / PLOTS[11],
        "Snapshot coherence summary",
        [row["run_id"] for row in run_summaries],
        [row["coherent_snapshot_count"] for row in run_summaries],
        ylabel="coherent snapshots",
    )
    if len(list(output.glob("*.png"))) != len(PLOTS):
        raise RuntimeError("fixed plot count mismatch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

