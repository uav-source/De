#!/usr/bin/env python3
"""Run the independent Backend Qualification v3 artifact verifier."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_qualification_v3_verification import (
    verify_backend_qualification_v3,
)


def main() -> int:
    result = verify_backend_qualification_v3(ROOT)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verification_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
