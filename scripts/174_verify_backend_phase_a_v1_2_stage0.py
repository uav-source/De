#!/usr/bin/env python3
"""Verify the committed compact Phase A v1.2 Stage-0 artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_phase_a_stage0_artifact import verify_stage0_artifact


def main() -> int:
    result = verify_stage0_artifact(ROOT)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result["verification_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
