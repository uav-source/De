#!/usr/bin/env python3
"""Run the complete pytest suite and write machine-verifiable provenance."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.test_provenance import run_verified_pytest  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    record = run_verified_pytest(ROOT, args.output)
    print(f"verified pytest status: {record['status']}")
    print(f"return code: {record['return_code']}")
    print(f"passed tests: {record['passed_test_count']}")
    print(f"duration: {record['duration_s']} s")
    print(f"provenance: {args.output}")
    return 0 if int(record["return_code"]) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
