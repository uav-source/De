#!/usr/bin/env python3
"""Analyze a complete zero-perturbation Development run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.development_analysis import analyze_development


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(analyze_development(ROOT, run_id=args.run_id))


if __name__ == "__main__":
    main()
