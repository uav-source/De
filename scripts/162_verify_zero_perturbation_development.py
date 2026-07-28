#!/usr/bin/env python3
"""Independently verify compact zero-perturbation Development artifacts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.verification import verify_development


def main() -> None:
    result = verify_development(ROOT)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["verification_pass"] else 1)


if __name__ == "__main__":
    main()
