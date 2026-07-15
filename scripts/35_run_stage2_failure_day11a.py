#!/usr/bin/env python3
"""Lock preregistered deterministic Stage 2 Day 11 diagnostic cases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.stage2_failure_day11a import run_stage2_failure_day11a  # noqa: E402


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock-cases", action="store_true")
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "results/stage2_failure_analysis/day11a_case_lock",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if not args.lock_cases:
        parser.error("Day 11A requires --lock-cases and does not support replay modes")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    manifest = run_stage2_failure_day11a(
        ROOT,
        args.run_id,
        args.output_root,
        overwrite=args.overwrite,
    )
    passed = bool(manifest["DAY11A_CASE_LOCK_PASS"])
    print(f"DAY11A_CASE_LOCK_PASS = {str(passed).lower()}")
    print(
        "DAY11B_DETERMINISTIC_REPLAY_AUTHORIZED = "
        f"{str(bool(manifest['DAY11B_DETERMINISTIC_REPLAY_AUTHORIZED'])).lower()}"
    )
    print("DAY11_REPLAY_PASS = false")
    print("STAGE2_GATE = INCOMPLETE")
    print("STAGE3_GATE = NOT_STARTED")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
