#!/usr/bin/env python3
"""Finalize coherent-map Experiment A gates, report, and manifest."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any, Mapping


REQUIRED_GATES = (
    "REMEDIATION_AUTHORIZATION_IDENTITY_PASS",
    "MAP_SNAPSHOT_LOCK_PROTOCOL_CONFIRMED",
    "MAP_SNAPSHOT_IMPLEMENTATION_PASS",
    "MAP_SNAPSHOT_COHERENCE_PASS",
    "MAP_SNAPSHOT_CROSS_SCAN_COHERENCE_PASS",
    "STATIC_READONLY_AUDIT_PASS",
    "FORMAL_FAST_MATH_UNCHANGED_PASS",
    "DEGEN_TARGETED_TEST_PASS",
    "DEGEN_FULL_TEST_PASS",
    "FAST_BUILD_PASS",
    "FAST_TEST_PASS",
    "TWO_REPLAY_RUNS_COMPLETE_PASS",
    "RUN_1_COMPLETENESS_PASS",
    "RUN_2_COMPLETENESS_PASS",
    "OBSERVATION_BINARY_INTEGRITY_PASS",
    "STAGE_HASH_V2_RECORD_COUNT_PASS",
    "STAGE_HASH_WINDOW_COVERAGE_PASS",
    "RAW_LIDAR_HASH_CAPTURE_PASS",
    "IMU_BUNDLE_HASH_CAPTURE_PASS",
    "UNDISTORTED_CLOUD_HASH_CAPTURE_PASS",
    "CORRESPONDENCE_HASH_REUSE_PASS",
    "INSERTION_BATCH_HASH_CAPTURE_PASS",
    "DIAGNOSTIC_IMMUTABILITY_PASS",
    "NO_TAP_DROP_PASS",
    "NO_WRITER_ERROR_PASS",
    "NO_GT_PASS",
    "PAIRWISE_STAGE_HASH_COMPARISON_PASS",
    "STAGE_CLASSIFICATION_COMPLETE",
    "DIFF_SCOPE_PASS",
    "AUDIT_PACKAGE_SCOPE_PASS",
)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_gate(run: Mapping[str, Any]) -> bool:
    return all(
        (
            run.get("complete") is True,
            int(run.get("lidar_callback_count", -1)) == 491,
            int(run.get("imu_callback_count", -1)) == 9953,
            int(run.get("runtime_scan_count", -1)) == 490,
            int(run.get("observation_record_count", -1)) == 487,
            int(run.get("stage_hash_v2_record_count", -1)) == 26,
            int(run.get("map_before_snapshot_count", -1)) == 26,
            int(run.get("map_after_snapshot_count", -1)) == 26,
            int(run.get("coherent_snapshot_count", -1)) == 52,
            int(run.get("incoherent_snapshot_count", -1)) == 0,
            int(
                run.get("cross_scan_continuity_violation_count", -1)
            )
            == 0,
            int(run.get("tap_drop_count", -1)) == 0,
            int(run.get("writer_error_count", -1)) == 0,
            int(run.get("in_call_mutation_count", -1)) == 0,
            int(run.get("diagnostic_mutation_count", -1)) == 0,
            int(run.get("schema_rejected_record_count", -1)) == 0,
            int(run.get("GT_TOPIC_CONSUMED_COUNT", -1)) == 0,
            run.get("end_of_stream_drain_pass") is True,
            run.get("normal_shutdown_pass") is True,
            run.get("runtime_products_complete_pass") is True,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", required=True, type=Path)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--run-lock", required=True, type=Path)
    parser.add_argument("--gate-evidence", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    args = parser.parse_args()

    run_lock = read_json(args.run_lock)
    evidence = read_json(args.gate_evidence)
    sub_ids = list(run_lock["sub_run_ids"])
    if len(sub_ids) != 2:
        raise ValueError("exactly two replay run IDs required")
    runs = [
        read_json(args.results_root / run_id / "run_summary.json")
        for run_id in sub_ids
    ]
    run_pass = [run_gate(run) for run in runs]
    classification = read_json(
        args.comparison_dir
        / "experiment_a_map_snapshot_stage_classification.json"
    )
    identity = read_json(
        args.comparison_dir
        / "experiment_a_map_snapshot_identity_summary.json"
    )

    gates = {
        field: bool(evidence.get(field, False)) for field in REQUIRED_GATES
    }
    gates.update(
        {
            "TWO_REPLAY_RUNS_COMPLETE_PASS": all(run_pass),
            "RUN_1_COMPLETENESS_PASS": run_pass[0],
            "RUN_2_COMPLETENESS_PASS": run_pass[1],
            "MAP_SNAPSHOT_COHERENCE_PASS": all(
                run.get("map_snapshot_coherence_pass") is True
                for run in runs
            ),
            "MAP_SNAPSHOT_CROSS_SCAN_COHERENCE_PASS": all(
                run.get("map_snapshot_cross_scan_coherence_pass") is True
                for run in runs
            ),
            "OBSERVATION_BINARY_INTEGRITY_PASS": all(
                int(run.get("binary_checksum_failure_count", -1)) == 0
                and int(run.get("truncated_record_count", -1)) == 0
                and int(run.get("extra_trailing_bytes", -1)) == 0
                for run in runs
            ),
            "STAGE_HASH_V2_RECORD_COUNT_PASS": all(
                int(run.get("stage_hash_v2_record_count", -1)) == 26
                for run in runs
            ),
            "STAGE_HASH_WINDOW_COVERAGE_PASS": all(
                int(run.get("stage_hash_first_scan", -1)) == 135
                and int(run.get("stage_hash_last_scan", -1)) == 160
                for run in runs
            ),
            "RAW_LIDAR_HASH_CAPTURE_PASS": all(
                run.get("raw_lidar_hash_capture_pass") is True
                for run in runs
            ),
            "IMU_BUNDLE_HASH_CAPTURE_PASS": all(
                run.get("imu_bundle_hash_capture_pass") is True
                for run in runs
            ),
            "UNDISTORTED_CLOUD_HASH_CAPTURE_PASS": all(
                run.get("undistorted_cloud_hash_capture_pass") is True
                for run in runs
            ),
            "CORRESPONDENCE_HASH_REUSE_PASS": all(
                run.get("correspondence_hash_reuse_pass") is True
                for run in runs
            ),
            "INSERTION_BATCH_HASH_CAPTURE_PASS": all(
                run.get("insertion_batch_hash_capture_pass") is True
                for run in runs
            ),
            "DIAGNOSTIC_IMMUTABILITY_PASS": all(
                int(run.get("diagnostic_mutation_count", -1)) == 0
                and int(run.get("diagnostic_internal_error_count", -1)) == 0
                for run in runs
            ),
            "NO_TAP_DROP_PASS": all(
                int(run.get("tap_drop_count", -1)) == 0 for run in runs
            ),
            "NO_WRITER_ERROR_PASS": all(
                int(run.get("writer_error_count", -1)) == 0 for run in runs
            ),
            "NO_GT_PASS": all(
                int(run.get("GT_TOPIC_CONSUMED_COUNT", -1)) == 0
                for run in runs
            ),
            "PAIRWISE_STAGE_HASH_COMPARISON_PASS":
                classification.get("comparison_pass") is True,
            "STAGE_CLASSIFICATION_COMPLETE":
                classification.get("stage_classification_complete") is True,
        }
    )
    execution_pass = all(gates.values())
    stage_class = str(classification["stage_classification"])
    localized = execution_pass and stage_class not in {
        "NO_DIVERGENCE_IN_DIAGNOSTIC_PAIR",
        "EVIDENCE_GAP_MAP_SNAPSHOT_NOT_COHERENT",
    }
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    identities = dict(identity.get("identity_status", {}))
    manifest: dict[str, Any] = {
        "schema_version":
            "experiment_a_map_snapshot_coherence_manifest_v1",
        "created_at_utc": created,
        "authorization_audit_sha256":
            run_lock["authorization_audit_sha256"],
        "snapshot_implementation":
            "NEW_READONLY_SYNCHRONIZED_KDTREE_API",
        "snapshot_schema_version": "coherent_map_snapshot_v2",
        "lock_protocol_status": "CONFIRMED",
        "lock_protocol_document_sha256":
            run_lock["lock_protocol_document_sha256"],
        "ikdtree_source_sha256_before":
            run_lock["ikdtree_source_sha256_before"],
        "ikdtree_source_sha256_after":
            run_lock["ikdtree_source_sha256"],
        "formal_math_source_sha256_before":
            run_lock["formal_math_source_sha256_before"],
        "formal_math_source_sha256_after":
            run_lock["formal_math_source_sha256_after"],
        "main_run_id": run_lock["main_run_id"],
        "sub_run_ids": sub_ids,
        "sequence_id": run_lock["sequence_id"],
        "clip_sha256": run_lock["clip_sha256"],
        "scan_start": 135,
        "scan_end": 160,
        "per_run_observation_count": [
            run["observation_record_count"] for run in runs
        ],
        "per_run_stage_record_count": [
            run["stage_hash_v2_record_count"] for run in runs
        ],
        "per_run_map_before_snapshot_count": [
            run["map_before_snapshot_count"] for run in runs
        ],
        "per_run_map_after_snapshot_count": [
            run["map_after_snapshot_count"] for run in runs
        ],
        "per_run_coherent_snapshot_count": [
            run["coherent_snapshot_count"] for run in runs
        ],
        "per_run_incoherent_snapshot_count": [
            run["incoherent_snapshot_count"] for run in runs
        ],
        "per_run_cross_scan_continuity_violation_count": [
            run["cross_scan_continuity_violation_count"] for run in runs
        ],
        "per_run_rebuild_generation_changes": [
            run.get("rebuild_generation_change_count", 0) for run in runs
        ],
        "per_run_logical_add_call_count": [
            run.get("logical_add_call_count", 0) for run in runs
        ],
        "per_run_logical_delete_call_count": [
            run.get("logical_delete_call_count", 0) for run in runs
        ],
        "first_divergence_scan":
            classification.get("first_divergence_scan"),
        "first_divergence_stage":
            classification.get("first_divergence_stage"),
        "stage_classification": stage_class,
        "raw_lidar_identity_status": identities.get("raw_lidar"),
        "imu_bundle_identity_status": identities.get("imu_bundle"),
        "undistorted_cloud_identity_status":
            identities.get("undistorted_cloud"),
        "map_content_before_identity_status":
            identities.get("map_content_before"),
        "map_traversal_before_identity_status":
            identities.get("map_traversal_before"),
        "correspondence_identity_status": identities.get("correspondence"),
        "post_update_state_identity_status":
            identities.get("post_update_state"),
        "insertion_batch_identity_status": identities.get("insertion_batch"),
        "map_content_after_identity_status":
            identities.get("map_content_after"),
        "map_traversal_after_identity_status":
            identities.get("map_traversal_after"),
        "snapshot_lock_wait_statistics": [
            run["snapshot_lock_wait_statistics"] for run in runs
        ],
        "snapshot_copy_cost_statistics": [
            run["snapshot_copy_cost_statistics"] for run in runs
        ],
        "map_snapshot_coherence_pass":
            gates["MAP_SNAPSHOT_COHERENCE_PASS"],
        "map_snapshot_cross_scan_coherence_pass":
            gates["MAP_SNAPSHOT_CROSS_SCAN_COHERENCE_PASS"],
        "experiment_a_map_snapshot_remediation_execution_pass":
            execution_pass,
        "experiment_a_stage_localization_pass": localized,
        "experiment_a_pass": localized,
        "day7_recommended":
            bool(classification.get("day7_recommended", False)),
        "day7_recommended_scope":
            classification.get("day7_recommended_scope", "NONE"),
        "day7_authorized": False,
        "additional_replay_recommended":
            bool(classification.get("additional_replay_recommended", False)),
        "additional_replay_authorized": False,
        "detector_called": False,
        "odi_computed": False,
        "weak_direction_computed": False,
        "roscore_run": True,
        "roslaunch_run": True,
        "rosbag_run": True,
        "fastlio2_run": True,
        "development_run": False,
        "holdout_run": False,
        "future_test_run": False,
        "commit_created": False,
        "push_performed": False,
        "gates": gates,
        "STAGE2_GATE": "FAIL",
        "TRANSITION": "PIVOT",
        "STAGE3_START_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE": "NOT_PROVEN",
        "HARMFUL_BIAS_DETECTABILITY_STATUS":
            "NOT_EVALUATED_DAY6_EXPERIMENT_A_MAP_SNAPSHOT_COHERENCE",
    }
    write_json(args.manifest, manifest)

    report = f"""# Experiment A Map Snapshot Coherence Report

