#!/usr/bin/env python3
"""Guarded cache-backed Phase A v1.2 Stage-1 execution entry."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_phase_a_stage1 import (
    dry_run_stage1,
    execute_stage1_from_cache,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the locked dual-backend Phase A matrix"
    )
    parser.add_argument("--protocol-lock", type=Path, required=True)
    parser.add_argument("--snapshot-lock", type=Path, required=True)
    parser.add_argument("--execution-lock", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def execution_entry(args: argparse.Namespace) -> dict:
    if args.dry_run:
        return dry_run_stage1(
            root=ROOT,
            protocol_lock=args.protocol_lock,
            snapshot_lock=args.snapshot_lock,
            execution_lock=args.execution_lock,
            run_id=args.run_id,
            output_dir=args.output_dir,
            workers=args.workers,
        )
    return execute_stage1_from_cache(
        root=ROOT,
        protocol_lock=args.protocol_lock,
        snapshot_lock=args.snapshot_lock,
        execution_lock=args.execution_lock,
        run_id=args.run_id,
        output_dir=args.output_dir,
        workers=args.workers,
        resume=args.resume,
    )


def main() -> int:
    args = build_parser().parse_args()
    import json

    result = execution_entry(args)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
