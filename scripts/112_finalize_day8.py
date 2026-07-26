#!/usr/bin/env python3
"""Evaluate Day 8 gates and materialize the bounded report and manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day8_query_root_cause import evaluate_day8_gate
from fastlio2_adapter.day8_range_query import validate_run_query_trace


RUN_IDS = tuple(
    f"multihyp_day8_range_query_r{index}" for index in range(1, 5)
)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
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


def _all_true(value: Mapping[str, Any], names: tuple[str, ...]) -> bool:
    return all(value.get(name) is True for name in names)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--root-cause-dir", required=True, type=Path)
    parser.add_argument("--plots-dir", required=True, type=Path)
    parser.add_argument("--execution-evidence", required=True, type=Path)
    parser.add_argument("--authorization-amendment", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    execution = _json(args.execution_evidence)
    amendment = _json(args.authorization_amendment)
    comparison = _json(
        args.comparison_dir / "day8_comparison_summary.json"
    )
    root = _json(args.root_cause_dir / "day8_root_cause_summary.json")
    synthetic = _json(
        args.comparison_dir / "day8_synthetic_query_trace_validation.json"
    )
    previous = _json(
        args.root_cause_dir / "first_divergent_query_previous_identity.json"
    )
    missing = _json(
        args.root_cause_dir / "missing_expected_point_witness.json"
    )
    pairwise_root = _json(
        args.root_cause_dir
        / "pairwise_day8_root_cause_classification.json"
    )
    run_summaries = {
        run_id: _json(args.runtime_root / run_id / "run_summary.json")
        for run_id in RUN_IDS
    }
    validations = [
        validate_run_query_trace(args.runtime_root / run_id)
        for run_id in RUN_IDS
    ]
    immutability = [
        _json(
            args.runtime_root / run_id
            / "day8_diagnostic_immutability_summary.json"
        )
        for run_id in RUN_IDS
    ]
    runtime_complete = all(
        value.get("complete") is True for value in run_summaries.values()
    )
    query_capture = all(
        item["query_summary_count"] > 0 for item in validations
    )
    token_capture = all(
        item["traversal_token_count"] > 0 for item in validations
    )
    voxel_capture = all(
        item["point_voxel_snapshot_count"] == 22 for item in validations
    )
    overflow_pass = all(
        not any(int(value) for value in item["overflow"].values())
        for item in validations
    )
    run_product_pass = all(
        _all_true(
            summary,
            (
                "wrapper_pipeline_clean_exit_pass",
                "map_snapshot_coherence_pass",
                "map_snapshot_cross_scan_coherence_pass",
            ),
        )
        and summary.get("coherent_snapshot_count") == 22
        and summary.get("incoherent_snapshot_count") == 0
        and summary.get("cross_scan_continuity_violation_count") == 0
        and summary.get("tap_drop_count", 0) == 0
        and summary.get("writer_error_count", 0) == 0
        and summary.get("ground_truth_topic_count", 0) == 0
        for summary in run_summaries.values()
    )
    diagnostic_immutability_pass = all(
        item.get("diagnostic_mutation_count") == 0
        and item.get("diagnostic_readonly_scope_pass") is True
        for item in immutability
    )
    pair_count = pairwise_root.get("pair_count") == 6
    first_localized = root["first_divergent_query_localized"] is True
    completeness_violation = (
        root["query_completeness_violation_observed"] is True
    )
    classifications = [
        item["classification"] for item in pairwise_root["pairs"]
    ]
    context_localized = first_localized and all(
        value not in {"EVIDENCE_GAP", "SAME_QUERY_TRACE_DIFFERENT_RESULT"}
        for value in classifications
    )
    missing_witness_pass = (
        missing["witness_count"] > 0 if first_localized else True
    )
    previous_pass = (
        all((
            previous["previous_query_equal"],
            previous["previous_shadow_state_equal"],
            previous["previous_formal_result_equal"],
            previous["previous_traversal_summary_equal"],
        )) if first_localized else True
    )
    gates = {
        "DAY8_AUTHORIZATION_AMENDMENT_PASS":
            amendment.get("day8_authorization_amendment_pass") is True,
        "DAY8_SOURCE_PATH_RESOLUTION_PASS":
            execution.get("DAY8_SOURCE_PATH_RESOLUTION_PASS") is True,
        "FAST_BUILD_PASS": execution.get("FAST_BUILD_PASS") is True,
        "FAST_TEST_PASS": execution.get("FAST_TEST_PASS") is True,
        "DEGEN_TARGETED_TEST_PASS":
            execution.get("DEGEN_TARGETED_TEST_PASS") is True,
        "DEGEN_FULL_TEST_PASS":
            execution.get("DEGEN_FULL_TEST_PASS") is True,
        "FORMAL_RANGE_SEARCH_LOGIC_UNCHANGED_PASS":
            execution.get("FORMAL_RANGE_SEARCH_LOGIC_UNCHANGED_PASS") is True,
        "DIAGNOSTIC_READONLY_SCOPE_PASS": diagnostic_immutability_pass,
        "DAY8_SYNTHETIC_QUERY_TRACE_VALIDATION_PASS":
            synthetic.get("DAY8_SYNTHETIC_QUERY_TRACE_VALIDATION_PASS") is True,
        "FOUR_REPLAY_RUNS_COMPLETE_PASS": runtime_complete,
        "OBSERVATION_BINARY_INTEGRITY_PASS": run_product_pass,
        "MAP_SNAPSHOT_COHERENCE_PASS": all(
            summary["coherent_snapshot_count"] == 22
            for summary in run_summaries.values()
        ),
        "DAY7_MUTATION_TRACE_REUSE_PASS": all(
            summary["day7_event_overflow_count"] == 0
            and summary["day7_unclassified_event_count"] == 0
            for summary in run_summaries.values()
        ),
        "RANGE_QUERY_SUMMARY_CAPTURE_PASS": query_capture,
        "RANGE_TRAVERSAL_TOKEN_CAPTURE_PASS": token_capture,
        "MAP_POINT_VOXEL_IDENTITY_SNAPSHOT_PASS": voxel_capture,
        "QUERY_TRACE_OVERFLOW_PASS": overflow_pass,
        "QUERY_TRACE_SCHEMA_PASS": all(
            item["query_schema_error_count"] == 0 for item in validations
        ),
        "SHADOW_LOGICAL_VOXEL_REPLAY_PASS":
            comparison["shadow_state_accounting_pass"] is True,
        "SHADOW_STATE_ACCOUNTING_PASS":
            comparison["shadow_state_accounting_pass"] is True,
        "SIX_PAIR_RANGE_QUERY_COMPARISON_PASS": pair_count,
        "PREVIOUS_QUERY_IDENTITY_CHECK_COMPLETE": previous_pass,
        "MISSING_EXPECTED_POINT_WITNESS_PASS": missing_witness_pass,
        "ROOT_CAUSE_CLASSIFICATION_COMPLETE": pair_count and all(
            value not in {
                "EVIDENCE_GAP", "SAME_QUERY_TRACE_DIFFERENT_RESULT",
            }
            for value in classifications
        ),
        "DIAGNOSTIC_IMMUTABILITY_PASS": diagnostic_immutability_pass,
        "NO_TAP_DROP_PASS": all(
            summary.get("tap_drop_count", 0) == 0
            for summary in run_summaries.values()
        ),
        "NO_WRITER_ERROR_PASS": all(
            summary.get("writer_error_count", 0) == 0
            for summary in run_summaries.values()
        ),
        "NO_GT_PASS": all(
            summary.get("ground_truth_topic_count", 0) == 0
            for summary in run_summaries.values()
        ),
        "OFFLINE_ANALYSIS_LOCK_PASS":
            execution.get("OFFLINE_ANALYSIS_LOCK_PASS") is True,
        "DIFF_SCOPE_PASS": execution.get("DIFF_SCOPE_PASS") is True,
        "AUDIT_PACKAGE_SCOPE_PASS":
            execution.get("AUDIT_PACKAGE_SCOPE_PASS") is True,
    }
    coarse = evaluate_day8_gate(
        validations, pairwise_root["pairs"],
        synthetic_pass=gates["DAY8_SYNTHETIC_QUERY_TRACE_VALIDATION_PASS"],
        static_logic_unchanged=
            gates["FORMAL_RANGE_SEARCH_LOGIC_UNCHANGED_PASS"],
    )
    execution_pass = all(gates.values()) and coarse["day8_execution_pass"]
    final = {
        "schema_version": "day8_final_gate_v1",
        "main_run_id":
            "multihyp_day8_ikdtree_range_search_context_v1",
        "gates": gates,
        "DAY8_EXECUTION_PASS": execution_pass,
        "FIRST_DIVERGENT_RANGE_QUERY_LOCALIZED": first_localized,
        "FORMAL_RANGE_QUERY_COMPLETENESS_VIOLATION_OBSERVED":
            completeness_violation,
        "IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED":
            context_localized,
        "DAY8_IKDTREE_RANGE_SEARCH_CONTEXT_PASS":
            execution_pass and context_localized,
        "DAY9_RECOMMENDED": execution_pass and context_localized,
        "FORMAL_IKDTREE_BUG_PROVEN": False,
        "DATA_RACE_PROVEN": False,
        "DAY9_AUTHORIZED": False,
        "STAGE3_START_AUTHORIZED": False,
        "STAGE4_START_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PATENT2_AUTHORIZED": False,
        "DETECTOR_ENABLED": False,
        "ODI_AIS_ENABLED": False,
        "WEAK_DIRECTION_ENABLED": False,
        "FEEDBACK_UPDATE_ENABLED": False,
        "GT_ENABLED": False,
        "COMMIT_PERFORMED": False,
        "PUSH_PERFORMED": False,
        "instrumentation_timing_perturbation_present": True,
        "shadow_replay_participates_in_fast_decisions": False,
        "query_completeness_violation_is_diagnostic_not_bug_proof": True,
        "per_run_validation": validations,
        "per_run_summary": run_summaries,
        "root_cause_summary": root,
    }
    final_path = args.output_dir / "day8_final_gate.json"
    _write_json(final_path, final)
    report = f"""# Day 8 ikd-tree Range-Search Context Root-Cause Report

