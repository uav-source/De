"""Locked deterministic diagnostic replay pipeline for Stage 2 Day 11B."""

from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import numpy as np
import scipy

from eval.analysis_lock import compute_directory_hash, git_commit, git_status_clean, sha256_file
from eval.stage2_failure_day11b_lock import verify_day11a_case_lock
from eval.stage2_failure_day11b_plan import (
    REPLAY_PLAN_FIELDS,
    build_replay_plan,
    replay_plan_document,
    validate_replay_plan,
)
from eval.stage2_failure_day11b_provenance import (
    AXIAL_SUPPORT_AUDIT_FIELDS,
    BASE_OBSERVATION_PAIRING_AUDIT_FIELDS,
    STRATEGY_CHAIN_AUDIT_FIELDS,
    V1_V2_EQUIVALENCE_AUDIT_FIELDS,
    audit_axial_support,
    base_observation_provenance,
    build_base_observation_pairing_audit,
    build_strategy_chain_audit,
    canonical_array_sequence_sha256,
    compare_v1_v2_scientific_outputs,
    result_tree_manifest,
    stressed_plane_checksum,
    write_v1_immutable_after_evidence,
)
from eval.stage2_failure_day11b_schema import (
    CASE_SUMMARY_FIELDS,
    DAY11B_RUN_SCHEMA_VERSION,
    LOGGING_AUDIT_FIELDS,
    MERGED_FIELDS,
    PAIRING_AUDIT_FIELDS,
    build_pairing_audit,
    compare_logging_runs,
    evaluate_day11b_gate,
    merge_frame_records,
    write_fixed_csv,
)
from eval.stage2_failure_day11b_stress_trace import STRESS_TRACE_FIELDS, compute_stress_trace
from eval.stage2_failure_day11b_v2_schema import (
    DAY11B_V2_RUN_SCHEMA_VERSION,
    DAY11B_V2_STRESS_MECHANISM_AUDIT_FIELDS,
    evaluate_day11b_v2_gate,
)
from eval.stage2_failure_day9 import compute_window_records, window_config_from_mapping
from eval.stage2_failure_gt_metrics import evaluate_gt_frame_records
from eval.stage2_failure_logging import Stage2FailureOnlineLogger
from eval.stage2_failure_no_gt_audit import GTAccessSentinelMapping
from eval.stage2_failure_schema import write_gt_csv, write_online_csv
from eval.stage2_failure_window_schema import write_window_csv
from eval.synthetic_pipeline_common import (
    generate_or_load_observations,
    generate_or_validate_sequence,
    load_yaml,
    write_json,
)
from eval.update_metrics import compute_update_metrics
from eval.weak_update_stage2c import (
    build_stage2c_specs,
    make_motion,
    observation_checksum,
    observation_patch_ids,
)
from minibench.correspondence_stress import apply_correspondence_stress
from minibench.map_lio import run_map_lio
from minibench.motion_simulator import process_noise_checksum
from minibench.nested_geometry_observations import array_checksum, simulate_nested_geometry_observations


HISTORICAL_ARTIFACT_PATHS = (
    "artifacts/current/detector_stage2a",
    "artifacts/history/stage2b_column_scaling_no_go",
    "artifacts/current/weak_update_stage2c",
)
DAY11B_V1_CHECKPOINT = "checkpoint/day11b-v1-runtime-pass-provenance-incomplete"
DAY11B_V1_RUN_RELATIVE = Path(
    "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v1"
)


def verify_lock_and_write_plan(
    root: Path,
    case_lock_path: Path,
    run_id: str,
    output_root: Path,
    overwrite: bool = False,
) -> Mapping[str, Any]:
    """Verify Day 11A and write a plan without invoking any estimator."""

    root = Path(root).resolve()
    if not git_status_clean(root):
        raise RuntimeError("Day 11B requires a clean worktree at start")
    config = _load_and_validate_config(root)
    verification = verify_day11a_case_lock(root, case_lock_path)
    rows = build_replay_plan(verification)
    result_dir = Path(output_root).resolve() / str(run_id)
    _reject_v1_output_path(root, result_dir)
    if result_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Day 11B output exists: {result_dir}")
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True)
    write_json(result_dir / "case_lock_verification.json", verification)
    write_fixed_csv(result_dir / "replay_plan.csv", rows, REPLAY_PLAN_FIELDS)
    write_json(result_dir / "replay_plan.json", replay_plan_document(rows))
    v1_plan = root / DAY11B_V1_RUN_RELATIVE / "replay_plan.csv"
    plan_byte_identical = bool(
        v1_plan.is_file() and (result_dir / "replay_plan.csv").read_bytes() == v1_plan.read_bytes()
    )
    if str(run_id).endswith("_v2") and not plan_byte_identical:
        raise ValueError("Day 11B v2 replay plan is not byte-identical to v1")
    return {
        "result_dir": str(result_dir),
        "case_lock_verification_pass": True,
        "replay_plan_row_count": len(rows),
        "estimator_run": False,
        "v1_v2_replay_plan_byte_identical": plan_byte_identical,
        "config": config,
    }


