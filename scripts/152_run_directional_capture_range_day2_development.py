#!/usr/bin/env python3
"""Run the locked exploratory Day 2 Development feasibility matrix."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from capture_range.day2_development_pipeline import run_day2_development  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--workers", type=int, default=min(24, os.cpu_count() or 1))
    parser.add_argument("--result-dir", type=Path)
    parser.add_argument("--artifact-dir", type=Path)
    args = parser.parse_args()
    output = run_day2_development(args.repository_root, workers=args.workers, result_dir=args.result_dir, artifact_dir=args.artifact_dir)
    print(json.dumps({name: output["manifest"][name] for name in ("DEVELOPMENT_PIPELINE_EXECUTABLE", "DIRECTIONAL_SIGNAL_OBSERVED", "FULL_REASSOCIATION_DIFFERENCE_OBSERVED", "CONFIRMATORY_PROTOCOL_READY")}, sort_keys=True))
    return 0 if output["manifest"]["DEVELOPMENT_PIPELINE_EXECUTABLE"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
