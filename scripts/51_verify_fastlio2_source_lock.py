#!/usr/bin/env python3
"""Generate and verify Git-aware source locks and FAST runtime inventories."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.source_lock import (
    clear_allowed_runtime_outputs,
    compare_runtime_inventories,
    runtime_output_allowlist,
    runtime_output_inventory,
    snapshot_source_lock,
    source_lock_mismatches,
    write_json,
    write_source_lock,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser("snapshot")
    snapshot.add_argument("--repo", required=True, type=Path)
    snapshot.add_argument("--repo-alias", required=True)
    snapshot.add_argument("--binary", type=Path)
    snapshot.add_argument("--binary-alias")
    snapshot.add_argument("--json", required=True, type=Path)
    snapshot.add_argument("--csv", required=True, type=Path)

    compare = subparsers.add_parser("compare")
    compare.add_argument("--repo", required=True, type=Path)
    compare.add_argument("--repo-alias", required=True)
    compare.add_argument("--binary", type=Path)
    compare.add_argument("--binary-alias")
    compare.add_argument("--expected", required=True, type=Path)
    compare.add_argument("--output", required=True, type=Path)

    allowlist = subparsers.add_parser("write-allowlist")
    allowlist.add_argument("--output", required=True, type=Path)

    inventory = subparsers.add_parser("inventory")
    inventory.add_argument("--repo", required=True, type=Path)
    inventory.add_argument("--output", required=True, type=Path)

    verify = subparsers.add_parser("verify-runtime")
    verify.add_argument("--before", required=True, type=Path)
    verify.add_argument("--after", required=True, type=Path)
    verify.add_argument("--output", required=True, type=Path)

    clear = subparsers.add_parser("clear-runtime")
    clear.add_argument("--repo", required=True, type=Path)
    clear.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "snapshot":
        value = snapshot_source_lock(
            args.repo,
            repo_alias=args.repo_alias,
            binary_path=args.binary,
            binary_path_alias=args.binary_alias,
        )
        write_source_lock(value, args.json, args.csv)
        return 0
    if args.command == "compare":
        expected = json.loads(args.expected.read_text(encoding="utf-8"))
        actual = snapshot_source_lock(
            args.repo,
            repo_alias=args.repo_alias,
            binary_path=args.binary,
            binary_path_alias=args.binary_alias,
        )
        mismatches = source_lock_mismatches(expected, actual)
        write_json(args.output, {"source_lock_pass": not mismatches, "mismatches": mismatches})
        return 0 if not mismatches else 1
    if args.command == "write-allowlist":
        write_json(args.output, runtime_output_allowlist())
        return 0
    if args.command == "inventory":
        write_json(args.output, runtime_output_inventory(args.repo))
        return 0
    if args.command == "verify-runtime":
        before = json.loads(args.before.read_text(encoding="utf-8"))
        after = json.loads(args.after.read_text(encoding="utf-8"))
        result = compare_runtime_inventories(before, after)
        write_json(args.output, result)
        return 0 if result["allowlist_pass"] else 1
    if args.command == "clear-runtime":
        write_json(args.output, {"actions": clear_allowed_runtime_outputs(args.repo)})
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
