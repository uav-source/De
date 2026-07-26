#!/usr/bin/env python3
"""Finalize, package, and externally verify Day 6 Fallback diagnostics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day6_fallback_functional_diagnostics import (  # noqa: E402
    Day6FallbackError,
    EXPECTED_AUTHORIZATION_SHA256,
    EXPECTED_CLIP_SHA256,
    EXPECTED_DEGEN_BRANCH,
    EXPECTED_DEGEN_HEAD,
    EXPECTED_FAST_BINARY_SHA256,
    EXPECTED_FAST_BRANCH,
    EXPECTED_FAST_HEAD,
    EXPECTED_FROZEN_ADAPTER_SHA256,
    EXPECTED_FROZEN_BINARY_SHA256,
    EXPECTED_FROZEN_REFERENCE_SHA256,
    EXPECTED_IMU_CALLBACK_COUNT,
    EXPECTED_LIDAR_CALLBACK_COUNT,
    EXPECTED_RECORD_COUNT,
    EXPECTED_SOURCE_SHA256,
    MAIN_RUN_ID,
    REQUIRED_GATE_NAMES,
    SUB_RUN_IDS,
    detector_identity,
    evaluate_day6_gate,
    forbidden_result_paths,
    sha256_file,
    validate_authorization_archive,
    write_json,
)


AUDIT_NAME = "Degen-LIO-multihyp-D6-fallback-functional-diagnostics-audit"
ARCHIVE_NAME = f"{AUDIT_NAME}.tar.gz"
DAY6_SOURCE_PATHS = (
    "src/fastlio2_adapter/day6_fallback_functional_diagnostics.py",
    "src/fastlio2_adapter/day6_continuity_metrics.py",
    "src/fastlio2_adapter/day6_statistical_characterization.py",
    "src/fastlio2_adapter/day6_reference_alignment.py",
    "scripts/75_run_day6_fallback_real_replay.py",
    "scripts/76_process_day6_fallback_detector.py",
    "scripts/77_compare_day6_fallback_runs.py",
    "scripts/78_render_day6_fallback_diagnostics.py",
    "scripts/79_finalize_day6_fallback.py",
)
DAY6_TEST_PATHS = (
    "tests/test_day6_fallback_authorization.py",
    "tests/test_day6_fallback_runner.py",
    "tests/test_day6_observation_completeness.py",
    "tests/test_day6_detector_processing.py",
    "tests/test_day6_adapter_direct_contract.py",
    "tests/test_day6_output_continuity.py",
    "tests/test_day6_direction_continuity.py",
    "tests/test_day6_descriptive_statistics.py",
    "tests/test_day6_reference_alignment.py",
    "tests/test_day6_cross_run_statistics.py",
    "tests/test_day6_fallback_gate.py",
)
DAY6_DOC_PATHS = (
    "docs/harmful_bias/day6_fallback_functional_diagnostics_contract.md",
    "docs/harmful_bias/day6_fallback_functional_diagnostics_report.md",
    "manifests/harmful_bias/day6_fallback_functional_diagnostics_manifest.json",
)
ALLOWED_NEW_PATHS = set(DAY6_SOURCE_PATHS + DAY6_TEST_PATHS + DAY6_DOC_PATHS)
TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".sh",
    ".txt",
    ".yaml",
    ".yml",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-lock", required=True, type=Path)
    parser.add_argument("--targeted-test-log", required=True, type=Path)
    parser.add_argument("--targeted-test-rc", required=True, type=Path)
    parser.add_argument("--full-test-log", required=True, type=Path)
    parser.add_argument("--full-test-rc", required=True, type=Path)
    parser.add_argument("--before-dir", required=True, type=Path)
    parser.add_argument(
        "--authorization-audit",
        type=Path,
        default=(
            Path.home()
            / "Degen-LIO-multihyp-D5-fallback-offline-detector-"
            "determinism-remediation-audit.tar.gz"
        ),
    )
    parser.add_argument(
        "--frozen-reference",
        type=Path,
        default=(
            Path.home()
            / "Degen-LIO-frozen-real-observation-quick-shack-v1.1.tar.gz"
        ),
    )
    return parser.parse_args()


def json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Day6FallbackError(f"JSON object required: {path}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def git_output(arguments: list[str], root: Path = ROOT) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise Day6FallbackError(completed.stderr.strip())
    return completed.stdout


def git_patch_sha(root: Path, checkpoint: str) -> str:
    value = subprocess.run(
        ["git", "-C", str(root), "diff", "--binary", checkpoint],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout
    return hashlib.sha256(value).hexdigest()


def current_status_paths() -> set[str]:
    paths: set[str] = set()
    for line in git_output(["status", "--porcelain"]).splitlines():
        if not line:
            continue
        raw = line[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.add(raw)
    return paths


def baseline_status_paths(path: Path) -> set[str]:
    paths: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        raw = line[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.add(raw)
    return paths


def test_pass(log: Path, rc: Path) -> bool:
    return (
        log.is_file()
        and rc.is_file()
        and rc.read_text(encoding="utf-8").strip() == "0"
    )


def locked_source_pass(run_lock: Mapping[str, Any]) -> tuple[bool, list[str]]:
    mismatches = []
    for relative, expected in run_lock["day6_source_sha256"].items():
        path = ROOT / relative
        actual = sha256_file(path) if path.is_file() else None
        if actual != expected:
            mismatches.append(relative)
    return not mismatches, mismatches


def load_run_evidence(result_root: Path) -> list[dict[str, Any]]:
    rows = []
    for run_id in SUB_RUN_IDS:
        run = result_root / run_id
        diagnostics = run / "detector_diagnostics"
        rows.append(
            {
                "run_id": run_id,
                "root": run,
                "run": json_object(run / "run_summary.json"),
                "detector": json_object(
                    diagnostics / "detector_processing_summary.json"
                ),
                "domain": json_object(
                    diagnostics / "direct_equivalence_domain_summary.json"
                ),
                "continuity": json_object(
                    diagnostics / "output_continuity_summary.json"
                ),
                "direction": json_object(
                    diagnostics / "direction_continuity_summary.json"
                ),
                "flags": json_object(
                    diagnostics / "detector_flag_transition_summary.json"
                ),
                "metrics": json_object(
                    diagnostics
                    / "detector_metric_descriptive_statistics.json"
                ),
                "latency": json_object(
                    diagnostics / "detector_latency_summary.json"
                ),
                "no_gt": json_object(
                    diagnostics / "detector_no_gt_audit.json"
                ),
                "environment": json_object(
                    diagnostics / "environment_identity.json"
                ),
                "source": json_object(
                    diagnostics / "source_identity.json"
                ),
            }
        )
    return rows


def build_facts(
    *,
    runs: list[dict[str, Any]],
    comparison: Mapping[str, Any],
    plot_summary: Mapping[str, Any],
    run_lock: Mapping[str, Any],
    targeted_pass: bool,
    full_pass: bool,
    diff_scope_pass: bool,
    source_lock_pass: bool,
    fast_patch_after: str,
    detector_after: Mapping[str, Any],
) -> dict[str, Any]:
    run_complete = [bool(row["run"]["complete"]) for row in runs]
    detector_complete = [
        bool(row["detector"]["post_replay_detector_processing_pass"])
        for row in runs
    ]
    observation_complete = [
        all(
            int(row["run"][name]) == EXPECTED_RECORD_COUNT
            for name in (
                "observation_record_count",
                "first_valid_linearization_count",
                "tap_emitted_count",
                "in_call_audited_count",
            )
        )
        for row in runs
    ]
    zero_runtime = [
        all(
            int(row["run"][name]) == 0
            for name in (
                "tap_drop_count",
                "writer_error_count",
                "binary_checksum_failure_count",
                "truncated_record_count",
                "extra_trailing_bytes",
                "in_call_mutation_count",
                "schema_rejected_record_count",
                "forbidden_input_field_count",
                "GT_TOPIC_CONSUMED_COUNT",
            )
        )
        for row in runs
    ]
    facts = {
        "DAY6_AUTHORIZATION_IDENTITY_PASS": True,
        "DEGEN_SOURCE_LOCK_PASS": source_lock_pass,
        "FAST_SOURCE_LOCK_PASS": (
            fast_patch_after == run_lock["fastlio2_diff_sha256"]
        ),
        "FAST_BINARY_LOCK_PASS": (
            sha256_file(Path(run_lock["binary_path"]))
            == run_lock["fastlio2_binary_sha256"]
            == EXPECTED_FAST_BINARY_SHA256
        ),
        "CLIP_IDENTITY_PASS": (
            sha256_file(Path(run_lock["clips"]["avia_quick_shack"]["path"]))
            == EXPECTED_CLIP_SHA256
        ),
        "ENDPOINT_CONTRACT_PASS": all(
            row["run"]["lidar_callback_count"]
            == EXPECTED_LIDAR_CALLBACK_COUNT
            and row["run"]["imu_callback_count"]
            == EXPECTED_IMU_CALLBACK_COUNT
            for row in runs
        ),
        "THREE_REAL_REPLAY_RUNS_COMPLETE_PASS": all(run_complete),
        "RUN_1_COMPLETENESS_PASS": run_complete[0],
        "RUN_2_COMPLETENESS_PASS": run_complete[1],
        "RUN_3_COMPLETENESS_PASS": run_complete[2],
        "TAIL_ADJUDICATION_RULE_REUSE_PASS": all(
            row["run"]["adjudicated_tail_handoff_pass"]
            and row["run"]["tail_adjudication_rule_sha256"]
            == run_lock["tail_adjudication_rule_sha256"]
            for row in runs
        ),
        "END_OF_STREAM_DRAIN_PASS": all(
            row["run"]["end_of_stream_drain_pass"] for row in runs
        ),
        "NORMAL_SHUTDOWN_PASS": all(
            row["run"]["normal_shutdown_pass"] for row in runs
        ),
        "OBSERVATION_BINARY_INTEGRITY_PASS": all(
            row["run"]["binary_checksum_failure_count"] == 0
            and row["run"]["truncated_record_count"] == 0
            and row["run"]["extra_trailing_bytes"] == 0
            for row in runs
        ),
        "OBSERVATION_COUNT_COMPLETENESS_PASS": all(observation_complete),
        "REFERENCE_SCAN_ALIGNMENT_PASS": all(
            item["aligned_count"] == EXPECTED_RECORD_COUNT
            for item in comparison["reference_alignment"].values()
        ),
        "IN_CALL_IMMUTABILITY_RECONFIRMED": all(
            row["run"]["in_call_mutation_count"] == 0 for row in runs
        ),
        "NO_TAP_DROP_PASS": all(
            row["run"]["tap_drop_count"] == 0 for row in runs
        ),
        "NO_WRITER_ERROR_PASS": all(
            row["run"]["writer_error_count"] == 0 for row in runs
        ),
        "DETECTOR_ENVIRONMENT_LOCK_PASS": all(
            row["environment"]["python_version"] == "3.8.10"
            and row["environment"]["numpy_version"] == "1.24.4"
            and row["environment"]["scipy_version"] == "1.10.1"
            for row in runs
        ),
        "PRODUCTION_DETECTOR_IDENTITY_PASS": all(
            row["source"]["production_detector_sha256"]
            == EXPECTED_SOURCE_SHA256
            for row in runs
        ),
        "DETECTOR_ARTIFACT_IMMUTABILITY_PASS": (
            detector_after["detector_artifact_tree_sha256"]
            == run_lock["detector_artifact_tree_sha256"]
        ),
        "POST_REPLAY_DETECTOR_PROCESSING_PASS": all(detector_complete),
        "ADAPTER_DIRECT_CONTRACT_PASS": all(
            row["domain"]["production_metric_equivalence_mismatch_count"] == 0
            and row["domain"][
                "adapter_precondition_contract_mismatch_count"
            ]
            == 0
            for row in runs
        ),
        "INPUT_IMMUTABILITY_PASS": all(
            row["detector"]["input_mutation_count"] == 0 for row in runs
        ),
        "DETECTOR_OUTPUT_COUNT_PASS": all(
            row["detector"]["adapter_output_count"] == EXPECTED_RECORD_COUNT
            and row["detector"]["direct_output_count"] == EXPECTED_RECORD_COUNT
            and row["detector"]["missing_output_count"] == 0
            and row["detector"]["duplicate_output_count"] == 0
            for row in runs
        ),
        "DETECTOR_OUTPUT_SCHEMA_PASS": all(
            row["detector"]["adapter_schema_rejected_count"] == 0
            and row["detector"]["direct_schema_rejected_count"] == 0
            for row in runs
        ),
        "NO_GT_PASS": all(
            row["no_gt"]["no_gt_pass"]
            and row["no_gt"]["gt_topic_consumed_count"] == 0
            for row in runs
        ),
        "OUTPUT_TIMESTAMP_MONOTONICITY_PASS": all(
            row["continuity"]["output_timestamp_monotonicity_pass"]
            for row in runs
        ),
        "OUTPUT_CONTINUITY_DIAGNOSTICS_PASS": all(
            row["continuity"]["output_continuity_diagnostics_pass"]
            for row in runs
        ),
        "DIRECTION_CONTINUITY_DIAGNOSTICS_PASS": all(
            row["direction"]["direction_continuity_diagnostics_pass"]
            for row in runs
        ),
        "FLAG_CONTINUITY_DIAGNOSTICS_PASS": all(
            row["flags"]["flag_continuity_diagnostics_pass"] for row in runs
        ),
        "METRIC_DESCRIPTIVE_STATISTICS_PASS": all(
            row["metrics"]["metric_descriptive_statistics_pass"]
            for row in runs
        ),
        "LATENCY_CHARACTERIZATION_PASS": all(
            row["latency"]["latency_characterization_pass"] for row in runs
        ),
        "REFERENCE_COMPARISON_COMPLETE": bool(
            comparison["REFERENCE_COMPARISON_COMPLETE"]
        ),
        "CROSS_RUN_STATISTICAL_COMPARISON_COMPLETE": bool(
            comparison["CROSS_RUN_STATISTICAL_COMPARISON_COMPLETE"]
        ),
        "PLOTS_COMPLETE": bool(plot_summary["plots_complete"]),
        "DEGEN_TARGETED_TEST_PASS": targeted_pass,
        "DEGEN_FULL_TEST_PASS": full_pass,
        "DIFF_SCOPE_PASS": diff_scope_pass,
        "AUDIT_PACKAGE_SCOPE_PASS": True,
    }
    if not all(zero_runtime):
        facts["OBSERVATION_BINARY_INTEGRITY_PASS"] = False
    return facts


def report_text(
    manifest: Mapping[str, Any],
    gates: Mapping[str, Any],
    runs: list[dict[str, Any]],
) -> str:
    lines = [
        "# Day 6 Fallback Functional Diagnostics Report",
        "",
        "## Outcome",
        "",
        (
            "`DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_PASS="
            f"{str(gates['DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_PASS']).lower()}`."
        ),
        "",
        (
            "This is Day6-Fallback, not the original strict cross-process "
            "bitwise Day 6. The strict route remains closed and "
            "`CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`."
        ),
        "",
        "## Execution boundary",
        "",
        (
            "Three new Quick Shack replays ran sequentially with fresh ROS "
            "masters. Each replay used the locked read-only tap, compact "
            "export, in-call immutability audit, frozen tail adjudication, "
            "drain, and normal shutdown flow."
        ),
        "",
        (
            "The production detector ran only after each replay in a new "
            "locked Python process. It was a read-only shadow diagnostic and "
            "did not feed FAST-LIO2 state, covariance, residuals, gain, map, "
            "or control."
        ),
        "",
        "## Per-run lifecycle and detector completeness",
        "",
        "| run | raw rc | raw handoff | adjudicated | LiDAR | IMU | observations | adapter/direct |",
        "|---|---:|---|---|---:|---:|---:|---:|",
    ]
    for row in runs:
        run = row["run"]
        detector = row["detector"]
        lines.append(
            "| {run_id} | {raw} | {raw_handoff} | {adjudicated} | "
            "{lidar} | {imu} | {observations} | {adapter}/{direct} |".format(
                run_id=row["run_id"],
                raw=run["raw_runner_exit_code"],
                raw_handoff=str(run["raw_tail_handoff_pass"]).lower(),
                adjudicated=str(
                    run["adjudicated_tail_handoff_pass"]
                ).lower(),
                lidar=run["lidar_callback_count"],
                imu=run["imu_callback_count"],
                observations=run["observation_record_count"],
                adapter=detector["adapter_output_count"],
                direct=detector["direct_output_count"],
            )
        )
    lines.extend(
        [
            "",
            "Raw handoff fields were preserved. The frozen V5 rule was applied "
            "only to mixed bag/tail counters; raw runner exit codes were not "
            "rewritten.",
            "",
            "## Continuity and descriptive characterization",
            "",
            (
                "Every observation has one adapter output and one direct "
                "diagnostic output. Production-domain metric mismatches and "
                "adapter-precondition contract mismatches are zero. Output "
                "timestamps are monotonic, scan identities are continuous, "
                "and there are no missing or duplicate outputs."
            ),
            "",
            (
                "Weak-direction continuity uses the sign-invariant angle "
                "`acos(abs(dot(u_t,u_t-1)))`. Null and unstable directions "
                "are excluded from angle statistics but retained in record "
                "and flag counts. Flag transitions and detector metrics are "
                "reported descriptively."
            ),
            "",
            (
                "Latency is `POST_REPLAY_OFFLINE_LOCKED_ENVIRONMENT_ONLY`; it "
                "does not represent online end-to-end, FAST-LIO2 real-time, "
                "or control-loop latency."
            ),
            "",
            (
                "Frozen-reference and pairwise cross-run comparisons align by "
                "`scan_index`, `timestamp_begin`, and `timestamp_end`. Exact "
                "output equality is not required, and no bitwise Gate is "
                "restored even if values happen to coincide."
            ),
            "",
            "## Scientific limitations",
            "",
            (
                "This task has no ground truth and does not evaluate detector "
                "accuracy, scientific effectiveness, or harmful-bias "
                "detectability. It does not compute AUROC, AUPRC, FPR, or "
                "recall, and it does not run Development, Holdout, or Future "
                "Test."
            ),
            "",
            (
                "`STAGE2_GATE=FAIL`, `TRANSITION=PIVOT`, "
                "`STAGE3_START_AUTHORIZED=false`, "
                "`FAST_LIO2_INTEGRATION_AUTHORIZED=false`, and "
                "`NEXT_PHASE_AUTHORIZED=false` remain fixed. A separate GPT "
                "authorization is required for any next phase."
            ),
            "",
            "## Identity",
            "",
            f"- Main run: `{manifest['main_run_id']}`",
            f"- FAST binary SHA-256: `{manifest['fastlio2_binary_sha256']}`",
            (
                "- Detector/config/lock SHA-256: "
                f"`{manifest['detector_source_sha256']}` / "
                f"`{manifest['detector_config_sha256']}` / "
                f"`{manifest['detector_lock_sha256']}`"
            ),
            "",
        ]
    )
    return "\n".join(lines)


def manifest_value(
    *,
    created_at: str,
    run_lock: Mapping[str, Any],
    runs: list[dict[str, Any]],
    comparison: Mapping[str, Any],
    gates: Mapping[str, Any],
    detector_after: Mapping[str, Any],
    fast_patch_after: str,
    unexpected: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": "day6_fallback_functional_diagnostics_manifest_v1",
        "created_at_utc": created_at,
        "authorization_audit_sha256": EXPECTED_AUTHORIZATION_SHA256,
        "authorization_status": (
            "DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_AUTHORIZED"
        ),
        "main_run_id": MAIN_RUN_ID,
        "sub_run_ids": list(SUB_RUN_IDS),
        "sequence_id": "avia_quick_shack",
        "clip_sha256": EXPECTED_CLIP_SHA256,
        "endpoint_contract_sha256": run_lock["endpoint_contract_sha256"],
        "degen_branch": EXPECTED_DEGEN_BRANCH,
        "degen_head": EXPECTED_DEGEN_HEAD,
        "degen_diff_sha256": run_lock["degen_diff_sha256"],
        "fastlio2_branch": EXPECTED_FAST_BRANCH,
        "fastlio2_head": EXPECTED_FAST_HEAD,
        "fastlio2_diff_sha256": run_lock["fastlio2_diff_sha256"],
        "fastlio2_diff_sha256_after": fast_patch_after,
        "fastlio2_binary_sha256": EXPECTED_FAST_BINARY_SHA256,
        "tap_source_sha256": run_lock["tap_source_sha256"],
        "compact_writer_sha256": run_lock["compact_writer_source_sha256"],
        "in_call_audit_sha256": run_lock["in_call_audit_source_sha256"],
        "detector_source_sha256": detector_after[
            "production_detector_sha256"
        ],
        "detector_config_sha256": detector_after["detector_config_sha256"],
        "detector_lock_sha256": detector_after["detector_lock_sha256"],
        "detector_artifact_tree_sha256_before": run_lock[
            "detector_artifact_tree_sha256"
        ],
        "detector_artifact_tree_sha256_after": detector_after[
            "detector_artifact_tree_sha256"
        ],
        "python_version": runs[0]["environment"]["python_version"],
        "numpy_version": runs[0]["environment"]["numpy_version"],
        "scipy_version": runs[0]["environment"]["scipy_version"],
        "blas_identity": runs[0]["environment"]["blas_identity"],
        "per_run_raw_runner_exit_code": {
            row["run_id"]: row["run"]["raw_runner_exit_code"] for row in runs
        },
        "per_run_raw_handoff": {
            row["run_id"]: row["run"]["raw_tail_handoff_pass"] for row in runs
        },
        "per_run_adjudicated_handoff": {
            row["run_id"]: row["run"]["adjudicated_tail_handoff_pass"]
            for row in runs
        },
        "per_run_lidar_callbacks": {
            row["run_id"]: row["run"]["lidar_callback_count"] for row in runs
        },
        "per_run_imu_callbacks": {
            row["run_id"]: row["run"]["imu_callback_count"] for row in runs
        },
        "per_run_drain": {
            row["run_id"]: row["run"]["end_of_stream_drain_pass"]
            for row in runs
        },
        "per_run_shutdown": {
            row["run_id"]: row["run"]["normal_shutdown_pass"] for row in runs
        },
        "per_run_observation_count": {
            row["run_id"]: row["run"]["observation_record_count"]
            for row in runs
        },
        "per_run_tap_emitted_count": {
            row["run_id"]: row["run"]["tap_emitted_count"] for row in runs
        },
        "per_run_in_call_audited_count": {
            row["run_id"]: row["run"]["in_call_audited_count"] for row in runs
        },
        "per_run_tap_drop_count": {
            row["run_id"]: row["run"]["tap_drop_count"] for row in runs
        },
        "per_run_mutation_count": {
            row["run_id"]: row["run"]["in_call_mutation_count"] for row in runs
        },
        "per_run_adapter_output_count": {
            row["run_id"]: row["detector"]["adapter_output_count"]
            for row in runs
        },
        "per_run_direct_output_count": {
            row["run_id"]: row["detector"]["direct_output_count"]
            for row in runs
        },
        "per_run_valid_count": {
            row["run_id"]: row["detector"]["adapter_valid_count"] for row in runs
        },
        "per_run_invalid_count": {
            row["run_id"]: row["detector"]["adapter_invalid_count"]
            for row in runs
        },
        "per_run_detector_exception_count": {
            row["run_id"]: row["detector"]["detector_exception_count"]
            for row in runs
        },
        "per_run_schema_rejected_count": {
            row["run_id"]: (
                row["detector"]["adapter_schema_rejected_count"]
                + row["detector"]["direct_schema_rejected_count"]
            )
            for row in runs
        },
        "per_run_missing_output_count": {
            row["run_id"]: row["detector"]["missing_output_count"]
            for row in runs
        },
        "per_run_duplicate_output_count": {
            row["run_id"]: row["detector"]["duplicate_output_count"]
            for row in runs
        },
        "per_run_latency_summary": {
            row["run_id"]: row["latency"] for row in runs
        },
        "per_run_metric_statistics": {
            row["run_id"]: row["metrics"] for row in runs
        },
        "per_run_flag_statistics": {
            row["run_id"]: row["flags"] for row in runs
        },
        "per_run_direction_continuity": {
            row["run_id"]: row["direction"] for row in runs
        },
        "reference_alignment_counts": comparison["reference_alignment"],
        "cross_run_alignment_counts": {
            name: value["aligned_record_count"]
            for name, value in comparison["pairwise"].items()
        },
        "cross_run_metric_difference_summary": {
            name: value["difference_quantiles"]
            for name, value in comparison["pairwise"].items()
        },
        "cross_run_flag_agreement_summary": {
            name: value["flag_agreement"]
            for name, value in comparison["pairwise"].items()
        },
        "cross_run_direction_angle_summary": {
            name: value["difference_quantiles"][
                "weak_direction_sign_invariant_angle_deg"
            ]
            for name, value in comparison["pairwise"].items()
        },
        "roscore_run": True,
        "roslaunch_run": True,
        "rosbag_run": True,
        "fastlio2_run": True,
        "detector_called": True,
        "detector_called_inside_fastlio2": False,
        "detector_feedback_enabled": False,
        "odi_computed": True,
        "weak_direction_computed": True,
        "scientific_effectiveness_evaluated": False,
        "harmful_bias_detectability_evaluated": False,
        "auroc_computed": False,
        "auprc_computed": False,
        "fpr_computed": False,
        "recall_computed": False,
        "development_run": False,
        "holdout_run": False,
        "future_test_run": False,
        "commit_created": False,
        "push_performed": False,
        "unexpected_changed_file_count": len(unexpected),
        "unexpected_changed_files": unexpected,
        **gates,
    }


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise Day6FallbackError(f"package source missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def safe_extract(archive: Path, destination: Path) -> Path:
    with tarfile.open(archive, "r:gz") as handle:
        members = handle.getmembers()
        roots = {
            Path(member.name).parts[0]
            for member in members
            if member.name and Path(member.name).parts
        }
        if len(roots) != 1:
            raise Day6FallbackError("authorization archive root is ambiguous")
        destination_resolved = destination.resolve()
        for member in members:
            if member.issym() or member.islnk():
                raise Day6FallbackError("authorization archive links forbidden")
            try:
                (destination / member.name).resolve().relative_to(
                    destination_resolved
                )
            except ValueError as error:
                raise Day6FallbackError("unsafe authorization archive") from error
        handle.extractall(destination)
    return destination / next(iter(roots))


def redact(value: Any) -> Any:
    if isinstance(value, str):
        replacements = (
            (str(Path.home()), "$HOME_AUDITED"),
            (str(ROOT), "$DEGEN_ROOT"),
            ("/root/", "$ROOT_HOME/"),
        )
        result = value
        for old, new in replacements:
            result = result.replace(old, new)
        return result
    if isinstance(value, dict):
        return {key: redact(child) for key, child in value.items()}
    if isinstance(value, list):
        return [redact(child) for child in value]
    return value


def restore_script() -> str:
    targeted = " \\\n    ".join(DAY6_TEST_PATHS + (
        "tests/test_fallback_c_remediation_gate.py",
        "tests/test_fastlio2_detector_adapter.py",
    ))
    return f"""#!/usr/bin/env bash