## Outcome

`DAY8_EXECUTION_PASS={str(execution_pass).lower()}`.
The fixed four-run diagnostic localized a first divergent formal range query:
`{str(first_localized).lower()}`.  The bounded classification set is
`{", ".join(sorted(set(classifications)))}`.

## Evidence boundary

The query box comes directly from the existing `Add_Points` downsampling box.
The C++ audit observes the existing `Search_by_range` invocation and result; it
does not add a search or mutate its result.  Detailed traversal tokens cover only
scans 160--163 and contain no node addresses, thread identifiers, coordinates,
or full tree structure.  Offline shadow replay uses only coherent canonical
point identities plus the formal C++ voxel identity.  It never participates in
FAST-LIO2 decisions.

## Required answers

- Four replay runs complete: `{str(runtime_complete).lower()}`.
- Query summary counts: `{json.dumps({k: v["range_query_summary_count"] for k, v in run_summaries.items()}, sort_keys=True)}`.
- Traversal token counts: `{json.dumps({k: v["detailed_traversal_token_count"] for k, v in run_summaries.items()}, sort_keys=True)}`.
- Point+voxel snapshots: 22 per run; coherent snapshot Gate:
  `{str(gates["MAP_SNAPSHOT_COHERENCE_PASS"]).lower()}`.
