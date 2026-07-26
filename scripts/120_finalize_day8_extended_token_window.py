#!/usr/bin/env python3
"""Finalize the locked Day 8 extended detailed-token diagnostic."""

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
from fastlio2_adapter.day8_extended_query_root_cause import (
    EXPLANATORY_CLASSIFICATIONS,
)
from fastlio2_adapter.day8_extended_token_window import (
    MAIN_RUN_ID,
    RUN_IDS,
    evaluate_extended_gate,
)
from fastlio2_adapter.day8_range_query import validate_run_query_trace


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


def _day9_scope(classifications: set[str]) -> str | None:
    if classifications & {
        "TREE_TRAVERSAL_PRUNING_DIVERGED",
        "FULL_COVER_SUBTREE_FLATTEN_RESULT_DIVERGED",
    }:
        return (
            "MINIMAL_IKDTREE_RANGE_QUERY_ISOLATION_"
            "AND_UNINSTRUMENTED_REPRODUCTION"
        )
    if "DELETION_FLAG_VISIBILITY_DIVERGED" in classifications:
        return "IKDTREE_DELETION_VISIBILITY_ISOLATION"
    if "REBUILD_SUBTREE_VISIBILITY_DIVERGED" in classifications:
        return "IKDTREE_REBUILD_READER_VISIBILITY_ISOLATION"
    return None


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
    synthetic = _read(
        args.comparison_dir / "day8_extended_synthetic_validation.json"
    )
    comparison = _read(
        args.comparison_dir / "day8_extended_comparison_summary.json"
    )
    pair_first = _read(
        args.comparison_dir
        / "pairwise_extended_first_query_divergence.json"
    )
    root = _read(
        args.root_cause_dir / "day8_extended_root_cause_summary.json"
    )
    pair_root = _read(
        args.root_cause_dir
        / "pairwise_extended_root_cause_classification.json"
    )
    previous = _read(
        args.root_cause_dir
        / "first_divergent_query_previous_identity.json"
    )
    witness = _read(
        args.root_cause_dir / "missing_expected_point_witness.json"
    )
    null_audit = _read(
        args.root_cause_dir / "null_token_semantics_audit.json"
    )
    range_query.SCAN_START = 155
    range_query.SCAN_END = 165
    range_query.DETAIL_START = 156
    range_query.DETAIL_END = 163
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
    run_complete = all(
        summary.get("complete") is True
        and summary.get("wrapper_exit_code") == 0
        and summary.get("wrapper_pipeline_clean_exit_pass") is True
        and summary.get("lidar_callback_count") == 491
        and summary.get("imu_callback_count") == 9953
        and summary.get("runtime_scan_count") == 490
        and summary.get("observation_record_count") == 487
        and summary.get("stage_hash_record_count") == 11
        and summary.get("stage_hash_first_scan") == 155
        and summary.get("stage_hash_last_scan") == 165
        and summary.get("coherent_snapshot_count") == 22
        and summary.get("incoherent_snapshot_count") == 0
        and summary.get("cross_scan_continuity_violation_count") == 0
        and summary.get("tap_drop_count") == 0
        and summary.get("writer_error_count") == 0
        and summary.get("in_call_mutation_count") == 0
        and summary.get("diagnostic_mutation_count") == 0
        and summary.get("schema_rejected_record_count") == 0
        and summary.get("ground_truth_topic_count", summary.get(
            "GT_TOPIC_CONSUMED_COUNT"
        )) == 0
        and summary.get("end_of_stream_drain_pass") is True
        and summary.get("normal_shutdown_pass") is True
        and summary.get("runtime_product_pass") is True
        for summary in summaries.values()
    )
    scan157_pass = all(
        value["scan157_token_coverage_pass"] is True
        and value["scan157_query_count"]
        == value["scan157_query_with_summary_count"]
        == value["scan157_query_with_detailed_token_count"]
        for value in coverages.values()
    )
    scan162_pass = all(
        value["scan162_token_coverage_pass"] is True
        and value["scan162_query_count"]
        == value["scan162_query_with_summary_count"]
        == value["scan162_query_with_detailed_token_count"]
        for value in coverages.values()
    )
    shadow_pass = all(
        value["shadow_state_accounting_pass"] is True
        and value["shadow_mutation_delta_failure_count"] == 0
        and value["shadow_state_closure_failure_count"] == 0
        for value in shadows.values()
    )
    overflow_pass = all(
        not any(validation["overflow"].values())
        and coverage["token_capture_failure_count"] == 0
        for validation, coverage in zip(
            validations.values(), coverages.values()
        )
    )
    schema_pass = all(
        validation["query_schema_error_count"] == 0
        and validation["unclassified_query_token_count"] == 0
        and coverage["unclassified_token_count"] == 0
        for validation, coverage in zip(
            validations.values(), coverages.values()
        )
    )
    immutable = all(
        _read(
            args.runtime_root / run_id
            / "day8_diagnostic_immutability_summary.json"
        ).get("diagnostic_readonly_scope_pass") is True
        for run_id in RUN_IDS
    )
    classifications = {
        item["classification"] for item in pair_root["pairs"]
    }
    divergent = [
        item for item in pair_first["pairs"]
        if item.get("aligned_query_index") is not None
    ]
    context_localized = bool(divergent) and all(
        item["classification"] in EXPLANATORY_CLASSIFICATIONS
        for item in pair_root["pairs"]
        if item.get("aligned_query_index") is not None
    )
    completeness = bool(divergent) and all((
        comparison["shadow_state_accounting_pass"] is True,
        comparison["formal_query_completeness_failure_count"] > 0,
        root["first_divergent_query_detailed_token_coverage_pass"] is True,
        root["missing_expected_point_witness_pass"] is True,
        not classifications & {
            "QUERY_INPUT_DIVERGED",
            "SHADOW_LOGICAL_VOXEL_MEMBERSHIP_DIVERGED",
            "EVIDENCE_GAP",
        },
    ))
    observation_pass = all(
        summary.get("binary_checksum_failure_count") == 0
        and summary.get("observation_record_count") == 487
        for summary in summaries.values()
    )
    snapshot_pass = all(
        summary.get("map_snapshot_coherence_pass") is True
        and summary.get("map_snapshot_cross_scan_coherence_pass") is True
        for summary in summaries.values()
    )
    day7_pass = all(
        summary.get("day7_event_overflow_count") == 0
        and summary.get("day7_unclassified_event_count") == 0
        and summary.get("day7_map_delta_accounting_failure_count") == 0
        for summary in summaries.values()
    )
    gates = evaluate_extended_gate(
        authorization_pass=authorization[
            "DAY8_EXTENDED_TOKEN_AUTHORIZATION_PASS"
        ],
        targeted_test_pass=execution["DEGEN_TARGETED_TEST_PASS"],
        full_test_pass=execution["DEGEN_FULL_TEST_PASS"],
        synthetic_pass=synthetic[
            "DAY8_EXTENDED_SYNTHETIC_VALIDATION_PASS"
        ],
        fast_source_lock_pass=execution["FAST_SOURCE_LOCK_PASS"],
        fast_binary_lock_pass=execution["FAST_BINARY_LOCK_PASS"],
        formal_logic_unchanged_pass=execution[
            "FORMAL_RANGE_SEARCH_LOGIC_UNCHANGED_PASS"
        ],
        four_replay_runs_complete_pass=run_complete,
        observation_binary_integrity_pass=observation_pass,
        map_snapshot_coherence_pass=snapshot_pass,
        day7_mutation_trace_reuse_pass=day7_pass,
        range_query_summary_capture_pass=all(
            value["query_summary_count"] > 0
            for value in validations.values()
        ),
        range_traversal_token_capture_pass=all(
            value["traversal_token_count"] > 0
            for value in validations.values()
        ),
        scan157_token_coverage_pass=scan157_pass,
        scan162_token_coverage_pass=scan162_pass,
        query_trace_overflow_pass=overflow_pass,
        query_trace_schema_pass=schema_pass,
        shadow_logical_voxel_replay_pass=shadow_pass,
        shadow_state_accounting_pass=shadow_pass,
        six_pair_range_query_comparison_pass=root[
            "six_pair_range_query_comparison_pass"
        ],
        previous_query_identity_check_complete=root[
            "previous_query_identity_check_complete"
        ],
        first_divergent_query_detailed_token_coverage_pass=root[
            "first_divergent_query_detailed_token_coverage_pass"
        ],
        missing_expected_point_witness_pass=root[
            "missing_expected_point_witness_pass"
        ],
        root_cause_classification_complete=root[
            "root_cause_classification_complete"
        ],
        null_token_semantics_fully_propagated_pass=null_audit[
            "NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS"
        ],
        offline_analysis_lock_pass=execution[
            "OFFLINE_ANALYSIS_LOCK_PASS"
        ],
        diagnostic_immutability_pass=immutable,
        no_tap_drop_pass=all(
            value.get("tap_drop_count") == 0
            for value in summaries.values()
        ),
        no_writer_error_pass=all(
            value.get("writer_error_count") == 0
            for value in summaries.values()
        ),
        no_gt_pass=all(
            value.get("ground_truth_topic_count", value.get(
                "GT_TOPIC_CONSUMED_COUNT"
            )) == 0 for value in summaries.values()
        ),
        diff_scope_pass=execution["DIFF_SCOPE_PASS"],
        audit_package_scope_pass=execution["AUDIT_PACKAGE_SCOPE_PASS"],
    )
    execution_pass = gates[
        "DAY8_EXTENDED_TOKEN_WINDOW_EXECUTION_PASS"
    ]
    recommended = execution_pass and completeness and context_localized
    scope = _day9_scope(classifications) if recommended else None
    final = {
        **gates,
        "main_run_id": MAIN_RUN_ID,
        "source_audit_sha256": lock["source_audit_sha256"],
        "authorization_sha256": lock["authorization_sha256"],
        "query_summary_window": [155, 165],
        "detailed_token_window": [156, 163],
        "token_semantics_version": "TOKEN_CAPTURE_SEMANTICS_V2",
        "DAY8_EXTENDED_TOKEN_AUTHORIZATION_PASS":
            authorization["DAY8_EXTENDED_TOKEN_AUTHORIZATION_PASS"],
        "NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS":
            null_audit["NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS"],
        "FOUR_REPLAY_RUNS_COMPLETE_PASS": run_complete,
        "SCAN157_TOKEN_COVERAGE_PASS": scan157_pass,
        "SCAN162_TOKEN_COVERAGE_PASS": scan162_pass,
        "SHADOW_STATE_ACCOUNTING_PASS": shadow_pass,
        "SIX_PAIR_RANGE_QUERY_COMPARISON_PASS":
            root["six_pair_range_query_comparison_pass"],
        "PREVIOUS_QUERY_IDENTITY_CHECK_COMPLETE":
            root["previous_query_identity_check_complete"],
        "FIRST_DIVERGENT_QUERY_DETAILED_TOKEN_COVERAGE_PASS":
            root["first_divergent_query_detailed_token_coverage_pass"],
        "FORMAL_RANGE_QUERY_COMPLETENESS_VIOLATION_OBSERVED":
            completeness,
        "IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED":
            context_localized,
        "DAY8_IKDTREE_RANGE_SEARCH_CONTEXT_PASS":
            execution_pass and context_localized,
        "FORMAL_IKDTREE_BUG_PROVEN": False,
        "DATA_RACE_PROVEN": False,
        "DAY9_RECOMMENDED": recommended,
        "DAY9_RECOMMENDED_SCOPE": scope,
        "DAY9_AUTHORIZED": False,
        "STAGE2_GATE": "FAIL",
        "TRANSITION": "PIVOT",
        "STAGE3_START_AUTHORIZED": False,
        "STAGE4_START_AUTHORIZED": False,
        "PATENT2_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "RISK_WARNING_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
        "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE": "NOT_PROVEN",
        "HARMFUL_BIAS_DETECTABILITY_STATUS":
            "NOT_EVALUATED_DAY8_EXTENDED_DETAILED_TOKEN_WINDOW",
        "result_identity":
            "INTERNAL_ENGINEERING_RANGE_QUERY_PATH_DIAGNOSTICS_ONLY",
        "DETECTOR_CALLED": False,
        "GT_USED": False,
        "FORMAL_SEARCH_LOGIC_MODIFIED": False,
        "FAST_SOURCE_MODIFIED": False,
        "FAST_BUILD_RUN": False,
        "FAST_TEST_RUN": False,
        "FAST_BINARY_CHANGED": False,
        "THREAD_CONFIGURATION_MODIFIED": False,
        "COMMIT_PERFORMED": False,
        "PUSH_PERFORMED": False,
        "OFFLINE_ANALYSIS_CODE_CHANGED_AFTER_RUNTIME_LOCK": False,
        "instrumentation_timing_perturbation_present": True,
        "shadow_replay_participates_in_fast_decisions": False,
        "query_completeness_violation_is_diagnostic_not_bug_proof": True,
        "multiple_root_cause_modes": len(
            classifications & EXPLANATORY_CLASSIFICATIONS
        ) > 1,
        "per_run_summary": summaries,
        "per_run_validation": validations,
        "per_run_token_coverage": coverages,
        "per_run_shadow_accounting": shadows,
        "pairwise_first_divergence": pair_first["pairs"],
        "pairwise_root_cause": pair_root["pairs"],
        "first_divergent_query": root["first_divergent_query"],
        "previous_query_identity": previous,
        "missing_expected_point_witness": witness,
        "null_token_semantics_audit": null_audit,
    }
    final_path = args.output_dir / "day8_extended_final_gate.json"
    _write(final_path, final)

    first = root.get("first_divergent_query")
    report = f"""# Day 8 Extended Detailed Token Window Report

## Outcome

`DAY8_EXTENDED_TOKEN_WINDOW_EXECUTION_PASS={str(execution_pass).lower()}`.
`IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED={str(context_localized).lower()}`.

## Required answers

1. The prior scan 162 query had no tokens because its frozen detailed window
   was 156--158.
2. The authorized detailed window is 156--163, covering scans 157 and 162
   while remaining inside the unchanged 155--165 summary window.
3. FAST was not changed because the existing binary reads all four window
   bounds from ROS parameters and validates the detailed window is nested.
4. Historical empty-list inference was replaced by
   `TOKEN_CAPTURE_SEMANTICS_V2`.
5. Null-token propagation audit passed:
   `{str(null_audit["NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS"]).lower()}`.
6. Four fixed replays complete: `{str(run_complete).lower()}`.
7. Scan 157 full coverage: `{str(scan157_pass).lower()}`.
8. Scan 162 full coverage: `{str(scan162_pass).lower()}`.
9. First formal query difference: `{json.dumps(first, sort_keys=True)}`.
10. Previous-query identity complete:
    `{str(root["previous_query_identity_check_complete"]).lower()}`.
11. Query input and 12. shadow membership are recorded in six-pair evidence.
13. Per-side formal result sets are recorded in the first-query evidence.
14--16. Expected-member visit/deleted/path evidence is in
    `missing_expected_point_witness.json` and the traversal-diff CSV.
17. Rebuild active/generation is preserved per query and token.
18. Formal completeness violation observed: `{str(completeness).lower()}`.
19. Range-search context localized: `{str(context_localized).lower()}`.
20. `FORMAL_IKDTREE_BUG_PROVEN=false`.
21. `DATA_RACE_PROVEN=false`.
22. Read-only instrumentation may perturb timing and scheduling.
23. Day 9 recommended: `{str(recommended).lower()}`; scope:
    `{scope}`.
24. `DAY9_AUTHORIZED=false`; a separate GPT audit is required.

Shadow replay is offline-only and never participates in FAST decisions.
Detector, ODI/AIS, weak direction, feedback, GT, commit, push, FAST build, and
FAST tests were not used. Empty or absent token evidence never means equal
traversal under V2.
"""
    report_path = (
        ROOT / "docs/harmful_bias/day8_extended_token_window_report.md"
    )
    report_path.write_text(report, encoding="utf-8")
    manifest = {
        "schema_version": "day8_extended_token_window_manifest_v1",
        "source_audit_sha256": lock["source_audit_sha256"],
        "authorization_sha256": lock["authorization_sha256"],
        "query_summary_window": [155, 165],
        "detailed_token_window": [156, 163],
        "token_semantics_version": "TOKEN_CAPTURE_SEMANTICS_V2",
        "degen_identity": lock["degen_identity"],
        "fast_identity": lock["fast_identity"],
        "run_ids": list(RUN_IDS),
        "ros_master_ports": lock["ros_master_ports"],
        "per_run_summary": summaries,
        "per_run_validation": validations,
        "per_run_token_coverage": coverages,
        "per_run_shadow_accounting": shadows,
        "pairwise_first_divergence": pair_first["pairs"],
        "pairwise_root_cause": pair_root["pairs"],
        "first_divergent_query": first,
        "previous_query_identity": previous,
        "missing_expected_point_witness": witness,
        "formal_query_completeness_violation_observed": completeness,
        "range_search_context_root_cause_localized": context_localized,
        "offline_analysis_lock_sha256":
            lock["offline_analysis_lock_sha256"],
        "detector_called": False,
        "GT": False,
        "commit": False,
        "push": False,
        "day8_pass": execution_pass,
        "day9_recommended": recommended,
        "day9_scope": scope,
        "day9_authorized": False,
        "gates": final,
        "plot_count": len(list(args.plots_dir.glob("*.png"))),
        "final_gate_sha256": _sha256(final_path),
        "report_sha256": _sha256(report_path),
    }
    _write(
        ROOT
        / "manifests/harmful_bias/day8_extended_token_window_manifest.json",
        manifest,
    )
    return 0 if execution_pass else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        raise SystemExit(1)
