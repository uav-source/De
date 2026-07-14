#!/usr/bin/env python3
"""Run Stage 1c development, lock, and reserved confirmatory test phases."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.metric_redesign_stage1c import (  # noqa: E402
    analyze_existing_stage1c,
    lock_stage1c_analysis,
    run_stage1c,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--quick", action="store_true")
    modes.add_argument("--development", action="store_true")
    modes.add_argument("--test", action="store_true")
    modes.add_argument("--lock-analysis", action="store_true")
    modes.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--analysis-lock", type=Path)
    parser.add_argument("--development-run-dir", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.resume and args.overwrite:
        parser.error("--resume and --overwrite are mutually exclusive")
    if args.lock_analysis and args.development_run_dir is None:
        parser.error("--lock-analysis requires --development-run-dir")
    if args.analyze_only and args.run_dir is None:
        parser.error("--analyze-only requires --run-dir")
    if (args.quick or args.development or args.test) and not args.run_id:
        parser.error("run phases require --run-id")
    if args.test and args.analysis_lock is None:
        parser.error("--test requires --analysis-lock")
    return args


def main() -> int:
    args = parse_args()
    if args.lock_analysis:
        lock = lock_stage1c_analysis(ROOT, args.development_run_dir)
        path = Path(args.development_run_dir) / "analysis_lock.json"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"analysis lock: {path}")
        print(f"analysis lock sha256: {digest}")
        print(f"low-information threshold: {lock['low_axis_information_threshold']}")
        print(f"source tree sha256: {lock['source_tree_sha256']}")
        return 0
    if args.analyze_only:
        manifest = analyze_existing_stage1c(ROOT, args.run_dir)
    else:
        phase = "quick" if args.quick else "development" if args.development else "test"
        manifest = run_stage1c(
            ROOT,
            phase,
            args.run_id,
            ROOT / "configs/redesign/stage1c_common.yaml",
            ROOT / f"configs/redesign/stage1c_{phase}.yaml",
            ROOT / "configs/detector/odi_stage1c.yaml",
            ROOT / "configs/toy_lio/motion_surrogate_stage1c.yaml",
            workers=args.workers,
            resume=args.resume,
            overwrite=args.overwrite,
            analysis_lock_path=args.analysis_lock,
        )
    print(f"stage1c phase: {manifest['phase']}")
    print(f"run id: {manifest['run_id']}")
    print(f"status: {manifest['status']}")
    print(f"independent sensor runs: {manifest['sensor_run_count']}")
    print(f"process trials: {manifest['process_trial_count']}")
    print(f"unique process-noise sequences: {manifest['unique_process_noise_sequences']}")
    if manifest.get("gates"):
        for name in ["engineering", "mechanism", "detector", "prediction"]:
            print(f"{name} gate: {manifest['gates'][name]}")
    if manifest.get("authorizations"):
        print(json.dumps(manifest["authorizations"], sort_keys=True))
    return 0 if manifest["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
