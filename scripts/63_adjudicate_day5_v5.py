#!/usr/bin/env python3
"""Adjudicate frozen Day 5 V5 evidence without running ROS or FAST-LIO2."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.day5_v5_adjudication import (  # noqa: E402
    AdjudicationError,
    adjudicate_archive,
    verify_output_directory,
    write_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Offline correction of the frozen Day 5 startup-sync V5 "
            "clock-counter adjudication"
        )
    )
    parser.add_argument("--v5-audit", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = adjudicate_archive(args.v5_audit)
        write_outputs(result, args.output_dir, overwrite=args.overwrite)
        verification = verify_output_directory(args.output_dir)
        if not verification["pass"]:
            raise AdjudicationError("output hash verification failed")
    except (AdjudicationError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    summary = result["summary"]
    print(
        "DAY5_V5_ADJUDICATION_PASS="
        + str(summary["DAY5_V5_ADJUDICATION_PASS"]).lower()
    )
    print(
        "DAY5_STARTUP_SYNC_V5_PASS="
        + str(summary["DAY5_STARTUP_SYNC_V5_PASS"]).lower()
    )
    print(
        "DAY5_RUNTIME_EQUIVALENCE_PASS="
        + str(summary["DAY5_RUNTIME_EQUIVALENCE_PASS"]).lower()
    )
    print(
        "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED="
        + str(summary["DAY6_QUICK_DIAGNOSTICS_AUTHORIZED"]).lower()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
