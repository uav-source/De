#!/usr/bin/env python3
"""Verify the Phase A v1.1 implementation lock without formal execution."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_phase_a_v1_1_verification import verify_v1_1_lock


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-final", action="store_true")
    args = parser.parse_args()
    result = verify_v1_1_lock(ROOT, require_final=args.require_final)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verification_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

