#!/usr/bin/env python3
"""Evaluate Day 8 trajectory metrics from saved TUM, GT, axis, and ODI files."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.metrics import (  # noqa: E402
    align_se3_if_needed,
    compute_ATE,
    compute_RPE,
    compute_axis_error,
    compute_cross_error,
    compute_cumulative_path_length,
    compute_sliding_window_drift_rate,
    load_axis_csv,
    load_tum_pose,
    summarize_odi_table,
)
from degen_detector.weak_direction import compute_drift_alignment  # noqa: E402


DEFAULT_SEQUENCES = [
    ROOT / "data/minibench/OC-L0-S01-M1",
    ROOT / "data/minibench/ST-L3-S01-M1",
    ROOT / "data/minibench/CT-L2-S01-M2",
    ROOT / "data/minibench/RT-L4-S01-M1",
]


WINDOW_FIELDNAMES = [
    "sequence_id",
    "start_idx",
    "end_idx",
    "path_length",
    "axis_error_start",
    "axis_error_end",
    "axis_drift_rate",
    "cross_drift_rate",
    "weak_drift_alignment",
    "mean_ODI",
    "median_ODI",
    "mean_AIS",
    "median_lambda_min",
    "median_lambda_min_clamped",
    "median_condition_number",
]


SUMMARY_FIELDNAMES = [
    "sequence_id",
    "ATE_RMSE",
    "RPE_mean",
    "final_axis_error",
    "final_cross_error",
    "mean_axis_error",
    "mean_cross_error",
    "axis_drift_rate_median",
    "cross_drift_rate_median",
    "weak_drift_alignment_median",
    "weak_drift_alignment_valid_ratio",
    "ODI_mean",
    "ODI_median",
    "AIS_mean",
    "lambda_min_median",
    "lambda_min_clamped_median",
    "condition_number_median",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seq", type=Path, help="Generated sequence directory.")
    parser.add_argument("--odi", type=Path, help="ODI CSV path for one sequence.")
    parser.add_argument("--est", type=Path, help="Estimated TUM trajectory for one sequence.")
    parser.add_argument("--out", type=Path, help="Output window metrics CSV for one sequence.")
    parser.add_argument("--config", type=Path, help="Detector config with window_size/window_stride.")
    parser.add_argument("--all", action="store_true", help="Evaluate all four Day 14 sequences.")
    return parser.parse_args()


def load_config(path: Path | None) -> Dict[str, float]:
    if path is None:
        return {"window_size": 20, "window_stride": 5}
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Detector config must be a mapping: {path}")
    return config


def load_odi_csv(path: Path) -> Dict[str, np.ndarray]:
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8") as handle:
        rows.extend(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"ODI CSV has no rows: {path}")

    columns: Dict[str, np.ndarray] = {}
    for key in rows[0].keys():
        columns[key] = np.asarray([float(row[key]) for row in rows], dtype=float)
    for key in ["timestamp", "ODI", "AIS", "lambda_min", "condition_number"]:
        if key not in columns:
            raise ValueError(f"ODI CSV missing required column {key}: {path}")
        if not np.all(np.isfinite(columns[key])):
            raise ValueError(f"ODI CSV column contains NaN/Inf: {key}")
    return columns


def build_window_rows(
    sequence_id: str,
    axis_error: np.ndarray,
    cross_error: np.ndarray,
    path_length: np.ndarray,
    odi_table: Dict[str, np.ndarray],
    translation_error: np.ndarray,
    window_size: int,
    stride: int,
) -> List[Dict[str, float]]:
    axis_windows = compute_sliding_window_drift_rate(axis_error, path_length, window_size, stride)
    cross_windows = compute_sliding_window_drift_rate(cross_error, path_length, window_size, stride)
    rows: List[Dict[str, float]] = []
    for axis_row, cross_row in zip(axis_windows, cross_windows):
        start = int(axis_row["start_idx"])
        end = int(axis_row["end_idx"])
        sl = slice(start, end + 1)
        weak_trans = representative_weak_translation(odi_table, start, end)
        drift_vector = translation_error[end] - translation_error[start]
        rows.append(
            {
                "sequence_id": sequence_id,
                "start_idx": start,
                "end_idx": end,
                "path_length": float(axis_row["path_length"]),
                "axis_error_start": float(axis_row["error_start"]),
                "axis_error_end": float(axis_row["error_end"]),
                "axis_drift_rate": float(axis_row["drift_rate"]),
                "cross_drift_rate": float(cross_row["drift_rate"]),
                "weak_drift_alignment": compute_drift_alignment(weak_trans, drift_vector),
                "mean_ODI": float(np.mean(odi_table["ODI"][sl])),
                "median_ODI": float(np.median(odi_table["ODI"][sl])),
                "mean_AIS": float(np.mean(odi_table["AIS"][sl])),
                "median_lambda_min": float(np.median(odi_table["lambda_min"][sl])),
                "median_lambda_min_clamped": float(
                    np.median(
                        odi_table["lambda_min_clamped"][sl]
                        if "lambda_min_clamped" in odi_table
                        else np.maximum(odi_table["lambda_min"][sl], 0.0)
                    )
                ),
                "median_condition_number": float(np.median(odi_table["condition_number"][sl])),
            }
        )
    return rows


def representative_weak_translation(odi_table: Dict[str, np.ndarray], start: int, end: int) -> np.ndarray:
    required = ["weak_trans_x", "weak_trans_y", "weak_trans_z", "weak_reliable"]
    if any(key not in odi_table for key in required):
        return np.full(3, np.nan, dtype=float)

    reliable = odi_table["weak_reliable"][start : end + 1].astype(bool)
    if not np.any(reliable):
        return np.full(3, np.nan, dtype=float)

    weak_trans = np.column_stack(
        [
            odi_table["weak_trans_x"][start : end + 1],
            odi_table["weak_trans_y"][start : end + 1],
            odi_table["weak_trans_z"][start : end + 1],
        ]
    )
    local_indices = np.flatnonzero(reliable)
    midpoint = 0.5 * (end - start)
    chosen = local_indices[int(np.argmin(np.abs(local_indices - midpoint)))]
    return weak_trans[chosen]


def evaluate_sequence(
    sequence_dir: Path,
    odi_path: Path,
    est_path: Path,
    out_path: Path,
    config: Dict[str, float],
) -> Dict[str, float]:
    gt = load_tum_pose(sequence_dir / "gt.tum")
    est = align_se3_if_needed(load_tum_pose(est_path), gt)
    axis = load_axis_csv(sequence_dir / "axis.csv")
    odi_table = load_odi_csv(odi_path)

    if axis.shape[0] != gt.shape[0]:
        raise ValueError(f"Axis count does not match GT count: {sequence_dir}")
    if odi_table["ODI"].shape[0] != gt.shape[0]:
        raise ValueError(f"ODI row count does not match GT count: {odi_path}")
    if not np.allclose(odi_table["timestamp"], gt[:, 0], atol=1.0e-6, rtol=0.0):
        raise ValueError(f"ODI timestamps do not match GT: {odi_path}")

    axis_error = compute_axis_error(est, gt, axis)
    cross_error = compute_cross_error(est, gt, axis)
    translation_error = est[:, 1:4] - gt[:, 1:4]
    path_length = compute_cumulative_path_length(gt)
    window_size = int(config.get("window_size", 20))
    stride = int(config.get("window_stride", 5))
    window_rows = build_window_rows(
        sequence_dir.name,
        axis_error,
        cross_error,
        path_length,
        odi_table,
        translation_error,
        window_size,
        stride,
    )
    write_window_metrics_csv(window_rows, out_path)

    rpe = compute_RPE(est, gt, window=1)
    odi_summary = summarize_odi_table(odi_table)
    summary = {
        "sequence_id": sequence_dir.name,
        "ATE_RMSE": compute_ATE(est, gt),
        "RPE_mean": float(np.mean(rpe)) if rpe.size else 0.0,
        "final_axis_error": float(axis_error[-1]),
        "final_cross_error": float(cross_error[-1]),
        "mean_axis_error": float(np.mean(axis_error)),
        "mean_cross_error": float(np.mean(cross_error)),
        "axis_drift_rate_median": float(np.median([row["axis_drift_rate"] for row in window_rows])),
        "cross_drift_rate_median": float(np.median([row["cross_drift_rate"] for row in window_rows])),
    }
    drift_alignment = np.asarray([row["weak_drift_alignment"] for row in window_rows], dtype=float)
    finite_drift_alignment = drift_alignment[np.isfinite(drift_alignment)]
    summary["weak_drift_alignment_median"] = (
        float(np.median(finite_drift_alignment)) if finite_drift_alignment.size else float("nan")
    )
    summary["weak_drift_alignment_valid_ratio"] = float(np.mean(np.isfinite(drift_alignment))) if drift_alignment.size else 0.0
    summary.update(odi_summary)
    return summary


def write_window_metrics_csv(rows: List[Dict[str, float]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=WINDOW_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_summary_csv(rows: List[Dict[str, float]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in SUMMARY_FIELDNAMES})


def default_paths(sequence_dir: Path) -> Tuple[Path, Path, Path]:
    sequence_id = sequence_dir.name
    return (
        ROOT / "results/day14/raw" / f"{sequence_id}_odi.csv",
        ROOT / "results/day14/raw" / f"{sequence_id}_pose_est_toy.tum",
        ROOT / "results/day14/metrics" / f"{sequence_id}_metrics.csv",
    )


def print_summary(summary: Dict[str, float], out_path: Path) -> None:
    print(
        f"metrics: seq={summary['sequence_id']} "
        f"ATE_RMSE={summary['ATE_RMSE']:.6f} "
        f"final_axis={summary['final_axis_error']:.6f} "
        f"final_cross={summary['final_cross_error']:.6f} out={out_path}"
    )


def main() -> int:
    args = parse_args()
    config = load_config(args.config)

    if args.all:
        summaries: List[Dict[str, float]] = []
        for sequence_dir in DEFAULT_SEQUENCES:
            odi_path, est_path, out_path = default_paths(sequence_dir)
            summary = evaluate_sequence(sequence_dir, odi_path, est_path, out_path, config)
            summaries.append(summary)
            print_summary(summary, out_path)
        write_summary_csv(summaries, ROOT / "results/day14/tables/day08_metric_summary.csv")
        return 0

    if args.seq is None:
        raise SystemExit("--seq is required unless --all is used")
    odi_path, est_path, out_path = default_paths(args.seq)
    summary = evaluate_sequence(
        args.seq,
        args.odi or odi_path,
        args.est or est_path,
        args.out or out_path,
        config,
    )
    print_summary(summary, args.out or out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
