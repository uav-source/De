#!/usr/bin/env python3
"""Finalize Experiment A gates, report, manifest, and compact artifact view."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any, Mapping


GATE_FIELDS = (
    "EXPERIMENT_A_AUTHORIZATION_IDENTITY_PASS",
    "EXPERIMENT_A_HOOK_RESOLUTION_PASS",
    "FAST_BUILD_PASS",
    "FAST_TEST_PASS",
    "DEGEN_TARGETED_TEST_PASS",
    "DEGEN_FULL_TEST_PASS",
    "STATIC_READONLY_AUDIT_PASS",
    "DIAGNOSTIC_IMMUTABILITY_PASS",
    "TWO_REPLAY_RUNS_COMPLETE_PASS",
    "RUN_1_COMPLETENESS_PASS",
    "RUN_2_COMPLETENESS_PASS",
    "CLIP_IDENTITY_PASS",
    "ENDPOINT_CONTRACT_PASS",
    "TAIL_ADJUDICATION_RULE_REUSE_PASS",
    "END_OF_STREAM_DRAIN_PASS",
    "NORMAL_SHUTDOWN_PASS",
    "OBSERVATION_BINARY_INTEGRITY_PASS",
    "OBSERVATION_COUNT_COMPLETENESS_PASS",
    "STAGE_HASH_RECORD_COUNT_PASS",
    "STAGE_HASH_WINDOW_COVERAGE_PASS",
    "STAGE_HASH_SCHEMA_PASS",
    "RAW_LIDAR_HASH_CAPTURE_PASS",
    "IMU_BUNDLE_HASH_CAPTURE_PASS",
    "UNDISTORTED_CLOUD_HASH_CAPTURE_PASS",
    "MAP_BEFORE_HASH_CAPTURE_PASS",
    "CORRESPONDENCE_HASH_REUSE_PASS",
    "INSERTION_BATCH_HASH_CAPTURE_PASS",
    "MAP_AFTER_HASH_CAPTURE_PASS",
    "PAIRWISE_STAGE_HASH_COMPARISON_PASS",
    "STAGE_CLASSIFICATION_COMPLETE",
    "NO_TAP_DROP_PASS",
    "NO_WRITER_ERROR_PASS",
    "NO_GT_PASS",
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


def _run_gate(summary: Mapping[str, Any]) -> bool:
    return all(
        (
            summary.get("complete") is True,
            int(summary.get("lidar_callback_count", -1)) == 491,
            int(summary.get("imu_callback_count", -1)) == 9953,
            int(summary.get("observation_record_count", -1)) == 487,
            int(summary.get("stage_hash_record_count", -1)) == 26,
            int(summary.get("stage_hash_first_scan", -1)) == 135,
            int(summary.get("stage_hash_last_scan", -1)) == 160,
            int(summary.get("tap_drop_count", -1)) == 0,
            int(summary.get("writer_error_count", -1)) == 0,
            int(summary.get("in_call_mutation_count", -1)) == 0,
            int(summary.get("diagnostic_mutation_count", -1)) == 0,
            int(summary.get("schema_rejected_record_count", -1)) == 0,
            int(summary.get("GT_TOPIC_CONSUMED_COUNT", -1)) == 0,
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
    sub_ids = tuple(run_lock["sub_run_ids"])
    if len(sub_ids) != 2:
        raise ValueError("exactly two sub-run IDs required")
    runs = [
        read_json(args.results_root / run_id / "run_summary.json")
        for run_id in sub_ids
    ]
    classification = read_json(
        args.comparison_dir / "experiment_a_stage_classification.json"
    )
    identity = read_json(
        args.comparison_dir / "experiment_a_identity_summary.json"
    )
    run_passes = [_run_gate(run) for run in runs]

    gates = {field: bool(evidence.get(field, False)) for field in GATE_FIELDS}
    gates.update(
        {
            "TWO_REPLAY_RUNS_COMPLETE_PASS": all(run_passes),
            "RUN_1_COMPLETENESS_PASS": run_passes[0],
            "RUN_2_COMPLETENESS_PASS": run_passes[1],
            "CLIP_IDENTITY_PASS": run_lock.get("clip_sha256")
            == (
                "272325265978787c838e010b1f0da963a15fb4b08ff8730fc3"
                "dd9901e32a0e20"
            ),
            "ENDPOINT_CONTRACT_PASS": all(
                run.get("lidar_callback_count") == 491
                and run.get("imu_callback_count") == 9953
                for run in runs
            ),
            "TAIL_ADJUDICATION_RULE_REUSE_PASS": all(
                run.get("adjudicated_tail_handoff_pass") is True
                for run in runs
            ),
            "END_OF_STREAM_DRAIN_PASS": all(
                run.get("end_of_stream_drain_pass") is True for run in runs
            ),
            "NORMAL_SHUTDOWN_PASS": all(
                run.get("normal_shutdown_pass") is True for run in runs
            ),
            "OBSERVATION_BINARY_INTEGRITY_PASS": all(
                int(run.get("binary_checksum_failure_count", -1)) == 0
                and int(run.get("truncated_record_count", -1)) == 0
                and int(run.get("extra_trailing_bytes", -1)) == 0
                for run in runs
            ),
            "OBSERVATION_COUNT_COMPLETENESS_PASS": all(
                run.get("observation_record_count") == 487 for run in runs
            ),
            "STAGE_HASH_RECORD_COUNT_PASS": all(
                run.get("stage_hash_record_count") == 26 for run in runs
            ),
            "STAGE_HASH_WINDOW_COVERAGE_PASS": all(
                run.get("stage_hash_first_scan") == 135
                and run.get("stage_hash_last_scan") == 160
                for run in runs
            ),
            "STAGE_HASH_SCHEMA_PASS": all(
                run.get("stage_hash_schema_pass") is True for run in runs
            ),
            "RAW_LIDAR_HASH_CAPTURE_PASS": all(
                run.get("raw_lidar_hash_capture_pass") is True for run in runs
            ),
            "IMU_BUNDLE_HASH_CAPTURE_PASS": all(
                run.get("imu_bundle_hash_capture_pass") is True for run in runs
            ),
            "UNDISTORTED_CLOUD_HASH_CAPTURE_PASS": all(
                run.get("undistorted_cloud_hash_capture_pass") is True
                for run in runs
            ),
            "MAP_BEFORE_HASH_CAPTURE_PASS": all(
                run.get("map_before_hash_capture_pass") is True for run in runs
            ),
            "CORRESPONDENCE_HASH_REUSE_PASS": all(
                run.get("correspondence_hash_reuse_pass") is True
                for run in runs
            ),
            "INSERTION_BATCH_HASH_CAPTURE_PASS": all(
                run.get("insertion_batch_hash_capture_pass") is True
                for run in runs
            ),
            "MAP_AFTER_HASH_CAPTURE_PASS": all(
                run.get("map_after_hash_capture_pass") is True for run in runs
            ),
            "PAIRWISE_STAGE_HASH_COMPARISON_PASS":
                classification.get("comparison_pass") is True,
            "STAGE_CLASSIFICATION_COMPLETE":
                classification.get("stage_classification_complete") is True,
            "DIAGNOSTIC_IMMUTABILITY_PASS": all(
                run.get("diagnostic_mutation_count") == 0
                and run.get("diagnostic_internal_error_count") == 0
                for run in runs
            ),
            "NO_TAP_DROP_PASS": all(
                run.get("tap_drop_count") == 0 for run in runs
            ),
            "NO_WRITER_ERROR_PASS": all(
                run.get("writer_error_count") == 0 for run in runs
            ),
            "NO_GT_PASS": all(
                run.get("GT_TOPIC_CONSUMED_COUNT") == 0 for run in runs
            ),
        }
    )
    execution_pass = all(gates.values())
    stage_class = str(classification["stage_classification"])
    localized = execution_pass and stage_class not in {
        "NO_DIVERGENCE_IN_DIAGNOSTIC_PAIR",
        "EVIDENCE_GAP",
    }
    identities = dict(identity["identity_status"])
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest: dict[str, Any] = {
        "schema_version": "day6_experiment_a_input_map_hash_manifest_v1",
        "created_at_utc": created,
        "authorization_audit_sha256": run_lock[
            "authorization_audit_sha256"
        ],
        "main_run_id": run_lock["main_run_id"],
        "sub_run_ids": list(sub_ids),
        "sequence_id": "avia_quick_shack",
        "clip_sha256": run_lock["clip_sha256"],
        "degen_branch": run_lock["degen_branch"],
        "degen_head": run_lock["degen_head"],
        "degen_diff_sha256": run_lock["degen_diff_sha256"],
        "fast_branch": run_lock["fast_branch"],
        "fast_head": run_lock["fast_head"],
        "fast_diff_sha256": run_lock["fast_diff_sha256"],
        "fast_binary_sha256": run_lock["fast_binary_sha256"],
        "diagnostic_module_sha256": run_lock["diagnostic_module_sha256"],
        "hash_algorithm": "FNV1A64_EXACT_BYTES_V1",
        "map_digest_version": "MapContentDigestV1+MapTraversalDigestV1",
        "scan_start": 135,
        "scan_end": 160,
        "expected_stage_record_count": 26,
        "per_run_callback_counts": [
            {
                "lidar": run["lidar_callback_count"],
                "imu": run["imu_callback_count"],
            }
            for run in runs
        ],
        "per_run_observation_counts": [
            run["observation_record_count"] for run in runs
        ],
        "per_run_stage_record_counts": [
            run["stage_hash_record_count"] for run in runs
        ],
        "per_run_raw_runner_exit_code": [
            run["raw_runner_exit_code"] for run in runs
        ],
        "per_run_raw_handoff": [
            run["raw_tail_handoff_pass"] for run in runs
        ],
        "per_run_adjudicated_handoff": [
            run["adjudicated_tail_handoff_pass"] for run in runs
        ],
        "per_run_tap_drop": [run["tap_drop_count"] for run in runs],
        "per_run_writer_error": [run["writer_error_count"] for run in runs],
        "per_run_in_call_mutation": [
            run["in_call_mutation_count"] for run in runs
        ],
        "per_run_diagnostic_mutation": [
            run["diagnostic_mutation_count"] for run in runs
        ],
        "first_divergence_scan": classification["first_divergence_scan"],
        "first_divergence_stage": classification["first_divergence_stage"],
        "stage_classification": stage_class,
        "raw_lidar_identity_status": identities["raw_lidar"],
        "imu_bundle_identity_status": identities["imu_bundle"],
        "undistorted_cloud_identity_status": identities["undistorted_cloud"],
        "prior_state_identity_status": identities["prior_state"],
        "prior_covariance_identity_status": identities["prior_covariance"],
        "map_content_before_identity_status": identities[
            "map_content_before"
        ],
        "map_traversal_before_identity_status": identities[
            "map_traversal_before"
        ],
        "correspondence_identity_status": identities["correspondence"],
        "post_update_state_identity_status": identities["post_update_state"],
        "insertion_batch_identity_status": identities["insertion_batch"],
        "map_content_after_identity_status": identities["map_content_after"],
        "map_traversal_after_identity_status": identities[
            "map_traversal_after"
        ],
        "checksum_collision_limitation_disclosed": True,
        "experiment_a_execution_pass": execution_pass,
        "experiment_a_stage_localization_pass": localized,
        "experiment_a_pass": localized,
        "day7_recommended": classification["day7_recommended"],
        "day7_recommended_scope": classification["day7_recommended_scope"],
        "day7_authorized": False,
        "additional_replay_recommended": classification[
            "additional_replay_recommended"
        ],
        "additional_replay_authorized": False,
        "detector_called": False,
        "odi_computed": False,
        "weak_direction_computed": False,
        "development_run": False,
        "holdout_run": False,
        "future_test_run": False,
        "commit_created": False,
        "push_performed": False,
        "STAGE2_GATE": "FAIL",
        "TRANSITION": "PIVOT",
        "STAGE3_START_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE": "NOT_PROVEN",
        "HARMFUL_BIAS_DETECTABILITY_STATUS":
            "NOT_EVALUATED_DAY6_EXPERIMENT_A_INPUT_MAP_HASHES",
        **gates,
        "EXPERIMENT_A_EXECUTION_PASS": execution_pass,
        "EXPERIMENT_A_STAGE_LOCALIZATION_PASS": localized,
        "EXPERIMENT_A_PASS": localized,
        "DAY7_AUTHORIZED": False,
        "EXPERIMENT_B_AUTHORIZED": False,
        "EXPERIMENT_C_AUTHORIZED": False,
    }
    write_json(args.manifest, manifest)

    def answer(status: str) -> str:
        return identities.get(status, "NOT_AVAILABLE")

    report = f"""# Day 6 Experiment A Input and Map Stage Hash Report