def run_stage2_failure_day11b(
    root: Path,
    case_lock_path: Path,
    run_id: str,
    output_root: Path,
    overwrite: bool = False,
) -> Mapping[str, Any]:
    """Execute exactly the eight preregistered method replays."""

    root = Path(root).resolve()
    clean_at_start = git_status_clean(root)
    if not clean_at_start:
        raise RuntimeError("Day 11B requires a clean worktree at start")
    config = _load_and_validate_config(root)
    result_dir = Path(output_root).resolve() / str(run_id)
    _reject_v1_output_path(root, result_dir)
    if result_dir.exists() and overwrite:
        shutil.rmtree(result_dir)
    if not result_dir.exists():
        verify_lock_and_write_plan(root, case_lock_path, run_id, output_root, False)
    verification = verify_day11a_case_lock(root, case_lock_path)
    plan_document = _read_json(result_dir / "replay_plan.json")
    plan = list(plan_document.get("rows", []))
    validate_replay_plan(plan, verification)
    expected_plan = list(build_replay_plan(verification))
    if plan != expected_plan:
        raise ValueError("stored Day 11B replay plan differs from the verified plan")
    v1_run = root / DAY11B_V1_RUN_RELATIVE
    v1_plan_path = v1_run / "replay_plan.csv"
    v2_plan_path = result_dir / "replay_plan.csv"
    plan_byte_identical = bool(
        v1_plan_path.is_file() and v2_plan_path.read_bytes() == v1_plan_path.read_bytes()
    )
    if not plan_byte_identical:
        raise ValueError("Day 11B v2 replay plan is not byte-identical to v1")
    before_manifest_path = Path.home() / "day11b_v1_result_sha256_before.txt"
    if not before_manifest_path.is_file():
        raise FileNotFoundError("Day 11B v1 immutable before-manifest is missing")
    if before_manifest_path.read_bytes() != result_tree_manifest(root, v1_run):
        raise RuntimeError("Day 11B v1 result tree changed before v2 replay")
    day11b_v1_checkpoint_commit = _git_rev_parse(root, f"{DAY11B_V1_CHECKPOINT}^{{}}")
    head_descends_from_day11b_v1 = _git_is_ancestor(root, DAY11B_V1_CHECKPOINT, "HEAD")
    if not head_descends_from_day11b_v1:
        raise RuntimeError("HEAD does not descend from the frozen Day 11B v1 checkpoint")

    historical_before = _historical_hashes(root)
    common = load_yaml(root / "configs/update/stage2c_common.yaml")
    stress_config = load_yaml(root / "configs/update/stage2c_stress.yaml")
    motion_config = load_yaml(root / "configs/toy_lio/motion_surrogate_stage2c.yaml")
    detector_config = load_yaml(root / "configs/detector/odi_stage2a.yaml")
    update_lock = _read_json(root / "artifacts/current/weak_update_stage2c/locked/update_lock.json")
    day9_config = load_yaml(root / str(config["day9_window_config"]))
    window_config = window_config_from_mapping(day9_config)
    threshold = float(update_lock["online_odi_threshold"])
    selected_alpha = float(update_lock["selected_attenuation_alpha"])
    huber_delta = float(common["huber_delta_sigma"])

    logging_rows = []
    all_online = []
    all_gt = []
    all_window = []
    all_stress = []
    all_merged = []
    summaries = []
    case_manifests = []
    strategy_rows = []
    axial_rows = []
    axial_summaries = []
    logging_case_failures = 0
    checksum_mismatches = 0
    max_differences = {
        "trajectory": 0.0, "covariance": 0.0, "applied_delta": 0.0, "full_delta": 0.0,
    }
    gt_access_attempts = 0
    solver_failures = 0
    incomplete_sequences = 0

    cases_by_input: Dict[tuple, list] = {}
    for row in plan:
        key = tuple(row[field] for field in (
            "sweep", "level", "geometry_seed", "sensor_seed", "process_seed", "stress"
        ))
        cases_by_input.setdefault(key, []).append(row)

    with tempfile.TemporaryDirectory(prefix="degen_lio_day11b_") as temporary:
        temp_root = Path(temporary)
        external_inputs: Dict[tuple, Mapping[str, Any]] = {}
        for sweep in ("geometry", "observation"):
            selected = verification[f"selected_{sweep}_case"]
            external_inputs.update(
                _build_external_inputs(
                    root, temp_root, sweep, selected, common, stress_config, motion_config
                )
            )
        for input_key, method_rows in cases_by_input.items():
            external = external_inputs[input_key]
            stressed = external["observations"]
            truth = np.asarray(stressed["pose_gt"], dtype=float).copy()
            axes = np.asarray(stressed["axis_per_frame"], dtype=float).copy()
            online_payload = GTAccessSentinelMapping(stressed)
            for plan_row in method_rows:
                case_id = str(plan_row["case_id"])
                method = str(plan_row["method"])
                context = {
                    "run_id": str(run_id), "sequence_id": str(external["sequence_id"]),
                    "sweep": str(plan_row["sweep"]), "level": str(plan_row["level"]),
                    "stress": str(plan_row["stress"]),
                    "geometry_seed": int(plan_row["geometry_seed"]),
                    "sensor_seed": int(plan_row["sensor_seed"]),
                    "process_seed": int(plan_row["process_seed"]), "method": method,
                }
                alpha = 1.0 if method == "huber_full" else selected_alpha
                disabled = run_map_lio(
                    online_payload, external["motion"], detector_config, common,
                    method, threshold, alpha, failure_logger=None,
                )
                logger = Stage2FailureOnlineLogger(context)
                enabled = run_map_lio(
                    online_payload, external["motion"], detector_config, common,
                    method, threshold, alpha, failure_logger=logger,
                )
                online_rows = list(logger.records)
                equivalence = compare_logging_runs(
                    case_id, disabled, enabled, online_rows,
                    float(config["logging_equivalence_tolerance"]),
                )
                logging_rows.extend(equivalence["rows"])
                logging_case_failures += int(not equivalence["pass"])
                checksum_mismatches += int(equivalence["checksum_mismatch_count"])
                for target, source in (
                    ("trajectory", "max_trajectory_difference"),
                    ("covariance", "max_covariance_difference"),
                    ("applied_delta", "max_applied_delta_difference"),
                    ("full_delta", "max_full_delta_difference"),
                ):
                    max_differences[target] = max(max_differences[target], float(equivalence[source]))
                gt_rows = list(evaluate_gt_frame_records(
                    online_rows, enabled["prior_poses"], enabled["poses"], truth, axes
                ))
                window_rows = list(compute_window_records(online_rows, window_config))
                stress_rows = list(compute_stress_trace(
                    online_rows, enabled["prior_poses"], stressed, huber_delta
                ))
                merged = list(merge_frame_records(
                    case_id, online_rows, gt_rows, window_rows, stress_rows
                ))
                case_axial_rows, case_axial_summary = audit_axial_support(
                    case_id, str(plan_row["stress"]), online_rows, stressed
                )
                case_dir = result_dir / "cases" / case_id
                write_online_csv(case_dir / "frame_diagnostics_online.csv", online_rows)
                write_gt_csv(case_dir / "frame_diagnostics_gt.csv", gt_rows)
                write_window_csv(case_dir / "frame_window_statistics.csv", window_rows)
                write_fixed_csv(case_dir / "frame_stress_trace.csv", stress_rows, STRESS_TRACE_FIELDS)
                metrics = compute_update_metrics(
                    enabled["poses"], truth, axes, enabled["frame_diagnostics"], enabled["covariances"]
                )
                provenance_fields = {
                    field: external[field] for field in (
                        "points_lidar_base_checksum", "normals_world_base_checksum",
                        "R_diag_list_checksum", "plane_points_world_base_checksum",
                        "plane_points_world_stressed_checksum", "initial_state_checksum",
                        "initial_covariance_checksum", "process_noise_checksum",
                        "scene_checksum", "stress_checksum",
                    )
                }
                metrics.update({
                    **provenance_fields,
                    "strategy": str(enabled["strategy"]),
                    "strategy_logging_disabled": str(disabled["strategy"]),
                    "strategy_logging_enabled": str(enabled["strategy"]),
                    "axial_support_mask_list_checksum": case_axial_summary[
                        "axial_support_mask_list_checksum"
                    ],
                    "contamination_mask_list_checksum": case_axial_summary[
                        "contamination_mask_list_checksum"
                    ],
                })
                case_manifest = {
                    **{field: plan_row[field] for field in (
                        "case_id", "sweep", "level", "stress", "geometry_seed",
                        "sensor_seed", "process_seed", "method"
                    )},
                    **{field: external[field] for field in (
                        "scene_checksum", "base_observation_checksum",
                        "stressed_observation_checksum", "stress_checksum",
                        "process_noise_checksum", "initial_state_checksum",
                        "initial_covariance_checksum", "contaminated_measurement_count",
                        "stress_active_frame_count", "points_lidar_base_checksum",
                        "normals_world_base_checksum", "R_diag_list_checksum",
                        "plane_points_world_base_checksum", "plane_points_world_stressed_checksum",
                        "points_lidar_frame_count", "normals_world_frame_count",
                        "R_diag_frame_count",
                    )},
                    "axial_support_mask_list_checksum": case_axial_summary[
                        "axial_support_mask_list_checksum"
                    ],
                    "contamination_mask_list_checksum": case_axial_summary[
                        "contamination_mask_list_checksum"
                    ],
                    "contaminated_axial_support_count": case_axial_summary[
                        "contaminated_axial_support_count"
                    ],
                    "contaminated_non_axial_support_count": case_axial_summary[
                        "contaminated_non_axial_support_count"
                    ],
                    "axial_only": bool(case_axial_summary["axial_only"]),
                    "frame_count": len(online_rows),
                    "expected_online_frame_count": int(truth.shape[0] - 1),
                    "full_sequence_complete": len(online_rows) == int(truth.shape[0] - 1),
                    "solver_failure_count": int(enabled["solver_failure_count"]),
                    "logging_equivalence_pass": bool(equivalence["pass"]),
                    "gt_field_access_attempt_count": int(online_payload.access_attempt_count),
                    "online_estimator_received_gt": False,
                }
                strategy_audit = build_strategy_chain_audit(
                    case_id, method, str(case_manifest["method"]), metrics,
                    disabled, enabled, online_rows,
                )
                metrics["strategy_chain_pass"] = bool(strategy_audit["pass"])
                case_manifest.update({
                    "strategy": str(enabled["strategy"]),
                    "strategy_logging_disabled": str(disabled["strategy"]),
                    "strategy_logging_enabled": str(enabled["strategy"]),
                    "strategy_chain_pass": bool(strategy_audit["pass"]),
                })
                write_json(case_dir / "trajectory_metrics.json", metrics)
                write_json(case_dir / "case_manifest.json", case_manifest)
                write_json(case_dir / "strategy_chain_audit.json", strategy_audit)
                summaries.append(_case_summary(plan_row, merged, metrics))
                case_manifests.append(case_manifest)
                strategy_rows.append(strategy_audit)
                axial_rows.extend(case_axial_rows)
                axial_summaries.append(case_axial_summary)
                all_online.extend(online_rows)
                all_gt.extend(gt_rows)
                all_window.extend(window_rows)
                all_stress.extend(stress_rows)
                all_merged.extend(merged)
                solver_failures += int(enabled["solver_failure_count"])
                incomplete_sequences += int(not case_manifest["full_sequence_complete"])
            gt_access_attempts += int(online_payload.access_attempt_count)
        stress_audits = [dict(value["stress_audit"]) for value in external_inputs.values()]

    pairing_rows = list(build_pairing_audit(case_manifests))
    pairing_violations = sum(int(not bool(row["pairing_valid"])) for row in pairing_rows)
    base_pairing_rows, base_pairing_counts = build_base_observation_pairing_audit(case_manifests)
    write_fixed_csv(result_dir / "logging_equivalence_audit.csv", logging_rows, LOGGING_AUDIT_FIELDS)
    write_fixed_csv(result_dir / "pairing_audit.csv", pairing_rows, PAIRING_AUDIT_FIELDS)
    write_fixed_csv(
        result_dir / "stress_mechanism_audit.csv", stress_audits,
        DAY11B_V2_STRESS_MECHANISM_AUDIT_FIELDS,
    )
    write_fixed_csv(
        result_dir / "strategy_chain_audit.csv", strategy_rows, STRATEGY_CHAIN_AUDIT_FIELDS
    )
    write_fixed_csv(result_dir / "axial_support_audit.csv", axial_rows, AXIAL_SUPPORT_AUDIT_FIELDS)
    axial_summary_document = {
        "schema_version": "stage2_failure_day11b_axial_support_summary_v2",
        "case_count": len(axial_summaries),
        "cases": axial_summaries,
        "frame_comparison_count": len(axial_rows),
        "contaminated_measurement_count": sum(
            int(row["contaminated_measurement_count"]) for row in axial_summaries
        ),
        "contaminated_axial_support_count": sum(
            int(row["contaminated_axial_support_count"]) for row in axial_summaries
        ),
        "contaminated_non_axial_support_count": sum(
            int(row["contaminated_non_axial_support_count"]) for row in axial_summaries
        ),
        "axial_only_audit_pass": bool(
            len(axial_summaries) == 8 and all(bool(row["pass"]) for row in axial_summaries)
        ),
    }
    write_json(result_dir / "axial_support_summary.json", axial_summary_document)
    write_fixed_csv(
        result_dir / "base_observation_pairing_audit.csv", base_pairing_rows,
        BASE_OBSERVATION_PAIRING_AUDIT_FIELDS,
    )
    write_fixed_csv(result_dir / "replay_case_summary.csv", summaries, CASE_SUMMARY_FIELDS)
    write_fixed_csv(result_dir / "replay_frame_diagnostics_merged.csv", all_merged, MERGED_FIELDS)
    equivalence_rows, equivalence_summary = compare_v1_v2_scientific_outputs(v1_run, result_dir)
    write_fixed_csv(
        result_dir / "v1_v2_scientific_equivalence_audit.csv", equivalence_rows,
        V1_V2_EQUIVALENCE_AUDIT_FIELDS,
    )
    immutable = write_v1_immutable_after_evidence(
        root, v1_run, before_manifest_path,
        Path.home() / "day11b_v1_result_sha256_after.txt",
        Path.home() / "day11b_v1_result_tree_digest_after.txt",
    )
    no_gt_audit = {
        "schema_version": "stage2_failure_day11b_no_gt_audit_v1",
        "gt_field_access_attempt_count": gt_access_attempts,
        "online_estimator_received_gt": False,
        "gt_evaluator_called_after_online_estimation": True,
        "window_statistics_read_gt": False,
        "audit_pass": gt_access_attempts == 0,
    }
    write_json(result_dir / "no_gt_audit.json", no_gt_audit)
    historical_after = _historical_hashes(root)
    clean_count = sum(int(row["contaminated_measurement_count"]) for row in stress_audits if row["stress"] == "clean")
    coherent_count = sum(int(row["contaminated_measurement_count"]) for row in stress_audits if row["stress"] == "coherent_subhuber_slip")
    coherent_active = sum(int(row["stress_active_frame_count"]) for row in stress_audits if row["stress"] == "coherent_subhuber_slip")
    axial_mask_list_checksum = canonical_array_sequence_sha256([
        np.asarray(row["axial_support_mask_list_checksum"], dtype="U64")
        for row in axial_summaries
    ])
    contamination_mask_list_checksum = canonical_array_sequence_sha256([
        np.asarray(row["contamination_mask_list_checksum"], dtype="U64")
        for row in axial_summaries
    ])
    manifest: Dict[str, Any] = {
        "run_id": str(run_id),
        "task": "Stage 2 Day 11B-R — Locked Replay Provenance Hardening v2",
        "schema_version": DAY11B_V2_RUN_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_branch": _git_branch(root), "git_commit": git_commit(root),
        "git_status_clean_at_start": clean_at_start,
        "python_version": platform.python_version(), "numpy_version": np.__version__,
        "scipy_version": scipy.__version__, "python311_available": False,
        "python311_tests_pass": False,
        "day11a_checkpoint_commit": verification["day11a_checkpoint_commit"],
        "head_descends_from_day11a_checkpoint": verification["head_descends_from_day11a_checkpoint"],
        "day11b_v1_checkpoint_commit": day11b_v1_checkpoint_commit,
        "head_descends_from_day11b_v1_checkpoint": head_descends_from_day11b_v1,
        "candidate_pool_path": str(Path(case_lock_path).resolve().parent / "candidate_pool.csv"),
        "candidate_pool_sha256": verification["candidate_pool_sha256"],
        "day11a_case_lock_path": str(Path(case_lock_path).resolve()),
        "day11a_case_lock_sha256": verification["day11a_case_lock_sha256"],
        "protocol_revision_manifest_sha256": verification["protocol_revision_manifest_sha256"],
        "case_lock_verification_pass": True,
        "case_lock_field_mismatch_count": verification["case_lock_field_mismatch_count"],
        "case_lock_hash_mismatch_count": verification["case_lock_hash_mismatch_count"],
        "case_selection_reproducibility_pass": verification["case_selection_reproducibility_pass"],
        "stage2c_tag": verification["stage2c_tag"], "stage2c_commit": verification["stage2c_commit"],
        "stage2c_test_manifest_sha256": verification["stage2c_test_manifest_sha256"],
        "stage2c_update_lock_sha256": verification["stage2c_update_lock_sha256"],
        "stage2c_common_config_sha256": verification["stage2c_common_config_sha256"],
        "stage2c_test_config_sha256": verification["stage2c_test_config_sha256"],
        "stage2c_stress_config_sha256": verification["stage2c_stress_config_sha256"],
        "method_list": list(verification["method_list"]),
        "replay_stress_list": list(verification["replay_stress_list"]),
        "allowed_stage2c_stress_list": list(verification["allowed_stage2c_stress_list"]),
        "expected_replay_count": 8, "completed_replay_count": len(case_manifests),
        "v1_run_dir": str(v1_run), "v2_run_dir": str(result_dir),
        "v1_replay_plan_sha256": sha256_file(v1_plan_path),
        "v2_replay_plan_sha256": sha256_file(v2_plan_path),
        "v1_v2_replay_plan_byte_identical": plan_byte_identical,
        **immutable,
        "selected_geometry_case": verification["selected_geometry_case"],
        "selected_observation_case": verification["selected_observation_case"],
        "gt_field_access_attempt_count": gt_access_attempts,
        "online_estimator_received_gt": False, "window_statistics_read_gt": False,
        "logging_equivalence_comparison_count": len(case_manifests),
        "logging_equivalence_failure_count": logging_case_failures,
        "logging_max_trajectory_difference": max_differences["trajectory"],
        "logging_max_covariance_difference": max_differences["covariance"],
        "logging_max_applied_delta_difference": max_differences["applied_delta"],
        "logging_max_full_delta_difference": max_differences["full_delta"],
        "logging_checksum_mismatch_count": checksum_mismatches,
        "strategy_chain_comparison_count": len(strategy_rows),
        "strategy_chain_mismatch_count": sum(
            int(not bool(row["pass"])) for row in strategy_rows
        ),
        "runtime_strategies": {
            str(row["case_id"]): str(row["logging_enabled_strategy"])
            for row in strategy_rows
        },
        "axial_support_frame_comparison_count": len(axial_rows),
        "contaminated_measurement_count": axial_summary_document[
            "contaminated_measurement_count"
        ],
        "contaminated_axial_support_count": axial_summary_document[
            "contaminated_axial_support_count"
        ],
        "contaminated_non_axial_support_count": axial_summary_document[
            "contaminated_non_axial_support_count"
        ],
        "axial_only_audit_pass": axial_summary_document["axial_only_audit_pass"],
        "axial_support_mask_list_checksum": axial_mask_list_checksum,
        "contamination_mask_list_checksum": contamination_mask_list_checksum,
        "case_axial_support_mask_list_checksums": {
            str(row["case_id"]): str(row["axial_support_mask_list_checksum"])
            for row in axial_summaries
        },
        "case_contamination_mask_list_checksums": {
            str(row["case_id"]): str(row["contamination_mask_list_checksum"])
            for row in axial_summaries
        },
        **base_pairing_counts,
        **equivalence_summary,
        "pairing_group_count": len(pairing_rows), "pairing_violation_count": pairing_violations,
        "online_row_count": len(all_online), "gt_row_count": len(all_gt),
        "window_row_count": len(all_window), "stress_trace_row_count": len(all_stress),
        "merged_row_count": len(all_merged), "duplicate_frame_key_count": 0,
        "missing_frame_key_count": 0, "nonfinite_violation_count": 0,
        "solver_failure_count": solver_failures,
        "incomplete_sequence_count": incomplete_sequences,
        "clean_contaminated_measurement_count": clean_count,
        "coherent_contaminated_measurement_count": coherent_count,
        "coherent_stress_active_frame_count": coherent_active,
        "case_summary_row_count": len(summaries),
        "stress_mechanism_failure_count": sum(
            int(not bool(row["external_stress_valid"])) for row in stress_audits
        ),
        "gross_outlier_control_replayed": False, "stress_name_alias_used": False,
        "legacy_stage2b_stress_name_used": False,
        "historical_artifact_hashes_before": historical_before,
        "historical_artifact_hashes_after": historical_after,
        "historical_artifacts_unchanged": historical_before == historical_after,
        "historical_trial_tables_available": False,
        "historical_metric_equivalence_performed": False,
        "new_seed_used": False, "full_reserved_test_suite_rerun": False,
        "new_reserved_test_namespace_consumed": False,
        "replay_is_independent_test": False, "replay_is_representative": False,
        "replay_for_diagnosis_only": True,
        "replay_used_for_threshold_selection": False,
        "replay_used_for_stage2_gate": False,
        "figures_generated": False, "threshold_created": False,
        "auroc_computed": False, "fpr_computed": False, "f1_computed": False,
        "detection_delay_computed": False, "fast_lio2_integrated": False,
        "STAGE2_GATE": "INCOMPLETE", "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED",
        "RISK_WARNING_AUTHORIZED": False, "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
        "DAY11B_V1_RUNTIME_RESULT": "PASS",
        "DAY11B_V1_PROVENANCE_COMPLETE": False,
    }
    runtime_passed = evaluate_day11b_gate(manifest)
    manifest["DAY11B_V2_RUNTIME_RESULT"] = "PASS" if runtime_passed else "FAIL"
    provenance_passed = evaluate_day11b_v2_gate(manifest)
    manifest["DAY11B_V2_PROVENANCE_COMPLETE"] = provenance_passed
    manifest["DAY11B_V2_PROVENANCE_PASS"] = provenance_passed
    manifest["DAY11B_DETERMINISTIC_REPLAY_PASS"] = provenance_passed
    manifest["DAY11_REPLAY_PASS"] = provenance_passed
    manifest["DAY12_DIAGNOSTIC_FIGURES_AUTHORIZED"] = provenance_passed
    write_json(result_dir / "day11b_v2_summary.json", manifest)
    write_json(result_dir / "run_manifest.json", manifest)
    return manifest


