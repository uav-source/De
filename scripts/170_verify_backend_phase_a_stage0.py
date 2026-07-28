#!/usr/bin/env python3
"""Independently verify a Phase A v1.2 Stage-0 cache from disk."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_phase_a_stage0_verification import verify_stage0_cache


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify Stage-0 snapshots without registration"
    )
    parser.add_argument("--protocol-lock", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = verify_stage0_cache(
        root=ROOT, protocol_lock=args.protocol_lock, cache_root=args.cache_dir
    )
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["verification_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
