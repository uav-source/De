#!/usr/bin/env python3
"""CLI for locked Stage 2 Day 11B verification and replay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from eval.stage2_failure_day11b import (  # noqa: E402
    run_stage2_failure_day11b,
    verify_lock_and_write_plan,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify-lock", action="store_true")
    mode.add_argument("--replay", action="store_true")
    parser.add_argument("--case-lock", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--output-root", type=Path,
        default=ROOT / "results/stage2_failure_analysis/day11b_replay",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    function = verify_lock_and_write_plan if args.verify_lock else run_stage2_failure_day11b
    result = function(ROOT, args.case_lock, args.run_id, args.output_root, args.overwrite)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
