#!/usr/bin/env python3
"""Render standalone engineering-diagnostic plots for Day 6 Fallback."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day6_fallback_functional_diagnostics import (  # noqa: E402
    Day6FallbackError,
    SUB_RUN_IDS,
    write_json,
)
from fastlio2_adapter.day6_reference_alignment import load_jsonl  # noqa: E402


PLOT_NAMES = (
    "odi_timeline_run1.png",
    "odi_timeline_run2.png",
    "odi_timeline_run3.png",
    "ais_timeline_run1.png",
    "condition_number_timeline_run1.png",
    "detector_flags_timeline_run1.png",
    "weak_direction_angle_timeline_run1.png",
    "detector_latency_distribution_run1.png",
    "metric_quantiles_across_runs.png",
    "flag_fractions_across_runs.png",
    "reference_vs_run_odi_difference.png",
    "cross_run_direction_angle_distribution.png",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def save_line(
    path: Path,
    x: list[float],
    y: list[float],
    *,
    title: str,
    ylabel: str,
) -> None:
    figure = plt.figure(figsize=(10, 4.8))
    axes = figure.add_axes((0.10, 0.14, 0.86, 0.78))
    axes.plot(x, y, linewidth=1.1)
    axes.set_title(title)
    axes.set_xlabel("Scan index")
    axes.set_ylabel(ylabel)
    axes.grid(True, alpha=0.25)
    figure.savefig(path, dpi=150)
    plt.close(figure)


def main() -> int:
    args = parse_args()
    result_root = args.result_root.expanduser().resolve()
    output = args.output_dir.expanduser().resolve()
    if output.exists():
        raise SystemExit(f"ERROR: output directory exists: {output}")
    output.mkdir(parents=True, exist_ok=False)
    runs = [
        load_jsonl(
            result_root
            / run_id
            / "detector_diagnostics/adapter_detector_outputs_v3.jsonl"
        )
        for run_id in SUB_RUN_IDS
    ]
    for index, rows in enumerate(runs, start=1):
        save_line(
            output / f"odi_timeline_run{index}.png",
            [float(row["scan_index"]) for row in rows],
            [
                float(row["odi_trans"])
                if row["odi_trans"] is not None
                else math.nan
                for row in rows
            ],
            title=f"ODI timeline, replay {index}",
            ylabel="ODI",
        )
    run1 = runs[0]
    save_line(
        output / "ais_timeline_run1.png",
        [float(row["scan_index"]) for row in run1],
        [
            float(row["ais_trans"]) if row["ais_trans"] is not None else math.nan
            for row in run1
        ],
        title="AIS timeline, replay 1",
        ylabel="AIS",
    )
    save_line(
        output / "condition_number_timeline_run1.png",
        [float(row["scan_index"]) for row in run1],
        [
            (
                float(row["condition_number_trans"])
                if row["condition_number_trans"] is not None
                else math.nan
            )
            for row in run1
        ],
        title="Condition number timeline, replay 1",
        ylabel="Condition number",
    )

    figure = plt.figure(figsize=(10, 4.8))
    axes = figure.add_axes((0.10, 0.14, 0.86, 0.78))
    scans = [int(row["scan_index"]) for row in run1]
    for offset, field in enumerate(
        (
            "valid",
            "primary_direction_stable",
            "degeneracy_triggered",
            "actionable_direction",
        )
    ):
        axes.step(
            scans,
            [int(bool(row[field])) + offset * 1.2 for row in run1],
            where="post",
            label=field,
            linewidth=1.0,
        )
    axes.set_title("Detector flag timelines, replay 1")
    axes.set_xlabel("Scan index")
    axes.set_ylabel("Flag state with vertical offsets")
    axes.legend(loc="upper right")
    axes.grid(True, alpha=0.25)
    figure.savefig(output / "detector_flags_timeline_run1.png", dpi=150)
    plt.close(figure)

    direction_rows = read_csv(
        result_root
        / SUB_RUN_IDS[0]
        / "detector_diagnostics/direction_continuity_records.csv"
    )
    save_line(
        output / "weak_direction_angle_timeline_run1.png",
        [float(row["scan_index"]) for row in direction_rows],
        [float(row["sign_invariant_angle_deg"]) for row in direction_rows],
        title="Sign-invariant weak-direction angle, replay 1",
        ylabel="Angle (degrees)",
    )

    latency_rows = read_csv(
        result_root
        / SUB_RUN_IDS[0]
        / "detector_diagnostics/detector_latency_records.csv"
    )
    figure = plt.figure(figsize=(8, 4.8))
    axes = figure.add_axes((0.12, 0.14, 0.84, 0.78))
    axes.hist(
        [
            float(row["adapter_total_call_latency_ns"]) / 1e6
            for row in latency_rows
        ],
        bins=40,
        alpha=0.65,
        label="adapter total",
    )
    axes.hist(
        [
            float(row["direct_production_call_latency_ns"]) / 1e6
            for row in latency_rows
        ],
        bins=40,
        alpha=0.55,
        label="direct production",
    )
    axes.set_title("Post-replay detector call latency, replay 1")
    axes.set_xlabel("Call latency (ms)")
    axes.set_ylabel("Record count")
    axes.legend()
    axes.grid(True, alpha=0.25)
    figure.savefig(output / "detector_latency_distribution_run1.png", dpi=150)
    plt.close(figure)

    metric_names = (
        "odi_trans",
        "ais_trans",
        "lambda_min_trans",
        "primary_eigengap_ratio",
    )
    figure = plt.figure(figsize=(9, 5))
    axes = figure.add_axes((0.12, 0.18, 0.84, 0.74))
    width = 0.22
    positions = np.arange(len(metric_names), dtype=float)
    for run_index, rows in enumerate(runs):
        medians = []
        for metric in metric_names:
            values = [
                float(row[metric])
                for row in rows
                if row.get(metric) is not None
            ]
            medians.append(float(np.median(values)))
        axes.bar(
            positions + (run_index - 1) * width,
            medians,
            width=width,
            label=f"replay {run_index + 1}",
        )
    axes.set_title("Metric medians across replays")
    axes.set_xticks(positions)
    axes.set_xticklabels(metric_names, rotation=20, ha="right")
    axes.set_ylabel("Median value")
    axes.legend()
    axes.grid(True, axis="y", alpha=0.25)
    figure.savefig(output / "metric_quantiles_across_runs.png", dpi=150)
    plt.close(figure)

    flag_names = (
        "valid",
        "primary_direction_stable",
        "degeneracy_triggered",
        "actionable_direction",
    )
    figure = plt.figure(figsize=(9, 5))
    axes = figure.add_axes((0.12, 0.18, 0.84, 0.74))
    for run_index, rows in enumerate(runs):
        fractions = [
            sum(bool(row[field]) for row in rows) / len(rows)
            for field in flag_names
        ]
        axes.bar(
            positions + (run_index - 1) * width,
            fractions,
            width=width,
            label=f"replay {run_index + 1}",
        )
    axes.set_title("Detector flag fractions across replays")
    axes.set_xticks(positions)
    axes.set_xticklabels(flag_names, rotation=20, ha="right")
    axes.set_ylabel("True fraction")
    axes.set_ylim(0.0, 1.05)
    axes.legend()
    axes.grid(True, axis="y", alpha=0.25)
    figure.savefig(output / "flag_fractions_across_runs.png", dpi=150)
    plt.close(figure)

    comparison = result_root / "comparison"
    reference_rows = read_csv(
        comparison / f"reference_alignment_{SUB_RUN_IDS[0]}.csv"
    )
    reference_odi_rows = [
        row
        for row in reference_rows
        if row.get("odi_trans_absolute_difference") not in (None, "")
    ]
    save_line(
        output / "reference_vs_run_odi_difference.png",
        [float(row["scan_index"]) for row in reference_odi_rows],
        [
            float(row["odi_trans_absolute_difference"])
            for row in reference_odi_rows
        ],
        title="Absolute ODI difference from frozen reference, replay 1",
        ylabel="Absolute ODI difference",
    )

    cross_rows = read_csv(comparison / "cross_run_aligned_metrics.csv")
    figure = plt.figure(figsize=(8, 4.8))
    axes = figure.add_axes((0.12, 0.14, 0.84, 0.78))
    for pair in ("r1-r2", "r1-r3", "r2-r3"):
        values = [
            float(row["weak_direction_sign_invariant_angle_deg"])
            for row in cross_rows
            if row["pair"] == pair
            and row["weak_direction_sign_invariant_angle_deg"]
        ]
        axes.hist(values, bins=36, alpha=0.45, label=pair)
    axes.set_title("Cross-replay sign-invariant direction angles")
    axes.set_xlabel("Angle (degrees)")
    axes.set_ylabel("Aligned record count")
    axes.legend()
    axes.grid(True, alpha=0.25)
    figure.savefig(
        output / "cross_run_direction_angle_distribution.png", dpi=150
    )
    plt.close(figure)

    missing = [name for name in PLOT_NAMES if not (output / name).is_file()]
    summary = {
        "schema_version": "day6_diagnostic_plot_summary_v1",
        "plot_count": len(PLOT_NAMES) - len(missing),
        "required_plot_count": len(PLOT_NAMES),
        "plot_names": list(PLOT_NAMES),
        "missing_plot_names": missing,
        "engineering_diagnostics_only": True,
        "plots_complete": not missing,
    }
    write_json(output / "plot_summary.json", summary)
    if missing:
        raise Day6FallbackError(f"required plots are missing: {missing}")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Day6FallbackError, OSError, KeyError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
