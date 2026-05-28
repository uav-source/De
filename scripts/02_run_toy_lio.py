#!/usr/bin/env python3
"""Run the Day 7 minimum synthetic LIO probe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minibench.toy_lio import (  # noqa: E402
    run_toy_lio,
    save_pose_est_tum,
    write_toy_summary_csv,
)


DEFAULT_SEQUENCES = [
    ROOT / "data/minibench/OC-L0-S01-M1",
    ROOT / "data/minibench/ST-L3-S01-M1",
    ROOT / "data/minibench/CT-L2-S01-M2",
    ROOT / "data/minibench/RT-L4-S01-M1",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seq", type=Path, help="Generated sequence directory.")
    parser.add_argument("--config", type=Path, required=True, help="Detector config path.")
    parser.add_argument("--out", type=Path, help="Output TUM trajectory for one sequence.")
    parser.add_argument("--all", action="store_true", help="Run all four Day 14 sequences.")
    return parser.parse_args()


def run_one(sequence_dir: Path, config_path: Path, out_path: Path):
    result = run_toy_lio(sequence_dir, config_path)
    save_pose_est_tum(result["poses"], out_path)
    summary = result["summary"]
    print(
        f"toy_lio: seq={sequence_dir.name} poses={result['poses'].shape[0]} "
        f"final_axis={summary['final_axis_error']:.6f} "
        f"final_cross={summary['final_cross_error']:.6f} out={out_path}"
    )
    return result


def main() -> int:
    args = parse_args()
    if args.all:
        rows = []
        for sequence_dir in DEFAULT_SEQUENCES:
            out = ROOT / "results/day14/raw" / f"{sequence_dir.name}_pose_est_toy.tum"
            result = run_one(sequence_dir, args.config, out)
            rows.append((sequence_dir.name, result["summary"]))
        write_toy_summary_csv(rows, ROOT / "results/day14/tables/day07_toy_lio_summary.csv")
        return 0

    if args.seq is None:
        raise SystemExit("--seq is required unless --all is used")
    out = args.out or ROOT / "results/day14/raw" / f"{args.seq.name}_pose_est_toy.tum"
    run_one(args.seq, args.config, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

