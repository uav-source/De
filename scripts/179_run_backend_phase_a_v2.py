#!/usr/bin/env python3
"""Run Phase A through the single Formal Run Lock v2 interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_phase_a_v2 import dry_run_phase_a_v2, execute_phase_a_v2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run layered-lock Phase A v2")
    parser.add_argument("--formal-run-lock", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def execution_entry(args: argparse.Namespace) -> dict:
    common = {
        "root": ROOT,
        "formal_run_lock": args.formal_run_lock,
        "run_id": args.run_id,
        "output_dir": args.output_dir,
        "workers": args.workers,
    }
    if args.dry_run:
        return dry_run_phase_a_v2(**common)
    return execute_phase_a_v2(**common, resume=args.resume)


def main() -> int:
    result = execution_entry(build_parser().parse_args())
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
