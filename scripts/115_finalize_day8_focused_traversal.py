#!/usr/bin/env python3
"""Finalize the bounded Day 8 focused traversal witness remediation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter import day8_range_query as range_query
from fastlio2_adapter.day8_focused_traversal_remediation import (
    RUN_IDS,
    evaluate_focused_gate,
)
from fastlio2_adapter.day8_range_query import validate_run_query_trace


MAIN_RUN_ID = "multihyp_day8_focused_traversal_witness_v1"


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--root-cause-dir", required=True, type=Path)
    parser.add_argument("--plots-dir", required=True, type=Path)
    parser.add_argument("--execution-evidence", required=True, type=Path)
    parser.add_argument("--authorization", required=True, type=Path)
    parser.add_argument("--run-lock", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    execution = _read(args.execution_evidence)
    authorization = _read(args.authorization)
    lock = _read(args.run_lock)
    comparison = _read(
        args.comparison_dir / "day8_comparison_summary.json"
    )
    root = _read(args.root_cause_dir / "day8_root_cause_summary.json")
    pairwise = _read(
        args.root_cause_dir
        / "pairwise_focused_root_cause_classification.json"
    )
    pair_first = _read(
        args.comparison_dir
        / "pairwise_focused_first_query_divergence.json"
    )
    previous = _read(
        args.root_cause_dir
        / "first_divergent_query_previous_identity.json"
    )
    witness = _read(
        args.root_cause_dir / "missing_expected_point_witness.json"
    )
    focused_coverage = _read(
        args.root_cause_dir
        / "first_divergent_query_token_coverage_gate.json"
    )
    synthetic = _read(
        args.comparison_dir / "day8_focused_synthetic_validation.json"
    )
    range_query.DETAIL_START = 156
    range_query.DETAIL_END = 158
    summaries = {
        run_id: _read(args.runtime_root / run_id / "run_summary.json")
        for run_id in RUN_IDS
    }
    validations = {
        run_id: validate_run_query_trace(args.runtime_root / run_id)
        for run_id in RUN_IDS
    }
    coverages = {
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
    classifications = [
        item["classification"] for item in pairwise["pairs"]
    ]
    explanatory = {
        "DELETION_FLAG_VISIBILITY_DIVERGED",
        "REBUILD_SUBTREE_VISIBILITY_DIVERGED",
        "TREE_TRAVERSAL_PRUNING_DIVERGED",
        "FULL_COVER_SUBTREE_FLATTEN_RESULT_DIVERGED",
    }
    context_localized = bool(classifications) and all(
        value in explanatory for value in classifications
    )
    run_complete = all(
        summary.get("complete") is True
        and summary.get("lidar_callback_count") == 491
        and summary.get("imu_callback_count") == 9953
        and summary.get("runtime_scan_count") == 490
        and summary.get("observation_record_count") == 487
        and summary.get("stage_hash_record_count") == 11
        and summary.get("coherent_snapshot_count") == 22
        and summary.get("incoherent_snapshot_count") == 0
        and summary.get("tap_drop_count") == 0
        and summary.get("writer_error_count") == 0
        and summary.get("ground_truth_topic_count") == 0
        for summary in summaries.values()
    )
    scan157_pass = all(
        value["scan157_token_coverage_pass"] is True
        and value["scan157_query_count"]
        == value["scan157_query_with_summary_count"]
        == value["scan157_query_with_detailed_token_count"]
        for value in coverages.values()
    )
    shadow_pass = all(
        value["shadow_state_accounting_pass"] is True
        and value["shadow_mutation_delta_failure_count"] == 0
        and value["shadow_state_closure_failure_count"] == 0
        for value in shadows.values()
    )
    previous_pass = all((
        previous.get("previous_query_equal") is True,
        previous.get("previous_shadow_state_equal") is True,
        previous.get("previous_formal_result_equal") is True,
        previous.get("previous_traversal_summary_equal") is True,
    ))
    immutable = all(
        _read(
            args.runtime_root / run_id
            / "day8_diagnostic_immutability_summary.json"
        ).get("diagnostic_readonly_scope_pass") is True
        for run_id in RUN_IDS
    )
    gate = evaluate_focused_gate(
        authorization_pass=execution[
            "DAY8_FOCUSED_TRAVERSAL_AUTHORIZATION_PASS"
        ],
        shadow_adjudication_pass=execution[
            "SOURCE_DAY8_SHADOW_DELTA_ADJUDICATION_PASS"
        ],
        targeted_test_pass=execution["DEGEN_TARGETED_TEST_PASS"],
        full_test_pass=execution["DEGEN_FULL_TEST_PASS"],
        fast_source_lock_pass=execution["FAST_SOURCE_LOCK_PASS"],
        fast_binary_lock_pass=execution["FAST_BINARY_LOCK_PASS"],
        formal_logic_unchanged_pass=execution[
            "FORMAL_RANGE_SEARCH_LOGIC_UNCHANGED_PASS"
        ],
        synthetic_pass=synthetic[
            "DAY8_FOCUSED_SYNTHETIC_VALIDATION_PASS"
        ],
        run_complete_pass=run_complete,
        scan157_coverage_pass=scan157_pass,
        shadow_accounting_pass=shadow_pass,
        six_pair_pass=pairwise["pair_count"] == 6,
        previous_identity_pass=previous_pass,
        first_divergence_coverage_pass=focused_coverage[
            "first_divergent_query_detailed_token_coverage_pass"
        ],
        witness_pass=witness["witness_count"] > 0,
        classification_complete=len(classifications) == 6 and all(
            value != "EVIDENCE_GAP" for value in classifications
        ),
        offline_analysis_lock_pass=execution[
            "OFFLINE_ANALYSIS_LOCK_PASS"
        ],
        immutable_pass=immutable,
        no_tap_drop_pass=all(
            value.get("tap_drop_count") == 0 for value in summaries.values()
        ),
        no_writer_error_pass=all(
            value.get("writer_error_count") == 0
            for value in summaries.values()
        ),
        no_gt_pass=all(
            value.get("ground_truth_topic_count") == 0
            for value in summaries.values()
        ),
        diff_scope_pass=execution["DIFF_SCOPE_PASS"],
        audit_scope_pass=execution["AUDIT_PACKAGE_SCOPE_PASS"],
    )
    completeness = (
        comparison["shadow_state_accounting_pass"] is True
        and comparison["formal_query_completeness_failure_count"] > 0
        and focused_coverage[
            "first_divergent_query_detailed_token_coverage_pass"
        ]
    )
    execution_pass = gate["DAY8_FOCUSED_TRAVERSAL_EXECUTION_PASS"]
    final = {
        **gate,
        "main_run_id": MAIN_RUN_ID,
        "source_day8_audit_sha256": lock["source_day8_audit_sha256"],
        "remediation_authorization_sha256":
            lock["remediation_authorization_sha256"],
        "SOURCE_DAY8_SHADOW_DELTA_ADJUDICATION_PASS": execution[
            "SOURCE_DAY8_SHADOW_DELTA_ADJUDICATION_PASS"
        ],
        "NULL_TOKEN_SEMANTICS_PASS": execution[
            "NULL_TOKEN_SEMANTICS_PASS"
        ],
        "FOUR_REPLAY_RUNS_COMPLETE_PASS": run_complete,
        "SCAN157_TOKEN_COVERAGE_PASS": scan157_pass,
        "SHADOW_STATE_ACCOUNTING_PASS": shadow_pass,
        "SIX_PAIR_RANGE_QUERY_COMPARISON_PASS": pairwise["pair_count"] == 6,
        "PREVIOUS_QUERY_IDENTITY_CHECK_COMPLETE": previous_pass,
        "FIRST_DIVERGENT_QUERY_DETAILED_TOKEN_COVERAGE_PASS":
            focused_coverage[
                "first_divergent_query_detailed_token_coverage_pass"
            ],
        "FORMAL_RANGE_QUERY_COMPLETENESS_VIOLATION_OBSERVED": completeness,
        "IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED":
            context_localized,
        "DAY8_IKDTREE_RANGE_SEARCH_CONTEXT_PASS":
            execution_pass and context_localized,
        "DAY9_RECOMMENDED": execution_pass and context_localized,
        "DAY9_RECOMMENDED_SCOPE":
            "GPT_AUDIT_OF_FOCUSED_QUERY_PATH_EVIDENCE_ONLY",
        "DAY9_AUTHORIZED": False,
        "STAGE2_GATE": "FAIL",
        "TRANSITION": "PIVOT",
        "HARMFUL_BIAS_DETECTABILITY_STATUS":
            "NOT_EVALUATED_DAY8_FOCUSED_TRAVERSAL_WITNESS",
        "DETECTOR_CALLED": False,
        "GT_USED": False,
        "FORMAL_SEARCH_LOGIC_MODIFIED": False,
        "THREAD_CONFIGURATION_MODIFIED": False,
        "COMMIT_PERFORMED": False,
        "PUSH_PERFORMED": False,
        "OFFLINE_ANALYSIS_CODE_CHANGED_AFTER_RUNTIME_LOCK": False,
        "instrumentation_timing_perturbation_present": True,
        "shadow_replay_participates_in_fast_decisions": False,
        "query_completeness_violation_is_diagnostic_not_bug_proof": True,
        "per_run_summary": summaries,
        "per_run_validation": validations,
        "per_run_token_coverage": coverages,
        "per_run_shadow_accounting": shadows,
        "pairwise_first_divergence": pair_first["pairs"],
        "pairwise_root_cause": pairwise["pairs"],
        "root_cause_summary": root,
        "missing_expected_point_witness": witness,
    }
    final_path = args.output_dir / "day8_focused_final_gate.json"
    _write(final_path, final)
    first = root.get("first_divergent_query")
    report = f"""# Day 8 Focused Traversal Witness Remediation Report

