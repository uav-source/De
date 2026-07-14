#!/usr/bin/env python3
"""Run detector-only Stage 2A quick, development, lock, test, or analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.detector_stage2a import (  # noqa: E402
    analyze_existing_stage2a,
    lock_detector_analysis,
    run_detector_stage2a,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--quick", action="store_true")
    modes.add_argument("--development", action="store_true")
    modes.add_argument("--lock-detector", action="store_true")
    modes.add_argument("--test", action="store_true")
    modes.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--detector-lock", type=Path)
    parser.add_argument("--development-run-dir", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.resume and args.overwrite:
        parser.error("--resume and --overwrite are mutually exclusive")
    if args.lock_detector and args.development_run_dir is None:
        parser.error("--lock-detector requires --development-run-dir")
    if args.test and args.detector_lock is None:
        parser.error("--test requires --detector-lock")
    if args.analyze_only and args.run_dir is None:
        parser.error("--analyze-only requires --run-dir")
    if (args.quick or args.development or args.test) and not args.run_id:
        parser.error("run phases require --run-id")
    return args


def main() -> int:
    args = parse_args()
    if args.lock_detector:
        lock = lock_detector_analysis(ROOT, args.development_run_dir)
        path = Path(args.development_run_dir) / "detector_lock.json"
        print(f"detector lock: {path}")
        print(f"detector lock sha256: {hashlib.sha256(path.read_bytes()).hexdigest()}")
        print(f"ODI trigger threshold: {lock['odi_trigger_threshold']}")
        return 0
    if args.analyze_only:
        manifest = analyze_existing_stage2a(ROOT, args.run_dir)
    else:
        phase = "quick" if args.quick else "development" if args.development else "test"
        manifest = run_detector_stage2a(
            ROOT,
            phase,
            args.run_id,
            ROOT / "configs/redesign/detector_stage2a_common.yaml",
            ROOT / f"configs/redesign/detector_stage2a_{phase}.yaml",
            ROOT / "configs/detector/odi_stage2a.yaml",
            workers=args.workers,
            resume=args.resume,
            overwrite=args.overwrite,
            detector_lock_path=args.detector_lock,
        )
    print(f"stage2a phase: {manifest['phase']}")
    print(f"run id: {manifest['run_id']}")
    print(f"status: {manifest['status']}")
    print(f"sensor runs: {manifest['sensor_run_count']}")
    print(f"process trials: {manifest['process_trial_count']}")
    if manifest.get("gates"):
        print(json.dumps(manifest["gates"], sort_keys=True, allow_nan=True))
        print(json.dumps(manifest["authorizations"], sort_keys=True))
    return 0 if manifest["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