def _build_external_inputs(
    root: Path,
    temp_root: Path,
    sweep: str,
    selected: Mapping[str, Any],
    common: Mapping[str, Any],
    stress_config: Mapping[str, Any],
    motion_config: Mapping[str, Any],
) -> Mapping[tuple, Mapping[str, Any]]:
    geometry_seed = int(selected["geometry_seed"])
    sensor_seed = int(selected["sensor_seed"])
    process_seed = int(selected["process_seed"])
    level = str(selected["level"])
    specs = [
        spec for spec in build_stage2c_specs(common, geometry_seed, "test")
        if str(spec["sweep_type"]) == sweep and str(spec["level"]) == level
    ]
    if len(specs) != 1:
        raise ValueError(f"frozen Stage 2C spec lookup failed for {sweep}/{level}")
    spec = specs[0]
    sequence_dir = temp_root / str(spec["sequence_id"])
    generate_or_validate_sequence(sequence_dir, spec)
    detector_path = root / "configs/detector/odi_stage2a.yaml"
    if sweep == "geometry":
        base = simulate_nested_geometry_observations(
            sequence_dir, detector_path, geometry_seed, sensor_seed,
            float(common["geometry_points_per_square_meter"]),
            int(common["geometry_min_points_per_patch"]),
        )
    else:
        base = generate_or_load_observations(
            sequence_dir / f"sensor_{sensor_seed:03d}", sequence_dir, spec,
            detector_path,
            {"candidate_multiplier": int(common["observation_candidate_multiplier"])},
            sensor_seed, False,
        )
    patch_ids = observation_patch_ids(sequence_dir, base)
    motion = make_motion(base, process_seed, geometry_seed, sensor_seed, motion_config)
    base_provenance = base_observation_provenance(base)
    common_checksums = {
        "scene_checksum": _scene_checksum(sequence_dir),
        "base_observation_checksum": observation_checksum(base),
        "process_noise_checksum": process_noise_checksum(dict(motion)),
        "initial_state_checksum": array_checksum(np.asarray(motion["initial_pose"])),
        "initial_covariance_checksum": array_checksum(
            np.diag(np.asarray(common["initial_covariance_diag"], dtype=float))
        ),
        **base_provenance,
    }
    output = {}
    for stress in ("clean", "coherent_subhuber_slip"):
        stressed = apply_correspondence_stress(
            base, stress, stress_config, "weak_update_stage2c",
            geometry_seed, sensor_seed, patch_ids,
        )
        mask = np.asarray(stressed["contamination_mask"], dtype=bool)
        axial = np.asarray(stressed["is_axial_support"], dtype=bool)
        if mask.shape != axial.shape:
            raise ValueError("stress masks changed shape")
        contaminated = int(np.count_nonzero(mask))
        contaminated_axial = int(np.count_nonzero(mask & axial))
        contaminated_non_axial = int(np.count_nonzero(mask & ~axial))
        axial_only = bool(
            contaminated_non_axial == 0
            and contaminated_axial == contaminated
            and np.all(np.logical_or(~mask, axial))
        )
        audit = {
            "sweep": sweep, "level": level, "stress": stress,
            "geometry_seed": geometry_seed, "sensor_seed": sensor_seed,
            "process_seed": process_seed, **common_checksums,
            "stressed_observation_checksum": observation_checksum(stressed),
            "stress_checksum": str(np.asarray(stressed["stress_checksum"]).item()),
            "plane_points_world_stressed_checksum": stressed_plane_checksum(stressed),
            "contaminated_measurement_count": contaminated,
            "stress_active_frame_count": int(np.count_nonzero(np.any(mask, axis=1))),
            "selected_patch_count": int(np.asarray(stressed["selected_axial_patch_ids"]).size),
            "contaminated_axial_support_count": contaminated_axial,
            "contaminated_non_axial_support_count": contaminated_non_axial,
            "axial_support_mask_list_checksum": canonical_array_sequence_sha256(
                [axial[index] for index in range(axial.shape[0])]
            ),
            "contamination_mask_list_checksum": canonical_array_sequence_sha256(
                [mask[index] for index in range(mask.shape[0])]
            ),
            "axial_only": axial_only,
        }
        audit["external_stress_valid"] = bool(
            (
                stress == "clean" and contaminated == 0
                and contaminated_axial == 0 and contaminated_non_axial == 0 and axial_only
            )
            or (
                stress == "coherent_subhuber_slip" and contaminated > 0
                and contaminated_axial == contaminated and contaminated_non_axial == 0
                and audit["stress_active_frame_count"] > 0 and axial_only
            )
        )
        key = (sweep, level, geometry_seed, sensor_seed, process_seed, stress)
        output[key] = {
            "sequence_id": str(spec["sequence_id"]), "observations": stressed,
            "motion": motion, "stress_audit": audit, **common_checksums,
            "stressed_observation_checksum": audit["stressed_observation_checksum"],
            "plane_points_world_stressed_checksum": audit[
                "plane_points_world_stressed_checksum"
            ],
            "stress_checksum": audit["stress_checksum"],
            "contaminated_measurement_count": audit["contaminated_measurement_count"],
            "stress_active_frame_count": audit["stress_active_frame_count"],
        }
    return output


