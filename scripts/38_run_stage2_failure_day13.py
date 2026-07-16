#!/usr/bin/env python3
"""Run the preregistered Stage 2 Day 13 diagnostic in locked phases."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from eval.stage2_failure_day13 import (  # noqa: E402
    analyze_day13,
    lock_day13_calibration,
    lock_day13_design,
    run_day13_calibration,
    run_day13_evaluation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    phase = parser.add_mutually_exclusive_group(required=True)
    phase.add_argument("--lock-design", action="store_true")
    phase.add_argument("--calibration", action="store_true")
    phase.add_argument("--lock-calibration", action="store_true")
    phase.add_argument("--evaluation", action="store_true")
    phase.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--design-lock", type=Path)
    parser.add_argument("--calibration-lock", type=Path)
    parser.add_argument(
        "--output-root", type=Path,
        default=ROOT / "results/stage2_failure_analysis/day13_new_seed",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.calibration or args.lock_calibration or args.evaluation:
        if args.design_lock is None:
            parser.error("this phase requires --design-lock")
    if args.evaluation and args.calibration_lock is None:
        parser.error("--evaluation requires --calibration-lock")
    if args.resume and args.overwrite:
        parser.error("--resume and --overwrite are mutually exclusive")
    return args


def main() -> int:
    args = parse_args()
    if args.lock_design:
        result = lock_day13_design(
            ROOT, args.run_id, args.output_root, overwrite=args.overwrite
        )
    elif args.calibration:
        result = run_day13_calibration(
            ROOT, args.design_lock, args.run_id, args.output_root,
            resume=args.resume, overwrite=args.overwrite,
        )
    elif args.lock_calibration:
        result = lock_day13_calibration(
            ROOT, args.design_lock, args.run_id, args.output_root
        )
    elif args.evaluation:
        result = run_day13_evaluation(
            ROOT, args.design_lock, args.calibration_lock, args.run_id,
            args.output_root, resume=args.resume, overwrite=args.overwrite,
        )
    else:
        result = analyze_day13(ROOT, args.run_id, output_root=args.output_root)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
