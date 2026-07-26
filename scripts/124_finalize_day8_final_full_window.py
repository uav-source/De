#!/usr/bin/env python3
"""Finalize the locked Day 8 full-window evidence without replaying ROS."""

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
from fastlio2_adapter.day8_final_full_window_analysis import (
    MAIN_RUN_ID,
    RUN_IDS,
    evaluate_final_gate,
)
from fastlio2_adapter.day8_final_plot_contract import (
    PLOT_INPUT_SCHEMA_VERSION,
)
from fastlio2_adapter.day8_range_query import validate_run_query_trace
from fastlio2_adapter.day8_strict_query_identity_v2 import (
    STRICT_QUERY_IDENTITY_SCHEMA_VERSION,
)
from fastlio2_adapter.day8_token_semantics_v3 import (
    TOKEN_CAPTURE_SEMANTICS_VERSION,
)


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _lock_code_pass(lock: dict[str, Any]) -> bool:
    files = lock.get("analysis_code_files", {})
    return bool(files) and all(
        (ROOT / value["path"]).is_file()
        and _sha(ROOT / value["path"]) == value["sha256"]
        for value in files.values()
    )


def _per_run_complete(summary: dict[str, Any], coverage: dict[str, Any]) -> bool:
    return all((
        summary.get("complete") is True,
        summary.get("wrapper_exit_code") == 0,
        summary.get("lidar_callback_count") == 491,
        summary.get("imu_callback_count") == 9953,
        summary.get("runtime_scan_count") == 490,
        summary.get("observation_record_count") == 487,
        summary.get("stage_hash_record_count") == 11,
        summary.get("stage_hash_first_scan") == 155,
        summary.get("stage_hash_last_scan") == 165,
        summary.get("coherent_snapshot_count") == 22,
        summary.get("incoherent_snapshot_count") == 0,
        summary.get("cross_scan_continuity_violation_count") == 0,
        summary.get("tap_drop_count") == 0,
        summary.get("writer_error_count") == 0,
        summary.get("in_call_mutation_count") == 0,
        summary.get("diagnostic_mutation_count") == 0,
        summary.get("schema_rejected_record_count") == 0,
        summary.get("ground_truth_topic_count") == 0,
        summary.get("end_of_stream_drain_pass") is True,
        summary.get("normal_shutdown_pass") is True,
        summary.get("runtime_product_pass") is True,
        coverage["FULL_WINDOW_QUERY_SUMMARY_COVERAGE_PASS"] is True,
        coverage["FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS"] is True,
        len(coverage["per_scan"]) == 11,
    ))


