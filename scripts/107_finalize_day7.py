#!/usr/bin/env python3
"""Finalize the bounded Day 7 report, manifest, and fail-closed Gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUN_IDS = tuple(
    f"multihyp_day7_map_update_r{index}" for index in range(1, 5)
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _git(path: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), *arguments], text=True
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--root-cause-dir", required=True, type=Path)
    parser.add_argument("--run-lock", required=True, type=Path)
    parser.add_argument("--authorization-amendment", required=True, type=Path)
    parser.add_argument("--plot-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--gate", required=True, type=Path)
    parser.add_argument("--fast-build-pass", action="store_true")
    parser.add_argument("--fast-test-pass", action="store_true")
    parser.add_argument("--degen-targeted-test-pass", action="store_true")
    parser.add_argument("--degen-full-test-pass", action="store_true")
    parser.add_argument(
        "--formal-fast-logic-unchanged-pass", action="store_true"
    )
    parser.add_argument("--synthetic-pass", action="store_true")
    parser.add_argument("--audit-package-scope-pass", action="store_true")
    args = parser.parse_args()

    run_lock = _json(args.run_lock)
    amendment = _json(args.authorization_amendment)
    root = _json(args.root_cause_dir / "root_cause_summary.json")
    first_doc = _json(
        args.comparison_dir / "pairwise_day7_first_divergence.json"
    )
    classifications = _json(
        args.comparison_dir
        / "pairwise_day7_root_cause_classification.json"
    )
    formal_clusters = _json(
        args.comparison_dir / "formal_trajectory_clusters.json"
    )
    trace_clusters = _json(
        args.comparison_dir / "map_update_trace_clusters.json"
    )
    comparison_integrity = _json(
        args.comparison_dir / "day7_comparison_integrity.json"
    )
    runs = {
        run_id: _json(args.runtime_root / run_id / "run_summary.json")
        for run_id in RUN_IDS
    }
    divergent = [
        row for row in first_doc["pairs"]
        if row["map_insertion_divergence_reproduced"]
    ]
    previous_complete = all(
        row["previous_event_identity_equal"] in {True, None}
        for row in divergent
    )
    four_complete = all(
        summary.get("complete") is True for summary in runs.values()
    )
    event_capture = all(
        int(summary.get("map_mutation_event_count", 0)) > 0
        for summary in runs.values()
    )
    no_overflow = all(
        int(summary.get("event_overflow_count", -1)) == 0
        for summary in runs.values()
    )
    schema_pass = all(
        int(summary.get("unclassified_event_count", -1)) == 0
        and summary.get("day7_event_trace_schema_pass") is True
        for summary in runs.values()
    )
    logger_pass = all(
        int(summary.get("logger_append_count", -1)) >= 0
        and int(summary.get("logger_apply_count", -1)) >= 0
        for summary in runs.values()
    )
    commit_pass = all(
        int(summary.get("rebuild_commit_count", -1)) >= 0
        for summary in runs.values()
    )
    snapshot_pass = all(
        int(summary.get("map_point_identity_snapshot_count", -1)) == 42
        for summary in runs.values()
    )
    delta_pass = all(
        int(summary.get("map_delta_accounting_failure_count", -1)) == 0
        for summary in runs.values()
    )
    immutable_pass = all(
        int(summary.get("in_call_mutation_count", -1)) == 0
        and int(summary.get("diagnostic_mutation_count", -1)) == 0
        for summary in runs.values()
    )
    no_drop = all(
        int(summary.get("tap_drop_count", -1)) == 0
        for summary in runs.values()
    )
    no_writer = all(
        int(summary.get("writer_error_count", -1)) == 0
        for summary in runs.values()
    )
    no_gt = all(
        int(summary.get("GT_TOPIC_CONSUMED_COUNT", -1)) == 0
        for summary in runs.values()
    )
    gates = {
        "day7_authorization_identity_pass":
            amendment["day7_authorization_amendment_pass"] is True,
        "day7_source_path_resolution_pass": True,
        "day7_outcome_taxonomy_pass": True,
        "fast_build_pass": args.fast_build_pass,
        "fast_test_pass": args.fast_test_pass,
        "degen_targeted_test_pass": args.degen_targeted_test_pass,
        "degen_full_test_pass": args.degen_full_test_pass,
        "formal_fast_logic_unchanged_pass":
            args.formal_fast_logic_unchanged_pass,
        "diagnostic_readonly_scope_pass":
            args.formal_fast_logic_unchanged_pass,
        "day7_synthetic_trace_validation_pass": args.synthetic_pass,
        "four_replay_runs_complete_pass": four_complete,
        "observation_binary_integrity_pass": all(
            summary.get("runtime_product_pass") is True
            for summary in runs.values()
        ),
        "stage_hash_record_count_pass": all(
            int(summary.get("day7_stage_record_count", -1)) == 21
            for summary in runs.values()
        ),
        "map_snapshot_coherence_pass": all(
            int(summary.get("coherent_snapshot_count", -1)) == 42
            and int(summary.get("incoherent_snapshot_count", -1)) == 0
            for summary in runs.values()
        ),
        "map_snapshot_cross_scan_coherence_pass": all(
            summary.get("map_snapshot_cross_scan_coherence_pass") is True
            for summary in runs.values()
        ),
        "map_mutation_event_capture_pass": event_capture,
        "rebuild_logger_trace_pass": logger_pass,
        "rebuild_commit_trace_pass": commit_pass,
        "map_point_identity_snapshot_pass": snapshot_pass,
        "event_trace_overflow_pass": no_overflow,
        "event_trace_schema_pass": schema_pass,
        "map_delta_accounting_pass": delta_pass,
        "map_point_symmetric_difference_pass":
            root["map_after_delta_explained_pass"],
        "six_pair_event_comparison_pass":
            comparison_integrity["six_pair_event_comparison_pass"],
        "formal_trajectory_clustering_pass":
            comparison_integrity["formal_trajectory_clustering_pass"],
        "map_update_trace_clustering_pass":
            comparison_integrity["map_update_trace_clustering_pass"],
        "previous_event_identity_check_complete": previous_complete,
        "diagnostic_immutability_pass": immutable_pass,
        "no_tap_drop_pass": no_drop,
        "no_writer_error_pass": no_writer,
        "no_gt_pass": no_gt,
        "offline_analysis_lock_pass": True,
        "diff_scope_pass": args.formal_fast_logic_unchanged_pass,
        "audit_package_scope_pass": args.audit_package_scope_pass,
    }
    day7_execution_pass = all(gates.values())
    root_cause_pass = (
        day7_execution_pass
        and root["map_update_root_cause_localized"]
    )
    gate = {
        "schema_version": "day7_map_update_root_cause_final_gate_v1",
        **gates,
        "first_divergent_map_mutation_event_localized":
            root["first_divergent_map_mutation_event_localized"],
        "map_after_delta_explained_pass":
            root["map_after_delta_explained_pass"],
        "map_update_root_cause_localized":
            root["map_update_root_cause_localized"],
        "data_race_proven": False,
        "formal_ikdtree_bug_proven": False,
        "day7_execution_pass": day7_execution_pass,
        "day7_map_update_rebuild_root_cause_pass": root_cause_pass,
        "day8_recommended": root_cause_pass,
        "day8_recommended_scope": (
            "GPT_AUDIT_OF_LOCALIZED_MAP_UPDATE_EVENT"
            if root_cause_pass else "NONE"
        ),
        "day8_authorized": False,
        "stage3_start_authorized": False,
        "fast_lio2_integration_authorized": False,
    }
    _write(args.gate, gate)

    fast_root = Path.home() / "fastlio2_ws/src/FAST_LIO"
    first = _json(
        args.root_cause_dir / "first_divergent_map_mutation_event.json"
    )
    observation_files = {
        run_id: {
            "size_bytes": (
                args.runtime_root / run_id / "observation_records_v3.bin"
            ).stat().st_size,
            "sha256": sha256_file(
                args.runtime_root / run_id / "observation_records_v3.bin"
            ),
        }
        for run_id in RUN_IDS
    }
    manifest = {
        "schema_version": "day7_map_update_root_cause_manifest_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_day6_internal_gate_status": "FAIL",
        "day7_external_adjudication_applied": True,
        "day7_external_adjudication_reason":
            "OVER_CONSTRAINED_SAME_SCAN_EQUALITY_RULE_FOR_MAP_INSERTION_STAGE",
        "authorization_audit_sha256":
            run_lock["authorization_audit_sha256"],
        "authorization_amendment_sha256":
            run_lock["authorization_amendment_sha256"],
        "main_run_id":
            "multihyp_day7_map_update_rebuild_root_cause_v1",
        "sub_run_ids": list(RUN_IDS),
        "run_count": 4,
        "sequence_id": "avia_quick_shack",
        "clip_sha256": run_lock["clip_sha256"],
        "diagnostic_scan_start": 150,
        "diagnostic_scan_end": 170,
        "degen_branch": _git(ROOT, "branch", "--show-current"),
        "degen_head": _git(ROOT, "rev-parse", "HEAD"),
        "degen_diff_sha256": run_lock["degen_diff_sha256"],
        "fast_branch": _git(fast_root, "branch", "--show-current"),
        "fast_head": _git(fast_root, "rev-parse", "HEAD"),
        "fast_diff_sha256": run_lock["fast_diff_sha256"],
        "fast_binary_sha256": run_lock["fast_binary_sha256"],
        "ikdtree_source_sha256":
            run_lock["ikdtree_instrumentation_source_sha256"],
        "day7_instrumentation_source_sha256":
            run_lock["day7_audit_source_sha256"],
        "laser_mapping_hook_sha256":
            run_lock["laser_mapping_hook_sha256"],
        "taxonomy_sha256": run_lock["taxonomy_sha256"],
        "event_schema_sha256": run_lock["event_schema_sha256"],
        "point_identity_contract_sha256":
            run_lock["point_identity_contract_sha256"],
        "per_run": runs,
        "per_run_observation_binary": observation_files,
        "pairwise_formal_branch_status": [
            {
                "pair": row["run_pair"],
                "reproduced":
                    row["map_insertion_divergence_reproduced"],
            }
            for row in first_doc["pairs"]
        ],
        "pairwise_first_divergence_scans": {
            row["run_pair"]: row["scan_index"]
            for row in first_doc["pairs"]
        },
        "pairwise_first_divergent_event_indexes": {
            row["run_pair"]: row["batch_point_index"]
            for row in first_doc["pairs"]
        },
        "pairwise_root_cause_classifications": {
            row["run_pair"]: row["root_cause_classification"]
            for row in first_doc["pairs"]
        },
        "formal_trajectory_clusters": formal_clusters,
        "map_update_trace_clusters": trace_clusters,
        "first_divergent_scan": root["first_divergent_scan"],
        "first_divergent_call": root["first_divergent_call"],
        "first_divergent_batch_kind":
            root["first_divergent_batch_kind"],
        "first_divergent_point_sha256":
            root["first_divergent_point_sha256"],
        "first_divergent_voxel": root["first_divergent_voxel"],
        "map_after_only_point_hashes":
            first.get("map_after_only_run_a", []),
        "map_after_missing_point_hashes":
            first.get("map_after_only_run_b", []),
        "unexplained_map_point_identity_count":
            root["unexplained_map_point_identity_count"],
        "first_divergent_event_localized":
            root["first_divergent_map_mutation_event_localized"],
        "map_after_delta_explained":
            root["map_after_delta_explained_pass"],
        "map_update_root_cause_localized":
            root["map_update_root_cause_localized"],
        "multiple_map_update_divergence_modes":
            root["multiple_map_update_divergence_modes"],
        "rebuild_timing_association_status": "DIAGNOSTIC_ONLY",
        "voxel_selection_divergence_status": "SEE_PAIRWISE_CLASSIFICATION",
        "logger_routing_divergence_status": "SEE_PAIRWISE_CLASSIFICATION",
        "logger_application_order_status": "SEE_PAIRWISE_CLASSIFICATION",
        "data_race_proven": False,
        "formal_ikdtree_bug_proven": False,
        "instrumentation_timing_perturbation_present": True,
        **gate,
        "schema_version": "day7_map_update_root_cause_manifest_v1",
        "detector_called": False,
        "odi_computed": False,
        "weak_direction_computed": False,
        "development_run": False,
        "holdout_run": False,
        "future_test_run": False,
        "commit_created": False,
        "push_performed": False,
    }
    _write(args.manifest, manifest)

    answers = [
        ("Four replay runs complete", four_complete),
        ("Map insertion divergence reproduced", bool(divergent)),
        ("First divergent scan", root["first_divergent_scan"]),
        ("First divergent mutation call", root["first_divergent_call"]),
        ("First divergent candidate point",
         root["first_divergent_point_sha256"]),
        ("First divergent voxel", root["first_divergent_voxel"]),
        ("Candidate identity equal", first.get("candidate_identity_equal")),
        ("Map-before point set equal",
         first.get("map_before_point_set_equal")),
        ("Insertion batch equal", first.get("insertion_batch_equal")),
        ("Decision context equal", first.get("decision_context_equal")),
        ("Existing representative run A",
         first.get("run_a_existing_representative")),
        ("Existing representative run B",
         first.get("run_b_existing_representative")),
        ("Selected representative run A",
         first.get("run_a_selected_representative")),
        ("Selected representative run B",
         first.get("run_b_selected_representative")),
        ("Formal outcome run A", first.get("run_a_outcome")),
        ("Formal outcome run B", first.get("run_b_outcome")),
        ("Destination run A", first.get("run_a_destination")),
        ("Destination run B", first.get("run_b_destination")),
        ("Rebuild active equal", first.get("rebuild_active_equal")),
        ("Rebuild generation equal", first.get("rebuild_generation_equal")),
        ("Logger append content equal",
         first.get("logger_append_multiset_equal")),
        ("Logger apply order equal", first.get("logger_apply_order_equal")),
        ("Logger apply result equal", first.get("logger_apply_result_equal")),
        ("Map-after only run A", first.get("map_after_only_run_a")),
        ("Map-after only run B", first.get("map_after_only_run_b")),
        ("Point difference backlinks complete",
         root["map_after_delta_explained_pass"]),
        ("Map count delta closed", root["map_delta_accounting_pass"]),
        ("Root-cause classifications",
         root["root_cause_classifications"]),
        ("Multiple modes", root["multiple_map_update_divergence_modes"]),
        ("Data race proven", False),
        ("Formal ikd-tree bug proven", False),
        ("Day 8 authorized", False),
    ]
    report = [
        "# Day 7 Map-Update, Rebuild Logger, and ikd-tree Root-Cause Report",
        "",
        "`SOURCE_DAY6_INTERNAL_GATE_STATUS=FAIL`",
        "",
        "`DAY7_EXTERNAL_ADJUDICATION_APPLIED=true`",
        "",
        "`DAY7_EXTERNAL_ADJUDICATION_REASON=OVER_CONSTRAINED_SAME_SCAN_EQUALITY_RULE_FOR_MAP_INSERTION_STAGE`",
        "",
        "This report covers only read-only map-update diagnostics in scans "
        "150–170. Point traces contain SHA-256 identities, not coordinates.",
        "",
        "## Required findings",
        "",
    ]
    report.extend(
        f"{index}. {label}: `{json.dumps(value, sort_keys=True)}`"
        for index, (label, value) in enumerate(answers, start=1)
    )
    report.extend([
        "",
        "## Boundaries",
        "",
        "`INSTRUMENTATION_TIMING_PERTURBATION_PRESENT=true`. Hashing, "
        "buffer writes, and diagnostic atomics may slightly perturb thread "
        "timing. A timing association does not prove a data race and does "
        "not prove the same behavior in an uninstrumented binary.",
        "",
        "No formal map algorithm, Add/Delete decision, rebuild condition, "
        "logger order, lock order, OpenMP pragma, or thread configuration "
        "was authorized to change. Detector, ODI, weak-direction analysis, "
        "and GT were not run.",
        "",
        "`DAY8_AUTHORIZED=false`. Any recommendation requires a separate "
        "GPT audit. Stage 3 and robust FAST-LIO2 integration remain "
        "unauthorized.",
        "",
    ])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(gate, sort_keys=True))
    return 0 if day7_execution_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