- First divergent query: `{json.dumps(root["first_divergent_query"], sort_keys=True)}`.
- Query boxes, shadow members, formal results, traversal/pruning and deletion/
  rebuild visibility are preserved in the pairwise and first-divergence files.
- Previous query identity complete:
  `{str(gates["PREVIOUS_QUERY_IDENTITY_CHECK_COMPLETE"]).lower()}`.
- Formal query completeness violation observed:
  `{str(completeness_violation).lower()}`.
- ikd-tree range-search context root cause localized:
  `{str(context_localized).lower()}`.
- Instrumentation timing perturbation is present and disclosed.
- `FORMAL_IKDTREE_BUG_PROVEN=false`; a diagnostic completeness violation does
  not automatically prove a formal implementation bug.
- `DATA_RACE_PROVEN=false`.
- Stage 3, Stage 4, FAST integration, Patent 2 and Day 9 remain unauthorized.

## Scope

Day 8 diagnoses only range-query and voxel-representative context.  Detector,
ODI/AIS, weak-direction, feedback update, GT, commit and push are all disabled.
"""
    report_path = (
        ROOT / "docs/harmful_bias/day8_range_query_root_cause_report.md"
    )
    report_path.write_text(report, encoding="utf-8")
    _write_json(
        ROOT
        / "manifests/harmful_bias/day8_range_query_root_cause_manifest.json",
        {
            "schema_version": "day8_range_query_root_cause_manifest_v1",
            "main_run_id": final["main_run_id"],
            "final_gate_path": str(final_path),
            "final_gate_sha256": _sha256(final_path),
            "report_path": str(report_path.relative_to(ROOT)),
            "report_sha256": _sha256(report_path),
            "run_ids": list(RUN_IDS),
            "query_summary_counts": {
                key: value["range_query_summary_count"]
                for key, value in run_summaries.items()
            },
            "traversal_token_counts": {
                key: value["detailed_traversal_token_count"]
                for key, value in run_summaries.items()
            },
            "plot_count": len(list(args.plots_dir.glob("*.png"))),
            "root_cause_classifications": classifications,
            "DAY8_EXECUTION_PASS": execution_pass,
            "FORMAL_IKDTREE_BUG_PROVEN": False,
            "DATA_RACE_PROVEN": False,
            "DAY9_AUTHORIZED": False,
            "commit_performed": False,
            "push_performed": False,
        },
    )
    return 0 if execution_pass else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
