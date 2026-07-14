#!/usr/bin/env python3
"""Run Stage 2B quick, Development, lock, reserved Test, or analysis-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.weak_update_stage2b import (  # noqa: E402
    analyze_existing_stage2b,
    lock_update_analysis,
    run_weak_update_stage2b,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--quick", action="store_true")
    modes.add_argument("--development", action="store_true")
    modes.add_argument("--lock-update", action="store_true")
    modes.add_argument("--test", action="store_true")
    modes.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--update-lock", type=Path)
    parser.add_argument("--development-run-dir", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.resume and args.overwrite:
        parser.error("--resume and --overwrite are mutually exclusive")
    if args.lock_update and args.development_run_dir is None:
        parser.error("--lock-update requires --development-run-dir")
    if args.test and args.update_lock is None:
        parser.error("--test requires --update-lock")
    if args.analyze_only and args.run_dir is None:
        parser.error("--analyze-only requires --run-dir")
    if (args.quick or args.development or args.test) and not args.run_id:
        parser.error("run phases require --run-id")
    return args


def main() -> int:
    args = parse_args()
    if args.lock_update:
        lock = lock_update_analysis(ROOT, args.development_run_dir)
        path = Path(args.development_run_dir) / "update_lock.json"
        print(f"update lock: {path}")
        print("committable update lock: artifacts/current/weak_update_stage2b/locked/update_lock.json")
        print(f"update lock sha256: {hashlib.sha256(path.read_bytes()).hexdigest()}")
        print(f"selected alpha: {lock['selected_attenuation_alpha']}")
        return 0
    if args.analyze_only:
        manifest = analyze_existing_stage2b(ROOT, args.run_dir)
    else:
        phase = "quick" if args.quick else "development" if args.development else "test"
        manifest = run_weak_update_stage2b(
            ROOT, phase, args.run_id, workers=args.workers, resume=args.resume,
            overwrite=args.overwrite, update_lock_path=args.update_lock,
        )
    print(f"stage2b phase: {manifest['phase']}")
    print(f"run id: {manifest['run_id']}")
    print(f"status: {manifest['status']}")
    print(f"sensor-stress blocks: {manifest['sensor_stress_block_count']}")
    print(f"method trials: {manifest['method_trial_count']}")
    print(f"selected alpha: {manifest.get('selected_attenuation_alpha')}")
    if manifest.get("gates"):
        print(json.dumps(manifest["gates"], sort_keys=True, allow_nan=True))
        print(json.dumps(manifest["authorizations"], sort_keys=True))
    return 0 if manifest["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
