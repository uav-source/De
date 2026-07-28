#!/usr/bin/env python3
"""Run the frozen Development-only anchor validity audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from capture_range.anchor_validity_pipeline import run_anchor_validity_audit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()
    result = run_anchor_validity_audit(
        args.repository_root,
        workers=args.workers,
    )
    print(json.dumps(result["decision"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
