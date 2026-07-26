#!/usr/bin/env python3
"""Render the twelve compact Experiment A engineering diagnostic figures."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


PLOTS = (
    (
        "experiment_a_stage_identity_timeline.png",
        None,
        "Stage checksum identity by scan",
    ),
    (
        "raw_lidar_hash_identity_timeline.png",
        "raw_lidar_identity",
        "Raw LiDAR checksum identity by scan",
    ),
    (
        "imu_bundle_hash_identity_timeline.png",
        "imu_bundle_identity",
        "IMU bundle checksum identity by scan",
    ),
    (
        "undistorted_cloud_hash_identity_timeline.png",
        "undistorted_cloud_identity",
        "Undistorted cloud checksum identity by scan",
    ),
    (
        "map_content_before_identity_timeline.png",
        "map_content_before_identity",
        "Map content checksum identity before measurement",
    ),
    (
        "map_traversal_before_identity_timeline.png",
        "map_traversal_before_identity",
        "Map traversal checksum identity before measurement",
    ),
    (
        "correspondence_identity_timeline.png",
        "correspondence_identity",
        "Formal correspondence checksum identity by scan",
    ),
    (
        "post_update_state_identity_timeline.png",
        "post_update_state_identity",
        "Post-update state checksum identity by scan",
    ),
    (
        "insertion_batch_identity_timeline.png",
        "insertion_batch_identity",
        "Map insertion batch checksum identity by scan",
    ),
    (
        "map_content_after_identity_timeline.png",
        "map_content_after_identity",
        "Map content checksum identity after insertion",
    ),
)


def _bool(value: object) -> bool:
    return str(value).strip().lower() == "true"


def _save_identity(
    rows: list[dict[str, str]],
    path: Path,
    field: str | None,
    title: str,
) -> None:
    scans = [int(row["scan_index"]) for row in rows]
    if field is None:
        identity_fields = [
            key for key in rows[0] if key.endswith("_identity")
        ]
        values = [
            sum(_bool(row[key]) for key in identity_fields)
            / len(identity_fields)
            for row in rows
        ]
        ylabel = "Matched stage fraction"
    else:
        values = [1.0 if _bool(row[field]) else 0.0 for row in rows]
        ylabel = "Checksum identity (1=matched)"
    figure, axis = plt.subplots(figsize=(8, 3.5))
    axis.step(scans, values, where="mid", color="#225ea8", linewidth=1.8)
    axis.set(xlabel="Scan index", ylabel=ylabel, title=title)
    axis.set_xlim(min(scans), max(scans))
    axis.set_ylim(-0.05, 1.05)
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison-csv", required=True, type=Path)
    parser.add_argument("--first-divergence", required=True, type=Path)
    parser.add_argument("--run-1-records", required=True, type=Path)
    parser.add_argument("--run-2-records", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with args.comparison_csv.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("comparison CSV is empty")
    for filename, field, title in PLOTS:
        _save_identity(rows, args.output_dir / filename, field, title)

    first = json.loads(args.first_divergence.read_text(encoding="utf-8"))
    stage = str(first.get("first_divergence_stage") or "NONE")
    scan = first.get("first_divergence_scan")
    figure, axis = plt.subplots(figsize=(8, 3.5))
    axis.barh([stage], [0 if scan is None else int(scan)], color="#41b6c4")
    axis.set(
        xlabel="First differing scan index",
        title="First observed stage checksum divergence",
    )
    axis.grid(axis="x", alpha=0.25)
    figure.tight_layout()
    figure.savefig(
        args.output_dir / "stage_first_divergence_summary.png", dpi=150
    )
    plt.close(figure)

    run_1 = json.loads(args.run_1_records.read_text(encoding="utf-8"))
    run_2 = json.loads(args.run_2_records.read_text(encoding="utf-8"))
    scans = [int(row["scan_index"]) for row in run_1]
    figure, axis = plt.subplots(figsize=(8, 3.5))
    axis.plot(
        scans,
        [int(row.get("diagnostic_runtime_ns", 0)) / 1e6 for row in run_1],
        label="run 1",
        linewidth=1.5,
    )
    axis.plot(
        scans,
        [int(row.get("diagnostic_runtime_ns", 0)) / 1e6 for row in run_2],
        label="run 2",
        linewidth=1.5,
    )
    axis.set(
        xlabel="Scan index",
        ylabel="Map snapshot diagnostic time (ms)",
        title="Diagnostic hash runtime cost",
    )
    axis.legend()
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(
        args.output_dir / "diagnostic_hash_runtime_cost.png", dpi=150
    )
    plt.close(figure)
    print("EXPERIMENT_A_PLOT_COUNT=12")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
