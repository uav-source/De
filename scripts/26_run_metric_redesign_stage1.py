#!/usr/bin/env python3
"""Run Metric Redesign Stage 1 without modifying legacy Day 1-32 outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.metric_redesign_stage1 import run_stage1  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--quick", action="store_true", help="Run 5 geometry/sensor samples and 10 process trials.")
    modes.add_argument("--full", action="store_true", help="Run 15 geometries, 30 sensor runs, and 150 process trials.")
    modes.add_argument("--analyze-only", action="store_true", help="Rebuild tables and gate report from existing outputs.")
    parser.add_argument("--sweep-config", type=Path, default=ROOT / "configs/redesign/stage1_st_sweep.yaml")
    parser.add_argument("--detector-config", type=Path, default=ROOT / "configs/detector/odi_redesign_stage1.yaml")
    parser.add_argument("--motion-config", type=Path, default=ROOT / "configs/toy_lio/motion_surrogate_stage1.yaml")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mode = "quick" if args.quick else "full" if args.full else "analyze-only"
    manifest = run_stage1(ROOT, mode, args.sweep_config, args.detector_config, args.motion_config)
    print(f"stage1 mode: {mode}")
    print(f"execution status: {manifest['status']}")
    print(f"scientific gate: {manifest['scientific_gate']}")
    print(f"geometry sequences: {manifest['sequence_count']}")
    print(f"independent sensor runs: {manifest['sensor_run_count']}")
    print(f"process trials: {manifest['process_trial_count']}")
    print(f"manifest: results/metric_redesign_stage1/manifests/stage1_manifest.json")
    return 0 if manifest["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