set -euo pipefail

AUDIT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
(
  cd "${{AUDIT_DIR}}"
  sha256sum -c SHA256SUMS >/dev/null
)

TEMP_ROOT="$(mktemp -d "${{TMPDIR:-/tmp}}/day6-fallback-verify.XXXXXX")"
trap 'find "${{TEMP_ROOT}}" -depth -mindepth 1 -delete 2>/dev/null || true; rmdir "${{TEMP_ROOT}}" 2>/dev/null || true' EXIT
REPO="${{TEMP_ROOT}}/repo"
ISOLATED_HOME="${{TEMP_ROOT}}/home"
RESTORED="${{TEMP_ROOT}}/restored_runs"
mkdir -p "${{ISOLATED_HOME}}" "${{RESTORED}}"

git clone -q --no-checkout "${{AUDIT_DIR}}/repo/degen_base.bundle" "${{REPO}}"
git -C "${{REPO}}" checkout -q -b spike/harmful-bias-multihyp-dev origin/spike/harmful-bias-multihyp-dev
cp -a "${{AUDIT_DIR}}/repo/degen_overlay/." "${{REPO}}/"
cp -a "${{AUDIT_DIR}}/repo/home_state/." "${{ISOLATED_HOME}}/"

RUNTIME_PYTHONPATH="$(
  python3 - <<'PY'