Result identity: `INTERNAL_ENGINEERING_DIVERGENCE_STAGE_DIAGNOSTICS_ONLY`.

1. Both restricted replays complete: `{all(run_passes)}`.
2. Branch reproduced in the diagnostic window: `{classification["branch_reproduced"]}`.
3. First divergence scan: `{classification["first_divergence_scan"]}`.
4. Raw LiDAR identity: `{answer("raw_lidar")}`.
5. IMU bundle identity: `{answer("imu_bundle")}`.
6. Undistorted cloud identity: `{answer("undistorted_cloud")}`.
7. Prior state/covariance identity: `{answer("prior_state")}` / `{answer("prior_covariance")}`.
8. Map content before measurement: `{answer("map_content_before")}`.
9. Map traversal before measurement: `{answer("map_traversal_before")}`.
10. Correspondence/J/h first separation is represented by first stage `{classification["first_divergence_stage"]}` at scan `{classification["first_divergence_scan"]}`; aggregate status is `{answer("correspondence")}`.
11. Post-update state identity: `{answer("post_update_state")}`.
12. Insertion batch identity: `{answer("insertion_batch")}`.
13. Map content after insertion: `{answer("map_content_after")}`.
14. Map traversal after insertion: `{answer("map_traversal_after")}`.
15. Classification: `{stage_class}`.
16. Checksum limitation: equal values mean only `MATCHED_BY_CANONICAL_CHECKSUM`; finite FNV-1a checksums may collide.
17. The evidence does not identify a particular point; full payloads, maps, neighbors, planes, and accepted-index arrays were not exported.
18. OpenMP data race proven: `false`.
19. ikd-tree root cause proven: `false`.
20. Day 7 recommended: `{classification["day7_recommended"]}`; scope: `{classification["day7_recommended_scope"]}`.
21. Day 7 remains unauthorized because this bounded engineering checksum result requires a separate GPT audit.

