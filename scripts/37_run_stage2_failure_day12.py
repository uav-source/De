#!/usr/bin/env python3
"""CLI for read-only Stage 2 Day 12 input verification and figures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from eval.stage2_failure_day12 import generate_day12_figures, verify_day12_input  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify-input", action="store_true")
    mode.add_argument("--generate-figures", action="store_true")
    parser.add_argument("--day11b-run-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--output-root", type=Path,
        default=ROOT / "results/stage2_failure_analysis/day12_figures",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    function = verify_day12_input if args.verify_input else generate_day12_figures
    result = function(
        ROOT, args.day11b_run_dir, args.run_id, args.output_root, args.overwrite
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