## Outcome

`DAY8_FOCUSED_TRAVERSAL_EXECUTION_PASS={str(execution_pass).lower()}` and
`IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED={str(context_localized).lower()}`.

## Required answers

1. Scan 157 had no source tokens because the source detailed window was
   160--163.
2. Missing/window-excluded tokens now resolve to an explicit NOT_CAPTURED
   status; empty lists can no longer prove equal traces.
3. The run2 47/46 discrepancy was representative-level versus full logical
   voxel replacement accounting: a two-member voxel becomes one member.
4. No runtime trace change was required; existing event and snapshot fields
   uniquely adjudicated the delta.
5. Query summaries remain 155--165; detailed tokens are exactly 156--158.
6. Four fixed replay runs complete: `{str(run_complete).lower()}`.
7. Scan 157 full query token coverage: `{str(scan157_pass).lower()}`.
8. First formal query divergence: `{json.dumps(first, sort_keys=True)}`.
9. Pairwise query input identity is recorded in the focused pair evidence.
10. Shadow member equality is recorded and shadow accounting passed:
    `{str(shadow_pass).lower()}`.
11. Expected-member visit evidence is recorded in
    `missing_expected_point_witness.json`.
12. If visited, deleted/tree_deleted/inside/returned flags are preserved.
13. If unvisited, the first node-range, relation, and child-path difference is
    preserved in the traversal-diff CSV.
