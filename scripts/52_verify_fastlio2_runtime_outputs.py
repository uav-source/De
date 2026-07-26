#!/usr/bin/env python3
"""Generate the frozen FAST-LIO2 runtime-output source scan and contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.runtime_output_contract import (
    scan_runtime_outputs,
    scan_summary,
    write_source_scan_csv,
)
from fastlio2_adapter.source_lock import runtime_output_allowlist, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fastlio2-root", required=True, type=Path)
    parser.add_argument("--scan-csv", required=True, type=Path)
    parser.add_argument("--allowlist-json", required=True, type=Path)
    parser.add_argument("--summary-json", required=True, type=Path)
    args = parser.parse_args()
    rows = scan_runtime_outputs(args.fastlio2_root)
    summary = scan_summary(rows)
    write_source_scan_csv(args.scan_csv, rows)
    write_json(args.allowlist_json, runtime_output_allowlist())
    write_json(args.summary_json, summary)
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["runtime_output_contract_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