def _case_summary(plan: Mapping[str, Any], merged: Sequence[Mapping[str, Any]], metrics: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        **{field: plan[field] for field in (
            "case_id", "sweep", "level", "stress", "geometry_seed", "sensor_seed", "process_seed", "method"
        )},
        "frame_count": len(merged),
        "valid_innovation_frame_count": sum(int(bool(row["weak_innovation_valid"])) for row in merged),
        "window_ready_frame_count": sum(int(bool(row["window_ready"])) for row in merged),
        "stress_active_frame_count": sum(int(bool(row["stress_active"])) for row in merged),
        **{field: float(metrics[field]) for field in (
            "axis_rmse", "axis_mae", "strong_translation_rmse", "orientation_rmse_rad", "trajectory_rmse_3d", "final_axis_error_abs"
        )},
        "median_abs_weak_innovation_z_huber": _finite_median([abs(float(row["weak_innovation_z_huber"])) for row in merged]),
        "median_huber_window_mean": _finite_median([row["huber_window_mean"] for row in merged]),
        "max_abs_huber_cusum_signed": _finite_max_abs([row["huber_cusum_signed"] for row in merged]),
        "max_huber_same_sign_run_length": max(int(row["huber_max_same_sign_run_length"]) for row in merged),
        "median_full_update_weak_abs_m": _finite_median([row["full_update_weak_abs_m"] for row in merged]),
        "median_applied_update_weak_abs_m": _finite_median([row["applied_update_weak_abs_m"] for row in merged]),
        "median_axis_abs_error_reduction_m": _finite_median([row["axis_abs_error_reduction_m"] for row in merged]),
        "fraction_axis_error_reduced": float(np.mean([float(row["axis_abs_error_reduction_m"]) > 0.0 for row in merged])),
        "median_huber_outlier_ratio": _finite_median([row["huber_outlier_ratio"] for row in merged]),
        "median_contaminated_subhuber_ratio": _finite_median([row["contaminated_subhuber_ratio"] for row in merged]),
        "median_contaminated_huber_downweighted_ratio": _finite_median([row["contaminated_huber_downweighted_ratio"] for row in merged]),
    }