`EXPERIMENT_A_EXECUTION_PASS={str(execution_pass).lower()}`

`EXPERIMENT_A_STAGE_LOCALIZATION_PASS={str(localized).lower()}`

`EXPERIMENT_A_PASS={str(localized).lower()}`

Fixed state remains `STAGE2_GATE=FAIL`, `TRANSITION=PIVOT`,
`CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`, and
`HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY6_EXPERIMENT_A_INPUT_MAP_HASHES`.
The production detector, ODI, weak-direction logic, GT, Development, Holdout,
and Future Test were not run.
"""
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")

    args.artifact_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(args.manifest, args.artifact_dir / args.manifest.name)
    shutil.copy2(args.report, args.artifact_dir / args.report.name)
    for name in (
        "experiment_a_pairwise_stage_hash_comparison.csv",
        "experiment_a_first_divergence.json",
        "experiment_a_stage_classification.json",
        "experiment_a_identity_summary.json",
    ):
        shutil.copy2(args.comparison_dir / name, args.artifact_dir / name)
    for index, (run_id, run) in enumerate(zip(sub_ids, runs), start=1):
        write_json(
            args.artifact_dir / f"run_{index}_summary.json",
            {"run_id": run_id, **run},
        )
    print(json.dumps(
        {
            "EXPERIMENT_A_EXECUTION_PASS": execution_pass,
            "EXPERIMENT_A_STAGE_LOCALIZATION_PASS": localized,
            "EXPERIMENT_A_PASS": localized,
            "stage_classification": stage_class,
        },
        sort_keys=True,
    ))
    return 0 if execution_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
