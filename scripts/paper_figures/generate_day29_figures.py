#!/usr/bin/env python3
"""Generate all Day 29 real paper figures."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/minibench")
    parser.add_argument("--config-root", type=Path, default=ROOT / "configs/minibench")
    parser.add_argument("--day30-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "docs/paper/figures")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    commands = [
        [
            sys.executable,
            str(ROOT / "scripts/paper_figures/generate_f01_benchmark_geometry.py"),
            "--data-root",
            str(args.data_root),
            "--config-root",
            str(args.config_root),
            "--out-dir",
            str(args.out_dir),
        ],
        [
            sys.executable,
            str(ROOT / "scripts/paper_figures/generate_f03_bias_audit.py"),
            "--day30-root",
            str(args.day30_root),
            "--out-dir",
            str(args.out_dir),
        ],
    ]
    for command in commands:
        result = subprocess.run(command, text=True)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
