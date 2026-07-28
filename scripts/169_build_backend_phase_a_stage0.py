#!/usr/bin/env python3
"""Build the locked Phase A v1.2 canonical snapshot cache only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_phase_a_v1_2 import build_stage0_cache


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build 210 Phase A v1.2 snapshots without registration"
    )
    parser.add_argument("--protocol-lock", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--resume", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = build_stage0_cache(
        root=ROOT,
        protocol_lock=args.protocol_lock,
        run_id=args.run_id,
        output_dir=args.output_dir,
        workers=args.workers,
        resume=args.resume,
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