def _load_and_validate_config(root: Path) -> Mapping[str, Any]:
    config = load_yaml(root / "configs/stage2_failure/day11b_replay.yaml")
    expected = {
        "mode": "day11b_locked_deterministic_replay",
        "schema_version": DAY11B_RUN_SCHEMA_VERSION,
        "methods": ["huber_full", "huber_projected_gain"],
        "replay_stress_regimes": ["clean", "coherent_subhuber_slip"],
        "allowed_stage2c_stress_regimes": ["clean", "coherent_subhuber_slip", "gross_outlier_control"],
        "expected_replay_count": 8, "logging_equivalence_tolerance": 1.0e-12,
        "replay_for_diagnosis_only": True, "replay_is_independent_test": False,
        "replay_is_representative": False, "replay_used_for_threshold_selection": False,
        "replay_used_for_stage2_gate": False, "generate_figures": False,
        "create_threshold": False, "compute_auroc": False, "compute_fpr": False,
        "compute_f1": False, "compute_detection_delay": False,
        "fast_lio2_integrated": False,
    }
    for field, value in expected.items():
        if config.get(field) != value or type(config.get(field)) is not type(value):
            raise ValueError(f"Day 11B config field changed: {field}")
    return config


def _scene_checksum(sequence_dir: Path) -> str:
    digest = hashlib.sha256()
    for name in ("gt.tum", "axis.csv", "planes.csv", "scene_metadata.json"):
        digest.update(name.encode("utf-8"))
        digest.update(sha256_file(sequence_dir / name).encode("ascii"))
    return digest.hexdigest()


