#!/usr/bin/env python3
"""Verify the independent-backend qualification artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_qualification_verification import (
    verify_backend_qualification,
)


def main() -> None:
    result = verify_backend_qualification(ROOT)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["verification_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
