#!/usr/bin/env python3
"""Render final Day 8 plots from formal analysis outputs only."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day8_final_full_window_analysis import RUN_IDS
from fastlio2_adapter.day8_final_plot_contract import render_plots


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--root-cause-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    coverage = {
        run_id: _read(
            args.runtime_root / run_id
            / "day8_token_capture_coverage_summary.json"
        )
        for run_id in RUN_IDS
    }
    shadows = {
        run_id: _read(
            args.runtime_root / run_id
            / "day8_shadow_accounting_summary.json"
        )
        for run_id in RUN_IDS
    }
    summaries = {
        run_id: _read(args.runtime_root / run_id / "run_summary.json")
        for run_id in RUN_IDS
    }
    documents = {
        "pairwise_final_query_comparison": _csv(
            args.comparison_dir / "pairwise_final_query_comparison.csv"
        ),
        "pairwise_final_strict_identity_summary": _read(
            args.comparison_dir
            / "pairwise_final_strict_identity_summary.json"
        ),
        "pairwise_final_first_divergence": _read(
            args.comparison_dir / "pairwise_final_first_divergence.json"
        ),
        "pairwise_final_root_cause_classification": _read(
            args.root_cause_dir
            / "pairwise_final_root_cause_classification.json"
        ),
        "root_cause_summary": _read(
            args.root_cause_dir / "day8_final_root_cause_summary.json"
        ),
        "token_coverage": {
            "runs": coverage,
            "FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS": all(
                value["FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS"]
                for value in coverage.values()
            ),
        },
        "shadow_accounting": {
            "runs": shadows,
            "SHADOW_STATE_ACCOUNTING_PASS": all(
                value["shadow_state_accounting_pass"]
                for value in shadows.values()
            ),
        },
        "instrumentation_cost": {
            "runs": {
                run_id: {
                    "snapshot_lock_wait_statistics":
                        summary["snapshot_lock_wait_statistics"],
                    "snapshot_copy_cost_statistics":
                        summary["snapshot_copy_cost_statistics"],
                }
                for run_id, summary in summaries.items()
            },
            "instrumentation_timing_perturbation_present": True,
        },
        "null_token_contract_audit": _read(
            args.root_cause_dir / "null_token_semantics_audit.json"
        ),
        "random_replay_route_decision": _read(
            args.root_cause_dir / "random_replay_route_decision.json"
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    materialization = {
        "schema_version": "day8_final_plot_input_materialization_v1",
        "formal_input_paths": [
            "comparison/pairwise_final_query_comparison.csv",
            "comparison/pairwise_final_strict_identity_summary.json",
            "comparison/pairwise_final_first_divergence.json",
            "root_cause/pairwise_final_root_cause_classification.json",
            "root_cause/day8_final_root_cause_summary.json",
            "runtime/day8_token_capture_coverage_summary.json",
            "runtime/day8_shadow_accounting_summary.json",
            "runtime/run_summary.json",
            "root_cause/null_token_semantics_audit.json",
            "root_cause/random_replay_route_decision.json",
        ],
        "alternate_scientific_input_used": False,
        "defaulted_critical_scientific_field_count": 0,
    }
    (args.output_dir / "plot_input_materialization.json").write_text(
        json.dumps(materialization, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = render_plots(documents, args.output_dir)
    return 0 if result["PLOT_INPUT_CONTRACT_PASS"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