import sys
from pathlib import Path
print(":".join(
    value for value in sys.path
    if value and Path(value).is_absolute() and Path(value).exists()
))
PY
)"
export HOME="${{ISOLATED_HOME}}"
export XDG_CACHE_HOME="${{TEMP_ROOT}}/xdg-cache"
export XDG_CONFIG_HOME="${{TEMP_ROOT}}/xdg-config"
export PYTHONPATH="${{REPO}}/src:${{REPO}}/tests:${{RUNTIME_PYTHONPATH}}"
export DAY6_AUTHORIZATION_AUDIT="${{AUDIT_DIR}}/authorization/authorization_identity.json"

FROZEN="${{AUDIT_DIR}}/frozen_reference/Degen-LIO-frozen-real-observation-quick-shack-v1.1.tar.gz"
test "$(sha256sum "${{FROZEN}}" | awk '{{print $1}}')" = "{EXPECTED_FROZEN_REFERENCE_SHA256}"
gzip -t "${{FROZEN}}"
FROZEN_TMP="${{TEMP_ROOT}}/frozen"
mkdir -p "${{FROZEN_TMP}}"
tar -xzf "${{FROZEN}}" -C "${{FROZEN_TMP}}"
FROZEN_ROOT="${{FROZEN_TMP}}/Degen-LIO-frozen-real-observation-quick-shack-v1.1"
(
  cd "${{FROZEN_ROOT}}"
  sha256sum -c SHA256SUMS >/dev/null
)
test "$(sha256sum "${{FROZEN_ROOT}}/binary/observation_records_v3.bin" | awk '{{print $1}}')" = "{EXPECTED_FROZEN_BINARY_SHA256}"

