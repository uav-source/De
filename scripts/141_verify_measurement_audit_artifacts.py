#!/usr/bin/env python3
"""Fail-closed verifier for Measurement Pilot scientific audit artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.measurement_pilot_scientific_audit import verify_audit_artifacts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-dir", required=True, type=Path)
    args = parser.parse_args()
    result = verify_audit_artifacts(args.audit_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
