#!/usr/bin/env python3
"""Finalize bounded branch gates from frozen replay and comparison evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.bounded_branch_reproduction import (  # noqa: E402
    branch_gate,
    run_completeness,
)


RUN_IDS = tuple(
    f"multihyp_day6_branch_repro_r{index}" for index in range(1, 5)
)


def day7_decision(stage_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    classifications = {
        row["stage_classification"]
        for row in stage_summaries
        if bool(row["formal_branch_reproduced"])
    }
    scopes = {
        "MAP_STATE_ALREADY_DIVERGED":
            "MAP_MUTATION_REBUILD_AND_IKDTREE_STATE_DIAGNOSTICS",
        "CORRESPONDENCE_CONSTRUCTION_DIVERGED_WITH_MATCHED_INPUT_AND_MAP_CONTENT":
            "FINE_GRAIN_CORRESPONDENCE_AND_THREAD_ORDER_DIAGNOSTICS",
        "IKDTREE_TRAVERSAL_ORDER_ASSOCIATED_CORRESPONDENCE_DIVERGENCE":
            "IKDTREE_TRAVERSAL_ORDER_AND_CORRESPONDENCE_SENSITIVITY",
    }
    selected = [
        scopes[name] for name in sorted(classifications) if name in scopes
    ]
    return {
        "day7_recommended": bool(selected),
        "day7_recommended_scope": (
            selected[0] if len(set(selected)) == 1 else (
                "MULTIPLE_BOUNDED_FORMAL_BRANCH_DIAGNOSTIC_SCOPES"
                if selected else "NONE"
            )
        ),
        "input_pipeline_remediation_recommended": bool(
            classifications
            & {
                "INPUT_STAGE_DIVERGED",
                "UNDISTORTION_OR_IMU_PROCESSING_STAGE_DIVERGED",
            }
        ),
        "day7_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    summaries = [
        json.loads(
            (args.runtime_root / run_id / "run_summary.json").read_text(
                encoding="utf-8"
            )
        )
        for run_id in RUN_IDS
    ]
    per_run = [run_completeness(summary) for summary in summaries]
    semantic = json.loads(
        (
            args.comparison_dir
            / "pairwise_semantic_observation_summary.json"
        ).read_text(encoding="utf-8")
    )["pairs"]
    stage = json.loads(
        (
            args.comparison_dir / "pairwise_stage_classification.json"
        ).read_text(encoding="utf-8")
    )["pairs"]
    gate = branch_gate(
        run_complete=[row["run_completeness_pass"] for row in per_run],
        semantic_summaries=semantic,
        stage_summaries=stage,
    )
    decision = day7_decision(stage) if gate["formal_branch_reproduced"] else {
        "day7_recommended": False,
        "day7_recommended_scope": "NONE",
        "input_pipeline_remediation_recommended": False,
        "day7_authorized": False,
    }
    final = {
        "schema_version": "bounded_formal_branch_reproduction_gate_v1",
        "per_run_completeness": dict(zip(RUN_IDS, per_run)),
        **gate,
        **decision,
        "experiment_a_pass": gate["formal_branch_reproduced"],
        "additional_replay_recommended": False,
        "additional_replay_authorized": False,
        "offline_analysis_code_changed_after_runtime_lock": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(final, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(final, sort_keys=True))
    return 0 if gate["bounded_branch_reproduction_execution_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