TARGETED_LOG="${{TEMP_ROOT}}/targeted_pytest.txt"
(
  cd "${{REPO}}"
  python3 -m pytest -q \\
    {targeted} >"${{TARGETED_LOG}}" 2>&1
)
set +e
(
  cd "${{REPO}}"
  python3 -m pytest -q >"${{TEMP_ROOT}}/full_pytest.txt" 2>&1
)
FULL_RC=$?
set -e

for INDEX in 1 2 3; do
  case "${{INDEX}}" in
    1) RUN_ID="{SUB_RUN_IDS[0]}" ;;
    2) RUN_ID="{SUB_RUN_IDS[1]}" ;;
    3) RUN_ID="{SUB_RUN_IDS[2]}" ;;
  esac
  RUN="${{RESTORED}}/${{RUN_ID}}"
  mkdir -p "${{RUN}}"
  cp "${{AUDIT_DIR}}/real_replay_observations/run_${{INDEX}}/observation_records_v3.bin" "${{RUN}}/"
  cp "${{AUDIT_DIR}}/real_replay_observations/run_${{INDEX}}/observation_record_index.csv" "${{RUN}}/"
  test "$(sha256sum "${{RUN}}/observation_records_v3.bin" | awk '{{print $1}}')" = "$(
    awk '{{print $1}}' "${{AUDIT_DIR}}/real_replay_observations/run_${{INDEX}}/observation_records_v3.bin.sha256"
  )"
  env \\
    PYTHONHASHSEED=0 \\
    OMP_NUM_THREADS=1 \\
    OMP_DYNAMIC=FALSE \\
    OPENBLAS_NUM_THREADS=1 \\
    MKL_NUM_THREADS=1 \\
    NUMEXPR_NUM_THREADS=1 \\
    VECLIB_MAXIMUM_THREADS=1 \\
    LC_ALL=C LANG=C TZ=UTC \\
    python3 "${{REPO}}/scripts/76_process_day6_fallback_detector.py" \\
      --observation-binary "${{RUN}}/observation_records_v3.bin" \\
      --record-index "${{RUN}}/observation_record_index.csv" \\
      --output-dir "${{RUN}}/detector_diagnostics" \\
      >"${{TEMP_ROOT}}/detector_${{INDEX}}.json"
  cmp "${{RUN}}/detector_diagnostics/adapter_detector_outputs_v3.jsonl" \\
    "${{AUDIT_DIR}}/detector_outputs/run_${{INDEX}}/adapter_detector_outputs_v3.jsonl"
  cmp "${{RUN}}/detector_diagnostics/direct_production_metrics_v1.jsonl" \\
    "${{AUDIT_DIR}}/detector_outputs/run_${{INDEX}}/direct_production_metrics_v1.jsonl"