14. Rebuild active/generation context is preserved per query and token.
15. Formal completeness violation reproduced: `{str(completeness).lower()}`.
16. Range-search context root cause localized:
    `{str(context_localized).lower()}`.
17. `FORMAL_IKDTREE_BUG_PROVEN=false`.
18. `DATA_RACE_PROVEN=false`.
19. Read-only instrumentation may perturb timing and scheduling.
20. Day 9 recommendation: `{str(final["DAY9_RECOMMENDED"]).lower()}` within
    `{final["DAY9_RECOMMENDED_SCOPE"]}`.
21. Day 9 remains unauthorized until a separate GPT audit grants it.

Shadow replay is offline-only and never participates in FAST-LIO2 decisions.
Detector, ODI/AIS, weak direction, feedback, GT, commit, and push were not used.
"""
    report_path = (
        ROOT
        / "docs/harmful_bias/day8_focused_traversal_remediation_report.md"
    )
    report_path.write_text(report, encoding="utf-8")
    manifest = {
        "schema_version":
            "day8_focused_traversal_remediation_manifest_v1",
        "authorization_sha256": _sha256(args.authorization),
        "source_day8_audit_sha256": lock["source_day8_audit_sha256"],
        "shadow_delta_adjudication_sha256":
            lock["shadow_delta_adjudication_sha256"],
        "null_token_semantics_version": "day8_token_capture_status_v1",
        "query_summary_window": [155, 165],
        "detailed_token_window": [156, 158],
        "degen_identity": {
            "branch": lock["degen_branch"], "head": lock["degen_head"],
            "diff_sha256": lock["degen_diff_sha256"],
        },
        "fast_identity": {
            "branch": lock["fast_branch"], "head": lock["fast_head"],
            "diff_sha256": lock["fast_diff_sha256"],
            "binary_sha256": lock["fast_binary_sha256"],
        },
        "run_ids": list(RUN_IDS),
        "per_run_summary": summaries,
        "per_run_validation": validations,
        "per_run_token_coverage": coverages,
        "per_run_shadow_accounting": shadows,
        "pairwise_first_divergence": pair_first["pairs"],
        "pairwise_root_cause": pairwise["pairs"],
        "first_divergent_query": first,
        "missing_expected_point_witness": witness,
        "formal_query_completeness_violation_observed": completeness,
        "root_cause_localized": context_localized,
        "offline_analysis_lock_pass": execution[
            "OFFLINE_ANALYSIS_LOCK_PASS"
        ],
        "detector_called": False,
        "GT": False,
        "commit": False,
        "push": False,
        "day8_pass": execution_pass,
        "day9_recommended": final["DAY9_RECOMMENDED"],
        "day9_authorized": False,
        "gates": final,
        "plot_count": len(list(args.plots_dir.glob("*.png"))),
        "final_gate_sha256": _sha256(final_path),
        "report_sha256": _sha256(report_path),
    }
    _write(
        ROOT
        / "manifests/harmful_bias/"
        "day8_focused_traversal_remediation_manifest.json",
        manifest,
    )
    return 0 if execution_pass else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
