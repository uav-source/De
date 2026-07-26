#!/usr/bin/env python3
"""Render the 13 required compact Experiment A engineering plots."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


PLOT_NAMES = (
    "map_snapshot_coherence_timeline_run1.png",
    "map_snapshot_coherence_timeline_run2.png",
    "map_validnum_vs_snapshot_count_run1.png",
    "map_validnum_vs_snapshot_count_run2.png",
    "map_content_identity_timeline.png",
    "map_traversal_identity_timeline.png",
    "rebuild_generation_timeline.png",
    "logical_map_mutation_counter_timeline.png",
    "cross_scan_map_count_continuity.png",
    "snapshot_lock_wait_distribution.png",
    "snapshot_locked_copy_cost.png",
    "experiment_a_stage_identity_timeline_v2.png",
    "stage_first_divergence_summary_v2.png",
)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, title: str, x: Sequence[Any], ys: Sequence[tuple[str, Sequence[Any]]]) -> None:
    figure, axis = plt.subplots(figsize=(8, 4.5))
    for label, values in ys:
        axis.plot(x, values, marker="o", markersize=2.5, label=label)
    axis.set_title(title)
    axis.set_xlabel("scan")
    axis.grid(True, alpha=0.25)
    if len(ys) > 1:
        axis.legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def _records(run: Path) -> list[dict[str, Any]]:
    return _json(run / "experiment_a_stage_hash_records_v2.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-1", required=True, type=Path)
    parser.add_argument("--run-2", required=True, type=Path)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    first = _records(args.run_1)
    second = _records(args.run_2)
    scans = [int(row["scan_index"]) for row in first]

    for index, records in enumerate((first, second), start=1):
        coherence = [
            int(
                row["map_before_snapshot_coherence_pass"]
                and row["map_after_snapshot_coherence_pass"]
            )
            for row in records
        ]
        _save(
            args.output_dir
            / f"map_snapshot_coherence_timeline_run{index}.png",
            f"Map snapshot coherence, run {index}",
            scans,
            (("coherent", coherence),),
        )
        _save(
            args.output_dir
            / f"map_validnum_vs_snapshot_count_run{index}.png",
            f"Validnum and coherent-copy count, run {index}",
            scans,
            (
                (
                    "before validnum",
                    [row["map_before_validnum_before"] for row in records],
                ),
                (
                    "before copied",
                    [row["map_before_snapshot_point_count"] for row in records],
                ),
                (
                    "after validnum",
                    [row["map_after_validnum_before"] for row in records],
                ),
                (
                    "after copied",
                    [row["map_after_snapshot_point_count"] for row in records],
                ),
            ),
        )

    comparison_rows: list[dict[str, str]] = []
    with (
        args.comparison_dir
        / "experiment_a_map_snapshot_pairwise_comparison.csv"
    ).open(encoding="utf-8", newline="") as stream:
        comparison_rows = list(csv.DictReader(stream))
    _save(
        args.output_dir / "map_content_identity_timeline.png",
        "Coherent map-content identity",
        scans,
        (
            (
                "before",
                [
                    int(row["map_content_before_identity"] == "True")
                    for row in comparison_rows
                ],
            ),
            (
                "after",
                [
                    int(row["map_content_after_identity"] == "True")
                    for row in comparison_rows
                ],
            ),
        ),
    )
    _save(
        args.output_dir / "map_traversal_identity_timeline.png",
        "Coherent map-traversal identity",
        scans,
        (
            (
                "before",
                [
                    int(row["map_traversal_before_identity"] == "True")
                    for row in comparison_rows
                ],
            ),
            (
                "after",
                [
                    int(row["map_traversal_after_identity"] == "True")
                    for row in comparison_rows
                ],
            ),
        ),
    )
    _save(
        args.output_dir / "rebuild_generation_timeline.png",
        "Rebuild generation",
        scans,
        tuple(
            (
                f"run {index}",
                [row["map_after_rebuild_generation_after"] for row in records],
            )
            for index, records in enumerate((first, second), start=1)
        ),
    )
    _save(
        args.output_dir / "logical_map_mutation_counter_timeline.png",
        "Logical map mutation counter",
        scans,
        tuple(
            (
                f"run {index}",
                [row["map_mutation_counter_after_insertion"] for row in records],
            )
            for index, records in enumerate((first, second), start=1)
        ),
    )
    _save(
        args.output_dir / "cross_scan_map_count_continuity.png",
        "Cross-scan logical map count continuity",
        scans,
        (
            ("run 1 before", [row["map_before_snapshot_point_count"] for row in first]),
            ("run 1 after", [row["map_after_snapshot_point_count"] for row in first]),
            ("run 2 before", [row["map_before_snapshot_point_count"] for row in second]),
            ("run 2 after", [row["map_after_snapshot_point_count"] for row in second]),
        ),
    )

    for filename, field, title in (
        (
            "snapshot_lock_wait_distribution.png",
            "lock_wait_ns",
            "Snapshot lock wait distribution",
        ),
        (
            "snapshot_locked_copy_cost.png",
            "locked_copy_ns",
            "Snapshot locked-copy cost",
        ),
    ):
        values = [
            int(row[f"{prefix}_{field}"])
            for records in (first, second)
            for row in records
            for prefix in ("map_before", "map_after")
        ]
        figure, axis = plt.subplots(figsize=(8, 4.5))
        axis.hist(values, bins=min(20, max(1, len(set(values)))))
        axis.set_title(title)
        axis.set_xlabel("nanoseconds")
        axis.set_ylabel("snapshot count")
        figure.tight_layout()
        figure.savefig(args.output_dir / filename, dpi=150)
        plt.close(figure)

    identity_fields = [
        key
        for key in comparison_rows[0]
        if key.endswith("_identity")
    ]
    figure, axis = plt.subplots(figsize=(10, 5))
    matrix = [
        [int(row[field] == "True") for row in comparison_rows]
        for field in identity_fields
    ]
    image = axis.imshow(matrix, aspect="auto", vmin=0, vmax=1)
    axis.set_yticks(range(len(identity_fields)))
    axis.set_yticklabels(identity_fields, fontsize=7)
    axis.set_xticks(range(len(scans)))
    axis.set_xticklabels(scans, rotation=90, fontsize=6)
    axis.set_title("Experiment A stage identity timeline V2")
    figure.colorbar(image, ax=axis)
    figure.tight_layout()
    figure.savefig(
        args.output_dir / "experiment_a_stage_identity_timeline_v2.png",
        dpi=150,
    )
    plt.close(figure)

    classification = _json(
        args.comparison_dir
        / "experiment_a_map_snapshot_stage_classification.json"
    )
    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.bar(
        [str(classification["first_divergence_stage"])],
        [0 if classification["first_divergence_scan"] is None else 1],
    )
    axis.set_ylim(0, 1.2)
    axis.set_title(
        "First divergence: "
        + str(classification["first_divergence_scan"])
    )
    axis.tick_params(axis="x", labelrotation=15)
    figure.tight_layout()
    figure.savefig(
        args.output_dir / "stage_first_divergence_summary_v2.png", dpi=150
    )
    plt.close(figure)

    print(json.dumps({"plot_count": len(PLOT_NAMES), "plots": PLOT_NAMES}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