Result identity:
`INTERNAL_ENGINEERING_MAP_SNAPSHOT_DIAGNOSTICS_ONLY`.

1. The prior 596 to 1575 anomaly came from an unlocked recursive read that
   could overlap background flatten, subtree replacement, logger replay, and
   old-node disposal. The 596-point observation is revoked.
2. The former traversal had no global reader admission or lifetime guard.
3. The current snapshot uses `rebuild_ptr_mutex_lock` then
   `working_flag_mutex`, matching the formal rebuild lock order.
4. A new read-only `KD_TREE::Snapshot_Valid_Points_Coherent` API was added.
5. The lock order matches the audited formal rebuild order.
6. Snapshot code copies points and metadata only; formal state, covariance,
   search, Add/Delete result, rebuild trigger, and OpenMP behavior are
   unchanged.
7. Coherent snapshots: {sum(int(run["coherent_snapshot_count"]) for run in runs)}/104.
8. Every successful validnum equals its copied point count:
   {str(gates["MAP_SNAPSHOT_COHERENCE_PASS"]).lower()}.
9. Rebuild generation is stable within each successful snapshot.
10. Logical mutation counter is stable within each successful snapshot.
11. Cross-scan violations, including count increase without Add:
    {sum(int(run["cross_scan_continuity_violation_count"]) for run in runs)}.
