#!/usr/bin/env python3
"""Run the frozen Directional Capture Range MVP Day 1 smoke matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from capture_range.pipeline import run_capture_range_smoke  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repository-root", type=Path, default=ROOT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--artifact-dir", type=Path)
    args = parser.parse_args()
    result = run_capture_range_smoke(
        args.config,
        args.run_id,
        repository_root=args.repository_root,
        output_root=args.output_root,
        artifact_dir=args.artifact_dir,
    )
    manifest = result["manifest"]
    print(
        json.dumps(
            {
                "DAY1_ENGINEERING_GATE": manifest["DAY1_ENGINEERING_GATE"],
                "DAY2_AUTHORIZED": manifest["DAY2_AUTHORIZED"],
                "artifact_dir": result["artifact_dir"],
                "result_dir": result["result_dir"],
            },
            sort_keys=True,
        )
    )
    return 0 if manifest["DAY1_ENGINEERING_GATE"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
