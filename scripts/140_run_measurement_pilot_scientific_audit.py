#!/usr/bin/env python3
"""Generate the independent Measurement Pilot scientific audit artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.measurement_pilot_scientific_audit import run_audit  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", required=True, type=Path)
    parser.add_argument("--pilot-artifact-dir", required=True, type=Path)
    parser.add_argument("--bag", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    manifest = run_audit(
        args.repository_root,
        args.pilot_artifact_dir,
        args.bag,
        args.output_dir,
    )
    print(
        json.dumps(
            {
                "SCIENTIFIC_AUDIT_COMPLETE": manifest["decision"]["SCIENTIFIC_AUDIT_COMPLETE"],
                "PRIMARY_AUDIT_CONCLUSION": manifest["decision"]["PRIMARY_AUDIT_CONCLUSION"],
                "MEASUREMENT_PLAN_STATUS": manifest["decision"]["MEASUREMENT_PLAN_STATUS"],
                "output_dir": str(args.output_dir.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
