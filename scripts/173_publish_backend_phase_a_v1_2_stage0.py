#!/usr/bin/env python3
"""Publish the compact Phase A v1.2 Stage-0 audit and snapshot lock."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_phase_a_stage0_artifact import publish_stage0_artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol-lock", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--targeted-pytest-summary", required=True)
    parser.add_argument("--full-pytest-summary", required=True)
    parser.add_argument("--pcl-ctest-summary", required=True)
    args = parser.parse_args()
    result = publish_stage0_artifact(
        root=ROOT,
        protocol_lock=args.protocol_lock,
        cache_root=args.cache_dir,
        run_id=args.run_id,
        targeted_pytest_summary=args.targeted_pytest_summary,
        full_pytest_summary=args.full_pytest_summary,
        pcl_ctest_summary=args.pcl_ctest_summary,
    )
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["decision"]["PHASE_A_V1_2_STAGE0_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