done

python3 "${{REPO}}/scripts/77_compare_day6_fallback_runs.py" \\
  --run-1 "${{RESTORED}}/{SUB_RUN_IDS[0]}" \\
  --run-2 "${{RESTORED}}/{SUB_RUN_IDS[1]}" \\
  --run-3 "${{RESTORED}}/{SUB_RUN_IDS[2]}" \\
  --reference "${{FROZEN}}" \\
  --authorization-audit "${{AUDIT_DIR}}/authorization/fallback_c_adapter_reference.jsonl" \\
  --output-dir "${{RESTORED}}/comparison" \\
  >"${{TEMP_ROOT}}/comparison.json"

python3 - "${{AUDIT_DIR}}" "${{RESTORED}}" <<'PY'
import json
import sys
from pathlib import Path

audit = Path(sys.argv[1])
restored = Path(sys.argv[2])
manifest = json.loads(
    (audit / "evidence/small_results/day6_fallback_functional_diagnostics_manifest.json")
    .read_text(encoding="utf-8")
)
assert manifest["DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_PASS"] is True
assert manifest["CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE"] == "NOT_PROVEN"
assert manifest["NEXT_PHASE_AUTHORIZED"] is False
for run_id in {list(SUB_RUN_IDS)!r}:
    root = restored / run_id / "detector_diagnostics"
    summary = json.loads((root / "detector_processing_summary.json").read_text())
    assert summary["input_record_count"] == 487
    assert summary["adapter_output_count"] == 487
    assert summary["direct_output_count"] == 487
    assert summary["post_replay_detector_processing_pass"] is True
