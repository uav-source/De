#!/usr/bin/env python3
"""Render sixteen fixed focused branch-localization audit figures."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


PLOTS = (
    "focused_four_run_trajectory_clusters.png",
    "focused_pairwise_semantic_mismatch_counts.png",
    "focused_first_divergence_scan_by_pair.png",
    "focused_stage_identity_timeline.png",
    "focused_raw_input_identity_timeline.png",
    "focused_undistorted_identity_timeline.png",
    "focused_map_content_before_identity.png",
    "focused_map_traversal_before_identity.png",
    "focused_correspondence_identity.png",
    "focused_post_update_state_identity.png",
    "focused_insertion_batch_identity.png",
    "focused_map_content_after_identity.png",
    "focused_divergence_window_scan164.png",
    "focused_divergence_window_scan196.png",
    "focused_stage_classification_summary.png",
    "focused_snapshot_coherence_summary.png",
)


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    semantic = _json(
        args.comparison_dir / "pairwise_full_stream_semantic_summary.json"
    )["pairs"]
    stage = _json(
        args.comparison_dir
        / "pairwise_focused_stage_classification.json"
    )["pairs"]
    clusters = _json(
        args.comparison_dir / "focused_formal_trajectory_clusters.json"
    )
    labels = [row["pair"] for row in semantic]
    _bar(
        args.output_dir / PLOTS[0],
        "Focused four-run formal trajectory clusters",
        [row["cluster_id"] for row in clusters["clusters"]],
        [row["size"] for row in clusters["clusters"]],
        "runs",
    )
    _bar(
        args.output_dir / PLOTS[1],
        "Full-stream semantic mismatches by pair",
        labels,
        [row["semantic_mismatch_count"] for row in semantic],
    )
    _bar(
        args.output_dir / PLOTS[2],
        "First full-stream divergence scan by pair",
        labels,
        [row["first_divergence_scan"] or 0 for row in semantic],
        "scan (0 means none)",
    )
    identity_specs = (
        (PLOTS[3], "formal_branch_reproduced"),
        (PLOTS[4], "raw_lidar"),
        (PLOTS[5], "undistorted_cloud"),
        (PLOTS[6], "map_content_before"),
        (PLOTS[7], "map_traversal_before"),
        (PLOTS[8], "formal_correspondence"),
        (PLOTS[9], "post_update_state"),
        (PLOTS[10], "insertion_batch"),
        (PLOTS[11], "map_content_after"),
    )
    for filename, field in identity_specs:
        if field == "formal_branch_reproduced":
            values = [int(row[field]) for row in stage]
        else:
            values = [
                int(row["identity_status"][field] == "DIVERGED")
                for row in stage
            ]
        _bar(
            args.output_dir / filename,
            f"{field.replace('_', ' ').title()} differences",
            labels,
            values,
            "difference observed",
        )
    with (
        args.comparison_dir / "pairwise_focused_stage_comparison.csv"
    ).open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for filename, scan in ((PLOTS[12], 164), (PLOTS[13], 196)):
        values = []
        for pair in labels:
            row = next(
                item for item in rows
                if item["pair"] == pair
                and int(item["scan_index"]) == scan
            )
            values.append(int(row["formal_divergence_in_scan"] == "True"))
        title = f"Formal divergence at scan {scan}"
        if not any(values):
            title += " — NOT_OBSERVED_IN_CURRENT_FOUR_RUNS"
        _bar(args.output_dir / filename, title, labels, values, "observed")
    classes = sorted({row["stage_classification"] for row in stage})
    _bar(
        args.output_dir / PLOTS[14],
        "Focused stage classification summary",
        classes,
        [sum(row["stage_classification"] == value for row in stage)
         for value in classes],
        "pairs",
    )
    summaries = [
        _json(path)
        for path in sorted(args.runtime_root.glob("*/run_summary.json"))
    ]
    _bar(
        args.output_dir / PLOTS[15],
        "Focused snapshot coherence",
        [row["run_id"] for row in summaries],
        [row["coherent_snapshot_count"] for row in summaries],
        "coherent snapshots",
    )
    if len(list(args.output_dir.glob("*.png"))) != len(PLOTS):
        raise RuntimeError("focused plot count mismatch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

