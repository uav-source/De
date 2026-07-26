#!/usr/bin/env python3
"""Verify Directional Capture Range MVP Day 1 artifacts fail-closed."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from capture_range.verification import verify_capture_range_day1  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=ROOT / "artifacts" / "current" / "directional_capture_range_day1",
    )
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--allow-failed-gate", action="store_true")
    args = parser.parse_args()
    result = verify_capture_range_day1(
        args.artifact_dir,
        repository_root=args.repository_root,
        require_gate_pass=not args.allow_failed_gate,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