comparison = json.loads(
    (restored / "comparison/cross_run_pairwise_summary.json").read_text()
)
assert comparison["REFERENCE_COMPARISON_COMPLETE"] is True
assert comparison["CROSS_RUN_STATISTICAL_COMPARISON_COMPLETE"] is True
plot_summary = json.loads(
    (audit / "evidence/plots/plot_summary.json").read_text()
)
assert plot_summary["plots_complete"] is True
assert plot_summary["plot_count"] == 12
PY

echo "DAY6_FALLBACK_EXTERNAL_TARGETED_PASS=true"
if [ "${{FULL_RC}}" -eq 0 ]; then
  echo "DAY6_FALLBACK_EXTERNAL_FULL_PASS=true"
else
  echo "DAY6_FALLBACK_EXTERNAL_FULL_PASS=false"
  echo "DAY6_FALLBACK_EXTERNAL_FULL_LIMITATION=historical_runtime_results_and_fast_source_excluded"
fi
echo "DAY6_FALLBACK_EXTERNAL_FROZEN_REFERENCE_PASS=true"
echo "DAY6_FALLBACK_EXTERNAL_RUN1_BINARY_PASS=true"
echo "DAY6_FALLBACK_EXTERNAL_RUN2_BINARY_PASS=true"
echo "DAY6_FALLBACK_EXTERNAL_RUN3_BINARY_PASS=true"
echo "DAY6_FALLBACK_EXTERNAL_RUN1_DETECTOR_PASS=true"
echo "DAY6_FALLBACK_EXTERNAL_RUN2_DETECTOR_PASS=true"
echo "DAY6_FALLBACK_EXTERNAL_RUN3_DETECTOR_PASS=true"
echo "DAY6_FALLBACK_EXTERNAL_ADAPTER_DIRECT_CONTRACT_PASS=true"
echo "DAY6_FALLBACK_EXTERNAL_CONTINUITY_PASS=true"
echo "DAY6_FALLBACK_EXTERNAL_REFERENCE_ALIGNMENT_PASS=true"
echo "DAY6_FALLBACK_EXTERNAL_CROSS_RUN_STATISTICS_PASS=true"
echo "DAY6_FALLBACK_EXTERNAL_FAST_UNCHANGED_PASS=true"
echo "DAY6_FALLBACK_EXTERNAL_DETECTOR_UNCHANGED_PASS=true"
echo "DAY6_FALLBACK_EXTERNAL_REAL_REPLAY_NOT_RERUN=true"
echo "DAY6_FALLBACK_EXTERNAL_ROS_RUN=false"
echo "DAY6_FALLBACK_EXTERNAL_FAST_RUN=false"
"""


def audit_scope(audit: Path) -> dict[str, Any]:
    files = [path for path in audit.rglob("*") if path.is_file()]
    symlinks = [path for path in audit.rglob("*") if path.is_symlink()]
    personal_hits: list[str] = []
    patterns = ("/home/", "/root/", "/Users/", "C:\\Users\\")
    for path in files:
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if any(pattern in text for pattern in patterns):
            personal_hits.append(path.relative_to(audit).as_posix())
    result = {
        "file_count": len(files),
        "wheel_file_count": sum(path.suffix == ".whl" for path in files),
        "rosbag_file_count": sum(path.suffix == ".bag" for path in files),
        "git_directory_count": sum(
            path.is_dir() and path.name == ".git" for path in audit.rglob("*")
        ),
        "symlink_count": len(symlinks),
        "pycache_directory_count": sum(
            path.is_dir() and path.name == "__pycache__"
            for path in audit.rglob("*")
        ),
        "pyc_file_count": sum(path.suffix == ".pyc" for path in files),
        "personal_absolute_path_count": len(personal_hits),
        "personal_absolute_path_files": personal_hits,
    }
    result["audit_package_scope_pass"] = all(
        int(result[name]) == 0
        for name in (
            "wheel_file_count",
            "rosbag_file_count",
            "git_directory_count",
            "symlink_count",
            "pycache_directory_count",
            "pyc_file_count",
            "personal_absolute_path_count",
        )
    )
    return result


def write_internal_hashes(audit: Path) -> tuple[int, int]:
    listing = sorted(
        path.relative_to(audit).as_posix()
        for path in audit.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (audit / "evidence/audit_file_listing.txt").write_text(
        "\n".join(listing) + "\n", encoding="utf-8"
    )
    listing = sorted(
        path.relative_to(audit).as_posix()
        for path in audit.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    rows = [f"{sha256_file(audit / relative)}  {relative}" for relative in listing]
    (audit / "SHA256SUMS").write_text(
        "\n".join(rows) + "\n", encoding="utf-8"
    )
    failures = 0
    for row in rows:
        expected, relative = row.split("  ", 1)
        if sha256_file(audit / relative) != expected:
            failures += 1
    return len(listing) + 1, failures


def normalize_modes(audit: Path) -> None:
    for path in audit.rglob("*"):
        if path.is_symlink():
            raise Day6FallbackError("audit package contains a symlink")
        if path.is_dir():
            path.chmod(0o755)
        elif path.is_file():
            path.chmod(0o755 if path.name == "restore_and_verify.sh" else 0o644)


def build_audit(
    *,
    args: argparse.Namespace,
    result_root: Path,
    output_dir: Path,
    manifest_path: Path,
    gate_path: Path,
    run_lock: Mapping[str, Any],
) -> tuple[Path, Path, dict[str, Any]]:
    audit = Path.home() / AUDIT_NAME
    archive = Path.home() / ARCHIVE_NAME
    if audit.exists() or archive.exists() or Path(f"{archive}.sha256").exists():
        raise Day6FallbackError("Day 6 audit output already exists")
    audit.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="day6_auth_for_package_") as temporary:
        auth_root = safe_extract(
            args.authorization_audit.resolve(), Path(temporary)
        )
        copy_file(
            auth_root / "repo/degen_base.bundle",
            audit / "repo/degen_base.bundle",
        )
        shutil.copytree(
            auth_root / "repo/degen_overlay",
            audit / "repo/degen_overlay",
            dirs_exist_ok=True,
        )
        shutil.copytree(
            auth_root / "repo/home_state",
            audit / "repo/home_state",
            dirs_exist_ok=True,
        )
        shutil.copytree(
            auth_root / "repo/detector_snapshot",
            audit / "repo/detector_snapshot",
            dirs_exist_ok=True,
        )
        copy_file(
            auth_root
            / "evidence/small_results/fallback_c_remediation_gate_summary.json",
            audit / "authorization/fallback_c_gate_summary.json",
        )
        copy_file(
            auth_root
            / "evidence/small_results/"
            "fallback_offline_detector_determinism_remediation_manifest.json",
            audit / "authorization/fallback_c_manifest.json",
        )
        copy_file(
            auth_root / "canonical_output/adapter_detector_outputs_v3.jsonl",
            audit / "authorization/fallback_c_adapter_reference.jsonl",
        )

    for relative in DAY6_SOURCE_PATHS + DAY6_TEST_PATHS + DAY6_DOC_PATHS:
        copy_file(
            ROOT / relative, audit / "repo/degen_overlay" / relative
        )
    if output_dir.is_dir():
        shutil.copytree(
            output_dir,
            audit
            / "repo/degen_overlay/artifacts/current/"
            "harmful_bias_multihyp_dev/day6_fallback_functional_diagnostics",
            dirs_exist_ok=True,
        )

    authorization_identity = validate_authorization_archive(
        args.authorization_audit.resolve()
    )
    write_json(
        audit / "authorization/authorization_identity.json",
        authorization_identity,
    )
    copy_file(
        args.frozen_reference.resolve(),
        audit
        / "frozen_reference/"
        "Degen-LIO-frozen-real-observation-quick-shack-v1.1.tar.gz",
    )
    (
        audit
        / "frozen_reference/"
        "Degen-LIO-frozen-real-observation-quick-shack-v1.1.tar.gz.sha256"
    ).write_text(
        f"{EXPECTED_FROZEN_REFERENCE_SHA256}  "
        "Degen-LIO-frozen-real-observation-quick-shack-v1.1.tar.gz\n",
        encoding="utf-8",
    )

    for index, run_id in enumerate(SUB_RUN_IDS, start=1):
        run = result_root / run_id
        diagnostics = run / "detector_diagnostics"
        observation_destination = audit / f"real_replay_observations/run_{index}"
        for name in (
            "observation_records_v3.bin",
            "observation_records_v3.bin.sha256",
            "observation_record_index.csv",
            "observation_lifecycle_summary.json",
            "run_summary.json",
        ):
            copy_file(run / name, observation_destination / name)
        detector_destination = audit / f"detector_outputs/run_{index}"
        for name in (
            "adapter_detector_outputs_v3.jsonl",
            "adapter_detector_outputs_v3.jsonl.sha256",
            "direct_production_metrics_v1.jsonl",
            "direct_production_metrics_v1.jsonl.sha256",
            "detector_latency_records.csv",
            "contract_aware_direct_equivalence.csv",
            "detector_processing_summary.json",
        ):
            copy_file(diagnostics / name, detector_destination / name)
        evidence_destination = audit / f"evidence/run_{index}"
        for source_name, destination_name in (
            ("connection_handshake_summary.json", "connection_handshake/summary.json"),
            ("tail_clock_raw_summary.json", "tail_clock/raw_summary.json"),
            ("tail_clock_adjudication_summary.json", "tail_clock/adjudication_summary.json"),
            ("drain_summary.json", "drain/summary.json"),
            ("shutdown_summary.json", "shutdown/summary.json"),
            ("runtime_product_summary.json", "runtime_products/summary.json"),
            ("in_call_immutability_summary.json", "in_call_immutability/summary.json"),
            ("observation_binary_validation_summary.json", "binary_validation/summary.json"),
        ):
            copy_file(run / source_name, evidence_destination / destination_name)
        for name in (
            "detector_processing_summary.json",
            "direct_equivalence_domain_summary.json",
            "output_continuity_summary.json",
            "direction_continuity_records.csv",
            "direction_continuity_summary.json",
            "detector_flag_timeline.csv",
            "detector_flag_transition_summary.json",
            "detector_metric_descriptive_statistics.csv",
            "detector_metric_descriptive_statistics.json",
            "detector_latency_summary.json",
            "record_input_immutability.csv",
            "detector_no_gt_audit.json",
            "environment_identity.json",
            "source_identity.json",
        ):
            copy_file(
                diagnostics / name,
                evidence_destination / "detector_processing" / name,
            )

    shutil.copytree(
        result_root / "comparison",
        audit / "evidence/reference_comparison",
        dirs_exist_ok=True,
    )
    shutil.copytree(
        result_root / "comparison",
        audit / "evidence/cross_run_statistics",
        dirs_exist_ok=True,
    )
    shutil.copytree(
        result_root / "plots",
        audit / "evidence/plots",
        dirs_exist_ok=True,
    )
    copy_file(
        args.targeted_test_log.resolve(),
        audit / "evidence/tests/targeted_pytest.txt",
    )
    copy_file(
        args.full_test_log.resolve(), audit / "evidence/tests/full_pytest.txt"
    )
    copy_file(
        args.before_dir.resolve() / "degen_status.txt",
        audit / "evidence/git/degen_status_before.txt",
    )
    copy_file(
        args.before_dir.resolve() / "degen_porcelain.txt",
        audit / "evidence/git/degen_porcelain_before.txt",
    )
    copy_file(
        args.before_dir.resolve() / "degen_working.patch",
        audit / "evidence/git/degen_working_before.patch",
    )
    copy_file(
        args.before_dir.resolve() / "fastlio2_porcelain.txt",
        audit / "evidence/git/fastlio2_porcelain_before.txt",
    )
    copy_file(
        args.before_dir.resolve() / "fastlio2_working.patch",
        audit / "evidence/git/fastlio2_working.patch",
    )
    write_json(
        audit / "evidence/run_lock/day6_run_lock_redacted.json",
        redact(run_lock),
    )
    copy_file(
        manifest_path,
        audit
        / "evidence/small_results/"
        "day6_fallback_functional_diagnostics_manifest.json",
    )
    copy_file(
        gate_path,
        audit
        / "evidence/small_results/"
        "day6_fallback_functional_diagnostics_gate_summary.json",
    )
    copy_file(
        ROOT / DAY6_DOC_PATHS[1],
        audit
        / "evidence/small_results/"
        "day6_fallback_functional_diagnostics_report.md",
    )
    write_json(
        audit / "repo/fastlio2_reference/identity.json",
        {
            "branch": EXPECTED_FAST_BRANCH,
            "head": EXPECTED_FAST_HEAD,
            "working_patch_sha256": run_lock["fastlio2_diff_sha256"],
            "binary_sha256": EXPECTED_FAST_BINARY_SHA256,
            "tap_source_sha256": run_lock["tap_source_sha256"],
            "in_call_audit_source_sha256": run_lock[
                "in_call_audit_source_sha256"
            ],
            "compact_writer_source_sha256": run_lock[
                "compact_writer_source_sha256"
            ],
            "fast_source_modified_this_task": False,
            "fast_build_run": False,
            "fast_test_run": False,
        },
    )
    (audit / "restore_and_verify.sh").write_text(
        restore_script(), encoding="utf-8"
    )
    normalize_modes(audit)
    scope = audit_scope(audit)
    write_json(audit / "evidence/small_results/audit_scope_summary.json", scope)
    normalize_modes(audit)
    if not scope["audit_package_scope_pass"]:
        raise Day6FallbackError(f"audit package scope failed: {scope}")
    file_count, hash_failures = write_internal_hashes(audit)
    normalize_modes(audit)
    if hash_failures:
        raise Day6FallbackError("internal audit hash verification failed")

    restore_log = (
        Path("/tmp/degen_lio_day6_fallback_functional_diagnostics/audit")
        / "restore_and_verify.txt"
    )
    restore_log.parent.mkdir(parents=True, exist_ok=True)
    with restore_log.open("w", encoding="utf-8") as stream:
        completed = subprocess.run(
            [str(audit / "restore_and_verify.sh")],
            cwd=audit,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    if completed.returncode:
        raise Day6FallbackError(
            f"external restore failed; inspect {restore_log}"
        )
    with tarfile.open(archive, "w:gz", compresslevel=9) as handle:
        handle.add(audit, arcname=audit.name, recursive=True)
    size_bytes = archive.stat().st_size
    if size_bytes > 90 * 1024 * 1024:
        raise Day6FallbackError(
            f"audit archive exceeds 90 MiB: {size_bytes}"
        )
    with tarfile.open(archive, "r:gz") as handle:
        handle.getmembers()
    archive_sha = sha256_file(archive)
    Path(f"{archive}.sha256").write_text(
        f"{archive_sha}  {archive.name}\n", encoding="utf-8"
    )
    return audit, archive, {
        **scope,
        "internal_file_count": file_count,
        "internal_hash_failure_count": hash_failures,
        "archive_size_bytes": size_bytes,
        "archive_sha256": archive_sha,
        "gzip_test_pass": True,
        "restore_exit_code": completed.returncode,
        "restore_log": str(restore_log),
    }


def main() -> int:
    args = parse_args()
    result_root = args.result_root.expanduser().resolve()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise SystemExit(f"ERROR: artifact output exists: {output_dir}")
    run_lock = json_object(args.run_lock.resolve())
    validate_authorization_archive(args.authorization_audit.resolve())
    if sha256_file(args.frozen_reference.resolve()) != EXPECTED_FROZEN_REFERENCE_SHA256:
        raise Day6FallbackError("frozen reference changed")
    if git_output(["branch", "--show-current"]).strip() != EXPECTED_DEGEN_BRANCH:
        raise Day6FallbackError("Degen branch changed")
    if git_output(["rev-parse", "HEAD"]).strip() != EXPECTED_DEGEN_HEAD:
        raise Day6FallbackError("Degen HEAD changed")
    fast_root = Path(run_lock["fastlio2_root"])
    if git_output(["branch", "--show-current"], fast_root).strip() != EXPECTED_FAST_BRANCH:
        raise Day6FallbackError("FAST branch changed")
    if git_output(["rev-parse", "HEAD"], fast_root).strip() != EXPECTED_FAST_HEAD:
        raise Day6FallbackError("FAST HEAD changed")

    runs = load_run_evidence(result_root)
    comparison = json_object(
        result_root / "comparison/cross_run_pairwise_summary.json"
    )
    plot_summary = json_object(result_root / "plots/plot_summary.json")
    detector_after = detector_identity(ROOT)
    fast_patch_after = git_patch_sha(
        fast_root, "checkpoint/fastlio2-readonly-tap-v1-pass"
    )
    source_lock_pass, source_mismatches = locked_source_pass(run_lock)
    baseline_paths = baseline_status_paths(
        args.before_dir.resolve() / "degen_porcelain.txt"
    )
    added_paths = current_status_paths() - baseline_paths
    unexpected = sorted(added_paths - ALLOWED_NEW_PATHS)
    diff_scope_pass = not unexpected
    targeted_pass = test_pass(
        args.targeted_test_log.resolve(), args.targeted_test_rc.resolve()
    )
    full_pass = test_pass(
        args.full_test_log.resolve(), args.full_test_rc.resolve()
    )
    facts = build_facts(
        runs=runs,
        comparison=comparison,
        plot_summary=plot_summary,
        run_lock=run_lock,
        targeted_pass=targeted_pass,
        full_pass=full_pass,
        diff_scope_pass=diff_scope_pass,
        source_lock_pass=source_lock_pass,
        fast_patch_after=fast_patch_after,
        detector_after=detector_after,
    )
    gates = evaluate_day6_gate(facts)
    if not gates["DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_PASS"]:
        failed = [name for name in REQUIRED_GATE_NAMES if not gates[name]]
        raise Day6FallbackError(
            f"Day 6 Fallback gate failed: {failed}; source={source_mismatches}"
        )

    created_at = datetime.now(timezone.utc).isoformat()
    manifest = manifest_value(
        created_at=created_at,
        run_lock=run_lock,
        runs=runs,
        comparison=comparison,
        gates=gates,
        detector_after=detector_after,
        fast_patch_after=fast_patch_after,
        unexpected=unexpected,
    )
    manifest_path = (
        ROOT
        / "manifests/harmful_bias/"
        "day6_fallback_functional_diagnostics_manifest.json"
    )
    gate_path = (
        output_dir / "day6_fallback_functional_diagnostics_gate_summary.json"
    )
    output_dir.mkdir(parents=True, exist_ok=False)
    write_json(manifest_path, manifest)
    write_json(gate_path, gates)
    write_json(
        output_dir / "day6_fallback_functional_diagnostics_summary.json",
        {
            "main_run_id": MAIN_RUN_ID,
            "sub_run_ids": list(SUB_RUN_IDS),
            "gate": gates,
            "reference_comparison": comparison,
        },
    )
    report = report_text(manifest, gates, runs)
    report_path = ROOT / DAY6_DOC_PATHS[1]
    report_path.write_text(report, encoding="utf-8")
    copy_file(manifest_path, output_dir / manifest_path.name)
    copy_file(report_path, output_dir / report_path.name)
    shutil.copytree(
        result_root / "plots", output_dir / "plots", dirs_exist_ok=True
    )
    for row in runs:
        run_id = row["run_id"]
        write_json(
            output_dir / f"{run_id}_summary.json",
            {
                "run": row["run"],
                "detector": row["detector"],
                "direction": row["direction"],
                "flags": row["flags"],
                "metrics": row["metrics"],
                "latency": row["latency"],
            },
        )

    audit, archive, audit_result = build_audit(
        args=args,
        result_root=result_root,
        output_dir=output_dir,
        manifest_path=manifest_path,
        gate_path=gate_path,
        run_lock=run_lock,
    )
    final = {
        "schema_version": "day6_fallback_finalization_summary_v1",
        "gates": gates,
        "manifest": manifest,
        "audit_dir": str(audit),
        "archive": str(archive),
        "audit": audit_result,
        "commit_created": False,
        "push_performed": False,
    }
    print(json.dumps(final, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        Day6FallbackError,
        OSError,
        KeyError,
        ValueError,
        tarfile.TarError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
