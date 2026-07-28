#!/usr/bin/env python3
"""Verify the independent PCL backend qualification v2 stopped artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_qualification_v2_verification import (  # noqa: E402
    verify_backend_qualification_v2,
)


def main() -> int:
    result = verify_backend_qualification_v2(ROOT)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verification_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