def _historical_hashes(root: Path) -> Mapping[str, str]:
    return {path: compute_directory_hash(root / path) for path in HISTORICAL_ARTIFACT_PATHS}


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON mapping: {path}")
    return value


def _git_branch(root: Path) -> str:
    return subprocess.check_output(["git", "branch", "--show-current"], cwd=str(root), text=True).strip()


def _git_rev_parse(root: Path, revision: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", revision], cwd=str(root), text=True
    ).strip()


def _git_is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=str(root), check=False,
    ).returncode == 0


def _reject_v1_output_path(root: Path, result_dir: Path) -> None:
    frozen = (Path(root).resolve() / DAY11B_V1_RUN_RELATIVE).resolve()
    if Path(result_dir).resolve() == frozen:
        raise ValueError("Day 11B v2 may not write to the frozen v1 output directory")


def _finite_values(values: Sequence[Any]) -> np.ndarray:
    array = np.asarray([float(value) for value in values], dtype=float)
    return array[np.isfinite(array)]


def _finite_median(values: Sequence[Any]) -> float:
    array = _finite_values(values)
    return float(np.median(array)) if array.size else float("nan")


def _finite_max_abs(values: Sequence[Any]) -> float:
    array = _finite_values(values)
    return float(np.max(np.abs(array))) if array.size else float("nan")
