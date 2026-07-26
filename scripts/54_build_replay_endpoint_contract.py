#!/usr/bin/env python3
"""Build the deterministic Day 5 replay endpoint contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.replay_endpoint_contract import (  # noqa: E402
    build_contract,
    canonical_json_bytes,
    validate_contract,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick-shack-bag", required=True, type=Path)
    parser.add_argument("--outdoor-bag", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = build_contract(
        {
            "avia_quick_shack": args.quick_shack_bag,
            "avia_outdoor_run_100hz": args.outdoor_bag,
        }
    )
    validate_contract(contract)
    args.output = args.output.expanduser().resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json_bytes(contract))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
