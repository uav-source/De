#!/usr/bin/env python3
"""Run smoke or complete zero-perturbation Development measurements."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.pipeline import run_development


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    result = run_development(
        ROOT,
        run_id=args.run_id,
        workers=args.workers,
        smoke=args.smoke,
        resume=args.resume,
    )
    print(result)


if __name__ == "__main__":
    main()
