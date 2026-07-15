#!/usr/bin/env python3
"""Run the quick-only Stage 2 failure-mechanism Day 8 logger."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.stage2_failure_day8 import run_stage2_failure_day8  # noqa: E402


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true", help="run the Day 8 engineering fixture")
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "results/stage2_failure_analysis/day8_quick",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if not args.quick:
        parser.error("Day 8 supports only --quick; formal and Reserved Test modes are unavailable")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    manifest = run_stage2_failure_day8(
        ROOT,
        args.run_id,
        args.output_root,
        overwrite=args.overwrite,
    )
    passed = bool(manifest["DAY8_LOGGING_PASS"])
    print(f"DAY8_LOGGING_PASS = {str(passed).lower()}")
    print("STAGE2_GATE = INCOMPLETE")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
