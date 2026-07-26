#!/usr/bin/env python3
"""Finalize the focused formal branch localization Gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.focused_branch_stage_localization import (
    focused_run_completeness,
    localization_gate,
)

RUN_IDS = tuple(
    f"multihyp_day6_focused_branch_r{index}" for index in range(1, 5)
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    per_run = {}
    for run_id in RUN_IDS:
        summary = json.loads(
            (args.runtime_root / run_id / "run_summary.json").read_text()
        )
        per_run[run_id] = focused_run_completeness(summary)
    semantic = json.loads(
        (
            args.comparison_dir
            / "pairwise_full_stream_semantic_summary.json"
        ).read_text()
    )["pairs"]
    stage = json.loads(
        (
            args.comparison_dir
            / "pairwise_focused_stage_classification.json"
        ).read_text()
    )["pairs"]
    gate = localization_gate(
        run_complete=[
            per_run[run_id]["run_completeness_pass"]
            for run_id in RUN_IDS
        ],
        semantic=semantic,
        stage=stage,
    )
    value = {
        "schema_version":
            "focused_formal_branch_stage_localization_gate_v1",
        "per_run_completeness": per_run,
        **gate,
        "offline_analysis_code_changed_after_runtime_lock": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(value, sort_keys=True))
    return 0 if gate[
        "focused_formal_branch_localization_execution_pass"
    ] else 1


if __name__ == "__main__":
    raise SystemExit(main())