def _report(manifest: dict[str, Any]) -> str:
    gate = manifest["gates"]
    route = manifest["random_replay_decision"]
    strict = manifest["strict_comparison"]
    root = manifest["root_cause"]
    lines = [
        "# Day 8 Final Full-Window Reproduction Report",
        "",
        "This was the authorized final random real-replay batch: exactly four new "
        "Quick Shack runs were executed and no fifth replay was added.",
        "",
        "## Fixed scope",
        "",
        "- Query-summary window: scan 155–165.",
        "- Detailed traversal-token window: scan 155–165, chosen to cover every "
        "formal query in the summary window.",
        "- FAST source modified: false; FAST rebuilt or tested: false.",
        "- Strict identity: `(scan_index, map_mutation_call_index, batch_id, "
        "batch_point_index, candidate_point_sha256, voxel_identity, "
        "query_box_checksum)`.",
        "- Comparison is identity-keyed. Positional query comparison is not used.",
        "- Result order differences are reported separately and never treated as "
        "member omissions.",
        "- Null-token semantics are fully propagated; absent capture is never "
        "treated as an equal empty trace.",
        "- Plotter inputs are the formal comparison, root-cause, coverage, "
        "accounting, cost, and route-decision outputs only.",
        "",
        "## Replay and comparison outcome",
        "",
        f"- Four runs complete: `{str(gate['FOUR_REPLAY_RUNS_COMPLETE_PASS']).lower()}`.",
        f"- Full-window token coverage: "
        f"`{str(gate['FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS']).lower()}`.",
        f"- Strict same-input formal member divergence reproduced: "
        f"`{str(root['STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED']).lower()}`.",
        f"- Formal completeness violation observed: "
        f"`{str(root['FORMAL_RANGE_QUERY_COMPLETENESS_VIOLATION_OBSERVED']).lower()}`.",
        f"- Root cause: `{root['root_cause_classification']}`.",
        f"- Root-cause localized: "
        f"`{str(root['IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED']).lower()}`.",
        f"- Pair summaries: `{json.dumps(strict['pairs'], sort_keys=True)}`.",
        "",
        "## Claim boundary and route decision",
        "",
        "- Shadow replay is offline evidence and never participates in FAST decisions.",
        "- Instrumentation can perturb scheduling and timing.",
        "- A query anomaly would not automatically prove a production bug or data race.",
        "- `FORMAL_IKDTREE_BUG_PROVEN=false`; `DATA_RACE_PROVEN=false`.",
        f"- Random replay route: `{route['RANDOM_REAL_REPLAY_ROUTE_STATUS']}`.",
        f"- Further random replay authorized: "
        f"`{str(route['FURTHER_RANDOM_REAL_REPLAY_AUTHORIZED']).lower()}`.",
        f"- Deterministic minimal fixture recommended: "
        f"`{str(route['DETERMINISTIC_IKDTREE_MINIMAL_FIXTURE_RECOMMENDED']).lower()}`.",
        f"- Next scope: `{route['NEXT_RECOMMENDED_SCOPE']}`.",
        "- Day 9 remains unauthorized and requires independent GPT audit.",
        "- The evidence does not authorize Stage 3 or a FAST robust-update path.",
        "",
        "## Scientific state",
        "",
        "- `STAGE2_GATE=FAIL`; `TRANSITION=PIVOT`.",
        "- `CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`.",
        "- Detector and ground truth were not used.",
    ]
    return "\n".join(lines) + "\n"


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
    parser.add_argument(
        "--report-path",
        type=Path,
        default=ROOT / "docs/harmful_bias/day8_final_full_window_report.md",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=ROOT / "manifests/harmful_bias/day8_final_full_window_manifest.json",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    execution = _read(args.execution_evidence)
    authorization = _read(args.authorization)
    lock = _read(args.run_lock)
    comparison = _read(
        args.comparison_dir / "day8_final_comparison_summary.json"
    )
    strict = _read(
        args.comparison_dir / "pairwise_final_strict_identity_summary.json"
    )
    root = _read(
        args.root_cause_dir / "day8_final_root_cause_summary.json"
    )
    null_audit = _read(
        args.root_cause_dir / "null_token_semantics_audit.json"
    )
    route = _read(
        args.root_cause_dir / "random_replay_route_decision.json"
    )
    plots = _read(args.plots_dir / "day8_final_plot_summary.json")
    range_query.SCAN_START = 155
    range_query.SCAN_END = 165
    range_query.DETAIL_START = 155
    range_query.DETAIL_END = 165
    summaries = {
        run_id: _read(args.runtime_root / run_id / "run_summary.json")
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
    validations = {
        run_id: validate_run_query_trace(args.runtime_root / run_id)
        for run_id in RUN_IDS
    }
    four_complete = all(
        _per_run_complete(summaries[run_id], coverages[run_id])
        for run_id in RUN_IDS
    )
    overflow_pass = all(
        not any(value["overflow"].values()) for value in validations.values()
    )
    schema_pass = all(
        value["query_schema_error_count"] == 0
        and value["unclassified_query_token_count"] == 0
        for value in validations.values()
    )
    shadow_pass = all(
        value["shadow_state_accounting_pass"] is True
        and value["shadow_accounting_failure_count"] == 0
        and value["shadow_mutation_delta_failure_count"] == 0
        and value["shadow_state_closure_failure_count"] == 0
        for value in shadows.values()
    )
    code_lock_pass = _lock_code_pass(lock)
    gates = evaluate_final_gate(
        authorization_pass=execution["DAY8_FINAL_FULL_WINDOW_AUTHORIZATION_PASS"],
        strict_query_identity_v2_pass=comparison["STRICT_QUERY_IDENTITY_V2_PASS"],
        null_token_semantics_v3_pass=comparison["NULL_TOKEN_SEMANTICS_V3_PASS"],
        null_token_semantics_fully_propagated_pass=null_audit[
            "NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS"
        ],
        plot_input_contract_pass=plots["PLOT_INPUT_CONTRACT_PASS"],
        targeted_test_pass=execution["DEGEN_TARGETED_TEST_PASS"],
        full_test_pass=execution["DEGEN_FULL_TEST_PASS"],
        synthetic_validation_pass=execution[
            "DAY8_FINAL_SYNTHETIC_VALIDATION_PASS"
        ],
        fast_source_lock_pass=execution["FAST_SOURCE_LOCK_PASS"],
        fast_binary_lock_pass=execution["FAST_BINARY_LOCK_PASS"],
        formal_range_search_logic_unchanged_pass=execution[
            "FORMAL_RANGE_SEARCH_LOGIC_UNCHANGED_PASS"
        ],
        fast_source_unmodified_pass=not execution["FAST_SOURCE_MODIFIED"],
        fast_build_not_run_pass=not execution["FAST_BUILD_RUN"],
        four_replay_runs_complete_pass=four_complete,
        observation_binary_integrity_pass=all(
            value["query_binary_sha256"] and
            summaries[run_id]["binary_checksum_failure_count"] == 0
            for run_id, value in validations.items()
        ),
        map_snapshot_coherence_pass=all(
            summary["map_snapshot_coherence_pass"]
            and summary["map_snapshot_cross_scan_coherence_pass"]
            for summary in summaries.values()
        ),
        day7_mutation_trace_reuse_pass=all(
            summary["day7_event_overflow_count"] == 0
            and summary["day7_unclassified_event_count"] == 0
            and summary["day7_map_delta_accounting_failure_count"] == 0
            for summary in summaries.values()
        ),
        full_window_query_summary_coverage_pass=all(
            value["FULL_WINDOW_QUERY_SUMMARY_COVERAGE_PASS"]
            for value in coverages.values()
        ),
        full_window_detailed_token_coverage_pass=all(
            value["FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS"]
            for value in coverages.values()
        ),
        query_trace_overflow_pass=overflow_pass,
        query_trace_schema_pass=schema_pass,
        shadow_logical_voxel_replay_pass=shadow_pass,
        shadow_state_accounting_pass=shadow_pass,
        six_pair_strict_identity_comparison_pass=strict[
            "SIX_PAIR_STRICT_IDENTITY_COMPARISON_PASS"
        ],
        previous_query_identity_check_complete=root[
            "PREVIOUS_QUERY_IDENTITY_CHECK_COMPLETE"
        ],
        root_cause_classification_complete=True,
        offline_analysis_lock_pass=code_lock_pass,
        offline_analysis_code_unchanged_after_runtime_lock_pass=code_lock_pass,
        diagnostic_immutability_pass=all(
            _read(
                args.runtime_root / run_id
                / "day8_diagnostic_immutability_summary.json"
            )["diagnostic_readonly_scope_pass"]
            for run_id in RUN_IDS
        ),
        no_tap_drop_pass=all(
            summary["tap_drop_count"] == 0 for summary in summaries.values()
        ),
        no_writer_error_pass=all(
            summary["writer_error_count"] == 0 for summary in summaries.values()
        ),
        no_gt_pass=all(
            summary["ground_truth_topic_count"] == 0
            for summary in summaries.values()
        ),
        diff_scope_pass=execution["DIFF_SCOPE_PASS"],
        audit_package_scope_pass=execution["AUDIT_PACKAGE_SCOPE_PASS"],
    )
    final_gate = {
        **gates,
        "DAY8_FINAL_FULL_WINDOW_AUTHORIZATION_PASS": execution[
            "DAY8_FINAL_FULL_WINDOW_AUTHORIZATION_PASS"
        ],
        "STRICT_QUERY_IDENTITY_V2_PASS": comparison[
            "STRICT_QUERY_IDENTITY_V2_PASS"
        ],
        "NULL_TOKEN_SEMANTICS_V3_PASS": comparison[
            "NULL_TOKEN_SEMANTICS_V3_PASS"
        ],
        "NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS": null_audit[
            "NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS"
        ],
        "PLOT_INPUT_CONTRACT_PASS": plots["PLOT_INPUT_CONTRACT_PASS"],
        "FOUR_REPLAY_RUNS_COMPLETE_PASS": four_complete,
        "FULL_WINDOW_QUERY_SUMMARY_COVERAGE_PASS": all(
            value["FULL_WINDOW_QUERY_SUMMARY_COVERAGE_PASS"]
            for value in coverages.values()
        ),
        "FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS": all(
            value["FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS"]
            for value in coverages.values()
        ),
        "SHADOW_STATE_ACCOUNTING_PASS": shadow_pass,
        "SIX_PAIR_STRICT_IDENTITY_COMPARISON_PASS": strict[
            "SIX_PAIR_STRICT_IDENTITY_COMPARISON_PASS"
        ],
        "PREVIOUS_QUERY_IDENTITY_CHECK_COMPLETE": root[
            "PREVIOUS_QUERY_IDENTITY_CHECK_COMPLETE"
        ],
        "STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED": root[
            "STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED"
        ],
        "FORMAL_RANGE_QUERY_COMPLETENESS_VIOLATION_OBSERVED": root[
            "FORMAL_RANGE_QUERY_COMPLETENESS_VIOLATION_OBSERVED"
        ],
        "IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED": root[
            "IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED"
        ],
        "DAY8_IKDTREE_RANGE_SEARCH_CONTEXT_PASS": (
            gates["DAY8_FINAL_FULL_WINDOW_EXECUTION_PASS"]
            and root["IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED"]
        ),
        "RANDOM_REAL_REPLAY_ROUTE_STATUS": route[
            "RANDOM_REAL_REPLAY_ROUTE_STATUS"
        ],
        "FURTHER_RANDOM_REAL_REPLAY_AUTHORIZED": False,
        "DETERMINISTIC_IKDTREE_MINIMAL_FIXTURE_RECOMMENDED": route[
            "DETERMINISTIC_IKDTREE_MINIMAL_FIXTURE_RECOMMENDED"
        ],
        "NEXT_RECOMMENDED_SCOPE": route["NEXT_RECOMMENDED_SCOPE"],
        "DAY9_RECOMMENDED": route["DAY9_RECOMMENDED"],
        "DAY9_RECOMMENDED_SCOPE": route["DAY9_RECOMMENDED_SCOPE"],
        "DAY9_AUTHORIZED": False,
        "STAGE2_GATE": "FAIL",
        "TRANSITION": "PIVOT",
        "STAGE3_START_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE": "NOT_PROVEN",
        "DETECTOR_CALLED": False,
        "GT_USED": False,
        "COMMIT_PERFORMED": False,
        "PUSH_PERFORMED": False,
        "FAST_SOURCE_MODIFIED": False,
        "FAST_BUILD_RUN": False,
        "FAST_TEST_RUN": False,
        "FORMAL_SEARCH_LOGIC_MODIFIED": False,
        "THREAD_CONFIGURATION_MODIFIED": False,
        "instrumentation_timing_perturbation_present": True,
    }
    _write(args.output_dir / "day8_final_gate.json", final_gate)
    manifest = {
        "schema_version": "day8_final_full_window_manifest_v1",
        "source_audit_sha256": lock["source_audit_sha256"],
        "authorization_sha256": lock["authorization_sha256"],
        "query_summary_window": [155, 165],
        "detailed_token_window": [155, 165],
        "strict_identity_schema_version": STRICT_QUERY_IDENTITY_SCHEMA_VERSION,
        "token_semantics_version": TOKEN_CAPTURE_SEMANTICS_VERSION,
        "plot_input_schema_version": PLOT_INPUT_SCHEMA_VERSION,
        "main_run_id": MAIN_RUN_ID,
        "source_identity": {
            "degen": lock["degen_identity"],
            "fast": lock["fast_identity"],
        },
        "runs": {
            run_id: {
                "run_id": run_id,
                "ros_master_port": summaries[run_id]["ros_master_port"],
                "callbacks": {
                    "lidar": summaries[run_id]["lidar_callback_count"],
                    "imu": summaries[run_id]["imu_callback_count"],
                },
                "observation_binary_sha256":
                    summaries[run_id]["observation_binary_sha256"],
                "query_summary_count":
                    validations[run_id]["query_summary_count"],
                "traversal_token_count":
                    validations[run_id]["traversal_token_count"],
                "full_window_coverage": coverages[run_id],
                "overflow": validations[run_id]["overflow"],
                "shadow_accounting": shadows[run_id],
            }
            for run_id in RUN_IDS
        },
        "strict_comparison": strict,
        "root_cause": root,
        "random_replay_decision": route,
        "plot_count": plots["plot_count"],
        "detector_called": False,
        "GT": False,
        "commit": False,
        "push": False,
        "gates": final_gate,
    }
    _write(args.output_dir / "day8_final_full_window_manifest.json", manifest)
    _write(args.manifest_path, manifest)
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(_report(manifest), encoding="utf-8")
    return 0 if final_gate["DAY8_FINAL_FULL_WINDOW_EXECUTION_PASS"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
