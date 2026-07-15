#!/usr/bin/env python3
"""Run the quick-only Stage 2 Day 10 strict no-GT dependency audit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.stage2_failure_day10 import run_stage2_failure_day10  # noqa: E402


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "results/stage2_failure_analysis/day10_quick",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if not args.quick:
        parser.error(
            "Day 10 supports only --quick; Development, Test, Reserved Test, "
            "representative seed, threshold, and ROC modes are unavailable"
        )
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    manifest = run_stage2_failure_day10(
        ROOT,
        args.run_id,
        args.output_root,
        overwrite=args.overwrite,
    )
    passed = bool(manifest["DAY10_NO_GT_AUDIT_PASS"])
    print(f"DAY10_NO_GT_AUDIT_PASS = {str(passed).lower()}")
    print("STAGE2_GATE = INCOMPLETE")
    print("STAGE3_GATE = NOT_STARTED")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
