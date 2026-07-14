#!/usr/bin/env python3
"""Run isolated, resumable Metric Redesign Stage 1b experiments."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.metric_redesign_stage1b import run_stage1b  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--quick", action="store_true", help="Run 9 sensor runs and 27 process trials.")
    modes.add_argument("--full", action="store_true", help="Run 90 sensor runs and 2700 process trials.")
    modes.add_argument("--analyze-only", action="store_true", help="Rebuild analysis from an existing result run.")
    parser.add_argument("--run-id", help="Run directory name; default is UTC timestamp plus config hash.")
    parser.add_argument("--run-dir", type=Path, help="Existing results run directory for --analyze-only.")
    parser.add_argument("--workers", type=int, default=1, help="Process-trial worker threads per sensor run.")
    parser.add_argument("--resume", action="store_true", help="Resume only missing sensor/process artifacts.")
    parser.add_argument("--overwrite", action="store_true", help="Delete only this run-id's data/results before running.")
    parser.add_argument("--common-config", type=Path, default=ROOT / "configs/redesign/stage1b_common.yaml")
    parser.add_argument(
        "--geometry-config", type=Path, default=ROOT / "configs/redesign/stage1b_geometry_sweep.yaml"
    )
    parser.add_argument(
        "--observation-config", type=Path, default=ROOT / "configs/redesign/stage1b_observation_sweep.yaml"
    )
    parser.add_argument("--detector-config", type=Path, default=ROOT / "configs/detector/odi_stage1b.yaml")
    parser.add_argument(
        "--motion-config", type=Path, default=ROOT / "configs/toy_lio/motion_surrogate_stage1b.yaml"
    )
    args = parser.parse_args()
    if args.analyze_only and args.run_dir is None:
        parser.error("--analyze-only requires --run-dir")
    if not args.analyze_only and args.run_dir is not None:
        parser.error("--run-dir is only valid with --analyze-only")
    if args.resume and args.overwrite:
        parser.error("--resume and --overwrite are mutually exclusive")
    return args


def main() -> int:
    args = parse_args()
    mode = "quick" if args.quick else "full" if args.full else "analyze-only"
    manifest = run_stage1b(
        ROOT,
        mode,
        args.common_config,
        args.geometry_config,
        args.observation_config,
        args.detector_config,
        args.motion_config,
        run_id=args.run_id,
        workers=args.workers,
        resume=args.resume,
        overwrite=args.overwrite,
        analyze_run_dir=args.run_dir,
    )
    print(f"stage1b mode: {mode}")
    print(f"run id: {manifest['run_id']}")
    print(f"execution status: {manifest['status']}")
    print(f"independent sensor runs: {manifest['sensor_run_count']}")
    print(f"process trials: {manifest['process_trial_count']}")
    print(f"engineering gate: {manifest['gates']['engineering']}")
    print(f"mechanism gate: {manifest['gates']['mechanism']}")
    print(f"prediction gate: {manifest['gates']['prediction']}")
    print(f"stage1b decision: {manifest['stage1b_decision']}")
    print(f"manifest: {manifest['result_run_dir']}/manifests/stage1b_manifest.json")
    return 0 if manifest["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
