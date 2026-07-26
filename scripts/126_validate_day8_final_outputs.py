#!/usr/bin/env python3
"""Recursively validate token semantics V3 across final JSON/CSV outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day8_token_semantics_v3 import audit_output_paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-root", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    paths: list[Path] = []
    for root in args.scan_root:
        if root.is_file() and root.suffix in {".json", ".csv"}:
            paths.append(root)
        elif root.is_dir():
            paths.extend(sorted(
                path for path in root.rglob("*")
                if path.is_file() and path.suffix in {".json", ".csv"}
            ))
        else:
            raise ValueError(f"scan root does not exist: {root}")
    result = audit_output_paths(paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if result["NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