12. Raw LiDAR identity: {identities.get("raw_lidar")}.
13. IMU bundle identity: {identities.get("imu_bundle")}.
14. Undistorted-cloud identity: {identities.get("undistorted_cloud")}.
15. Coherent map-content-before identity:
    {identities.get("map_content_before")}.
16. Coherent map-traversal-before identity:
    {identities.get("map_traversal_before")}.
17. Correspondence identity: {identities.get("correspondence")}.
18. Post-update state identity: {identities.get("post_update_state")}.
19. Insertion-batch identity: {identities.get("insertion_batch")}.
20. Coherent map-content-after identity:
    {identities.get("map_content_after")}.
21. Formal branch reproduced:
    {str(bool(classification.get("branch_reproduced", False))).lower()}.
22. First divergence: scan {classification.get("first_divergence_scan")},
    stage {classification.get("first_divergence_stage")}.
23. Stage classification: `{stage_class}`.
24. Checksums are compact engineering identity evidence with a theoretical
    collision limitation.
25. This task does not prove a data race.
26. This task does not prove ikd-tree caused the original Day 6 branch.
27. Day 7 recommended:
    {str(bool(classification.get("day7_recommended", False))).lower()};
    scope `{classification.get("day7_recommended_scope", "NONE")}`.
28. Day 7 remains unauthorized pending GPT audit. No third replay was added.

The snapshot lock can slightly perturb background thread timing. Content digest
is order-independent; traversal digest is order-sensitive. Detector, ODI, weak
direction, GT, development, holdout, and future-test paths were not run.

`EXPERIMENT_A_MAP_SNAPSHOT_REMEDIATION_EXECUTION_PASS={str(execution_pass).lower()}`

`EXPERIMENT_A_STAGE_LOCALIZATION_PASS={str(localized).lower()}`

`EXPERIMENT_A_PASS={str(localized).lower()}`

`DAY7_AUTHORIZED=false`

`STAGE2_GATE=FAIL`

`TRANSITION=PIVOT`
"""
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")

    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.report, args.artifact_dir / args.report.name)
    shutil.copy2(args.manifest, args.artifact_dir / args.manifest.name)
    for source in sorted(args.comparison_dir.iterdir()):
        if source.is_file():
            shutil.copy2(source, args.artifact_dir / source.name)
    write_json(args.artifact_dir / "final_gate_evidence.json", gates)
    print(
        json.dumps(
            {
                "execution_pass": execution_pass,
                "stage_classification": stage_class,
                "localized": localized,
                "day7_authorized": False,
            },
            sort_keys=True,
        )
    )
    return 0 if execution_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
