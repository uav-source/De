#!/usr/bin/env python3
"""Compute Day 6 ODI/AIS/lambda/condition-number CSV files."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from degen_detector.odi_tracker import compute_metrics_for_sequence  # noqa: E402


DEFAULT_SEQUENCES = [
    ROOT / "data/minibench/OC-L0-S01-M1",
    ROOT / "data/minibench/ST-L3-S01-M1",
    ROOT / "data/minibench/CT-L2-S01-M2",
    ROOT / "data/minibench/RT-L4-S01-M1",
]


def load_config(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Detector config must be a mapping: {path}")
    return config


def write_odi_csv(rows: np.ndarray, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows.dtype.names)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row[name].item() for name in fieldnames})


def compute_one(sequence_dir: Path, config_path: Path, out_path: Path) -> np.ndarray:
    observations_path = sequence_dir / "observations.npz"
    if not observations_path.exists():
        raise FileNotFoundError(f"Missing observations file: {observations_path}")
    observations = np.load(observations_path)
    rows = compute_metrics_for_sequence(observations, load_config(config_path))
    write_odi_csv(rows, out_path)
    print(
        f"computed ODI: seq={sequence_dir.name} frames={len(rows)} "
        f"mean_ODI={float(np.mean(rows['ODI'])):.6f} out={out_path}"
    )
    return rows


def write_summary(results, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sequence_id",
        "mean_ODI",
        "median_ODI",
        "mean_AIS",
        "median_lambda_min",
        "median_condition_number",
        "mean_num_points",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for sequence_id, rows in results:
            writer.writerow(
                {
                    "sequence_id": sequence_id,
                    "mean_ODI": float(np.mean(rows["ODI"])),
                    "median_ODI": float(np.median(rows["ODI"])),
                    "mean_AIS": float(np.mean(rows["AIS"])),
                    "median_lambda_min": float(np.median(rows["lambda_min"])),
                    "median_condition_number": float(np.median(rows["condition_number"])),
                    "mean_num_points": float(np.mean(rows["num_points"])),
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seq", type=Path, help="Generated sequence directory.")
    parser.add_argument("--config", type=Path, required=True, help="Detector config path.")
    parser.add_argument("--out", type=Path, help="Output ODI CSV path for one sequence.")
    parser.add_argument("--all", action="store_true", help="Compute ODI for all four Day 14 sequences.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.all:
        results = []
        for sequence_dir in DEFAULT_SEQUENCES:
            out = ROOT / "results/day14/raw" / f"{sequence_dir.name}_odi.csv"
            rows = compute_one(sequence_dir, args.config, out)
            results.append((sequence_dir.name, rows))
        write_summary(results, ROOT / "results/day14/tables/day06_odi_summary.csv")
        return 0

    if args.seq is None:
        raise SystemExit("--seq is required unless --all is used")
    out = args.out or (ROOT / "results/day14/raw" / f"{args.seq.name}_odi.csv")
    compute_one(args.seq, args.config, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

