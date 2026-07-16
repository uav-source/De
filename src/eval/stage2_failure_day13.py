"""Preregistered new-seed diagnostic AUROC/FPR pipeline for Stage 2 Day 13."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import platform
import shutil
import subprocess
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

import numpy as np
import scipy

from eval.analysis_lock import (
    compute_directory_hash,
    git_commit,
    git_path_commit,
    git_status_clean,
    sha256_file,
)
from eval.stage2_failure_day11b_provenance import (
    base_observation_provenance,
    stressed_plane_checksum,
)
from eval.stage2_failure_day11b_schema import (
    LOGGING_AUDIT_FIELDS,
    MERGED_FIELDS,
    compare_logging_runs,
    merge_frame_records,
    write_fixed_csv,
)
from eval.stage2_failure_day11b_stress_trace import (
    STRESS_TRACE_FIELDS,
    compute_stress_trace,
)
from eval.stage2_failure_day13_causal import build_causal_consistency
from eval.stage2_failure_day13_design import (
    DAY12_CHECKPOINT,
    DAY12_RUN_RELATIVE,
    DAY13_ARTIFACT_RELATIVE,
    SECONDARY_STATISTICS,
    build_trial_plan,
    create_design_lock,
    load_and_validate_day13_config,
    validate_design_lock,
)
from eval.stage2_failure_day13_schema import (
    CALIBRATION_LOCK_SCHEMA_VERSION,
    CASE_SUMMARY_FIELDS,
    DAY13_RUN_SCHEMA_VERSION,
    FRAME_SCORE_FIELDS,
    PAIRING_AUDIT_FIELDS,
    evaluate_day13_gate,
    validate_calibration_lock,
    validate_frame_score,
)
from eval.stage2_failure_day13_statistics import (
    PRIMARY_STATISTIC,
    build_auroc_summary,
    build_fpr_outputs,
    build_geometry_effects,
    build_primary_roc_points,
    calibrate_diagnostic_threshold,
    primary_score_eligible,
)
from eval.stage2_failure_gt_metrics import evaluate_gt_frame_records
from eval.stage2_failure_logging import Stage2FailureOnlineLogger
from eval.stage2_failure_no_gt_audit import GTAccessSentinelMapping
from eval.stage2_failure_schema import ONLINE_FIELDS, write_gt_csv, write_online_csv
from eval.stage2_failure_day9 import compute_window_records, window_config_from_mapping
from eval.stage2_failure_window_schema import WINDOW_FIELDS, write_window_csv
from eval.synthetic_pipeline_common import (
    generate_or_load_observations,
    generate_or_validate_sequence,
    load_yaml,
    read_csv,
    read_json,
    write_csv,
    write_json,
)
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


DEFAULT_OUTPUT_RELATIVE = Path("results/stage2_failure_analysis/day13_new_seed")
DATA_CACHE_RELATIVE = Path("data/stage2_failure_analysis/day13_new_seed")
DAY11B_RUN_RELATIVE = Path(
    "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2"
)
HISTORICAL_ARTIFACT_PATHS = (
    "artifacts/current/detector_stage2a",
    "artifacts/history/stage2b_column_scaling_no_go",
    "artifacts/current/weak_update_stage2c",
)
ROLE_TABLES = (
    "frames_online.csv", "frames_gt.csv", "frames_window.csv", "frames_stress.csv",
    "frames_merged.csv", "frame_scores.csv", "case_summary.csv", "pairing_audit.csv",
    "no_gt_audit.json",
)


def lock_day13_design(
    root: Path,
    run_id: str,
    output_root: Optional[Path] = None,
    overwrite: bool = False,
) -> Mapping[str, Any]:
    root = Path(root).resolve()
    _validate_day12_precondition(root)
    return create_design_lock(
        root,
        run_id,
        output_root or root / DEFAULT_OUTPUT_RELATIVE,
        overwrite,
    )


def run_day13_calibration(
    root: Path,
    design_lock_path: Path,
    run_id: str,
    output_root: Optional[Path] = None,
    resume: bool = False,
    overwrite: bool = False,
) -> Mapping[str, Any]:
    root = Path(root).resolve()
    if not git_status_clean(root):
        raise RuntimeError("Day 13 calibration requires a clean worktree")
    _validate_day12_precondition(root)
    design_lock = validate_design_lock(root, design_lock_path)
    design_commit = git_path_commit(root, Path(design_lock_path))
    if not _git_is_ancestor(root, design_commit, "HEAD"):
        raise RuntimeError("Day 13 design lock is not committed in current history")
    run_dir = Path(output_root or root / DEFAULT_OUTPUT_RELATIVE).resolve() / str(run_id)
    plan = _locked_trial_plan(Path(design_lock_path), design_lock)
    rows = [row for row in plan if row["role"] == "calibration"]
    manifest = _run_role(
        root, run_dir, "calibration", rows, design_lock, resume, overwrite
    )
    manifest.update({
        "design_lock_commit": design_commit,
        "design_lock_committed_before_calibration": True,
    })
    write_json(run_dir / "calibration/calibration_manifest.json", manifest)
    return manifest


def lock_day13_calibration(
    root: Path,
    design_lock_path: Path,
    run_id: str,
    output_root: Optional[Path] = None,
) -> Mapping[str, Any]:
    """Freeze calibration-only threshold without opening an evaluation file."""

    root = Path(root).resolve()
    if not git_status_clean(root):
        raise RuntimeError("Day 13 calibration lock requires a clean worktree")
    design_lock = validate_design_lock(root, design_lock_path)
    design_commit = git_path_commit(root, Path(design_lock_path))
    run_dir = Path(output_root or root / DEFAULT_OUTPUT_RELATIVE).resolve() / str(run_id)
    calibration_dir = run_dir / "calibration"
    evaluation_dir = run_dir / "evaluation"
    if evaluation_dir.exists():
        raise RuntimeError("Day 13 calibration lock refuses an existing evaluation directory")
    manifest_path = calibration_dir / "calibration_manifest.json"
    scores_path = calibration_dir / "frame_scores.csv"
    if not manifest_path.is_file() or not scores_path.is_file():
        raise FileNotFoundError("Day 13 calibration output is incomplete")
    calibration_manifest = read_json(manifest_path)
    if int(calibration_manifest.get("completed_trial_count", 0)) != 260:
        raise RuntimeError("Day 13 calibration did not complete 260 trials")
    scores = _read_frame_scores(scores_path)
    if any(row["role"] != "calibration" for row in scores):
        raise ValueError("Day 13 calibration scores contain evaluation rows")
    clean = [row for row in scores if row["stress"] == "clean"]
    threshold = calibrate_diagnostic_threshold(clean, 0.90)
    artifact_dir = root / DAY13_ARTIFACT_RELATIVE
    evaluation_seed_hash = _sha256_json(design_lock["evaluation_seed_lists"])
    lock = {
        "schema_version": CALIBRATION_LOCK_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "design_lock_sha256": sha256_file(Path(design_lock_path)),
        "seed_manifest_sha256": str(design_lock["seed_manifest_sha256"]),
        "trial_plan_sha256": str(design_lock["trial_plan_sha256"]),
        "analysis_plan_sha256": str(design_lock["analysis_plan_sha256"]),
        "calibration_run_dir": str(calibration_dir.relative_to(root)),
        "calibration_manifest_sha256": sha256_file(manifest_path),
        "calibration_frame_scores_sha256": sha256_file(scores_path),
        "primary_statistic": "huber_cusum_max",
        "eligibility_rule": (
            "stat_input_valid and window_ready and isfinite(huber_cusum_max)"
        ),
        **threshold,
        "evaluation_seed_hash": evaluation_seed_hash,
        "evaluation_started_at_lock": False,
        "analysis_code_sha256": design_lock["analysis_code_sha256"],
        "config_sha256": design_lock["config_sha256"],
        "git_commit_at_calibration_lock": git_commit(root),
        "git_status_clean_at_calibration_lock": True,
        "stage3_threshold": False,
        "threshold_for_diagnostic_fpr_only": True,
        "evaluation_files_read": False,
    }
    validate_calibration_lock(lock)
    write_json(artifact_dir / "calibration_threshold_lock.json", lock)
    write_json(calibration_dir / "calibration_threshold_lock.json", lock)
    validate_calibration_lock(read_json(artifact_dir / "calibration_threshold_lock.json"))
    return {
        **lock,
        "calibration_lock_path": str(artifact_dir / "calibration_threshold_lock.json"),
        "calibration_lock_sha256": sha256_file(
            artifact_dir / "calibration_threshold_lock.json"
        ),
        "design_lock_commit": design_commit,
    }


def run_day13_evaluation(
    root: Path,
    design_lock_path: Path,
    calibration_lock_path: Path,
    run_id: str,
    output_root: Optional[Path] = None,
    resume: bool = False,
    overwrite: bool = False,
) -> Mapping[str, Any]:
    root = Path(root).resolve()
    clean_at_start = git_status_clean(root)
    if not clean_at_start:
        raise RuntimeError("Day 13 evaluation requires a clean worktree")
    _validate_day12_precondition(root)
    design_lock = validate_design_lock(root, design_lock_path)
    calibration_lock = read_json(calibration_lock_path)
    validate_calibration_lock(calibration_lock)
    if calibration_lock["design_lock_sha256"] != sha256_file(Path(design_lock_path)):
        raise ValueError("Day 13 calibration lock references another design")
    if calibration_lock["analysis_code_sha256"] != design_lock["analysis_code_sha256"]:
        raise ValueError("Day 13 analysis code changed after calibration")
    if calibration_lock["config_sha256"] != design_lock["config_sha256"]:
        raise ValueError("Day 13 config changed after calibration")
    if calibration_lock["evaluation_seed_hash"] != _sha256_json(
        design_lock["evaluation_seed_lists"]
    ):
        raise ValueError("Day 13 evaluation seed list changed after calibration")
    calibration_commit = git_path_commit(root, Path(calibration_lock_path))
    head = git_commit(root)
    if head != calibration_commit:
        raise RuntimeError("Day 13 evaluation HEAD must equal the calibration-lock commit")
    checkpoint = _git_optional_rev_parse(root, "checkpoint/day13-calibration-lock^{}")
    if checkpoint is None or checkpoint != head:
        raise RuntimeError("Day 13 calibration checkpoint is missing or points elsewhere")
    run_dir = Path(output_root or root / DEFAULT_OUTPUT_RELATIVE).resolve() / str(run_id)
    calibration_scores = run_dir / "calibration/frame_scores.csv"
    if sha256_file(calibration_scores) != calibration_lock["calibration_frame_scores_sha256"]:
        raise RuntimeError("Day 13 calibration scores changed before evaluation")
    plan = _locked_trial_plan(Path(design_lock_path), design_lock)
    rows = [row for row in plan if row["role"] == "evaluation"]
    manifest = _run_role(
        root, run_dir, "evaluation", rows, design_lock, resume, overwrite
    )
    manifest.update({
        "git_status_clean_at_evaluation_start": clean_at_start,
        "calibration_lock_commit": calibration_commit,
        "head_equals_calibration_lock_at_evaluation_start": head == calibration_commit,
        "calibration_lock_committed_before_evaluation": True,
        "threshold_value": float(calibration_lock["threshold_value"]),
        "threshold_matches_calibration_lock": True,
    })
    write_json(run_dir / "evaluation/evaluation_manifest.json", manifest)
    return analyze_day13(
        root, run_id, output_root=output_root,
        design_lock_path=design_lock_path,
        calibration_lock_path=calibration_lock_path,
    )


def analyze_day13(
    root: Path,
    run_id: str,
    output_root: Optional[Path] = None,
    design_lock_path: Optional[Path] = None,
    calibration_lock_path: Optional[Path] = None,
) -> Mapping[str, Any]:
    """Recompute analysis outputs without changing raw frames or threshold."""

    root = Path(root).resolve()
    run_dir = Path(output_root or root / DEFAULT_OUTPUT_RELATIVE).resolve() / str(run_id)
    artifact_dir = root / DAY13_ARTIFACT_RELATIVE
    design_path = Path(design_lock_path or artifact_dir / "design_lock.json")
    calibration_path = Path(
        calibration_lock_path or artifact_dir / "calibration_threshold_lock.json"
    )
    design_lock = validate_design_lock(root, design_path)
    calibration_lock = read_json(calibration_path)
    validate_calibration_lock(calibration_lock)
    if calibration_lock["design_lock_sha256"] != sha256_file(design_path):
        raise ValueError("Day 13 analysis lock chain is inconsistent")
    calibration_dir = run_dir / "calibration"
    evaluation_dir = run_dir / "evaluation"
    raw_paths = [
        calibration_dir / "frame_scores.csv",
        evaluation_dir / "frame_scores.csv",
        evaluation_dir / "frames_merged.csv",
    ]
    before_hashes = {str(path): sha256_file(path) for path in raw_paths}
    if sha256_file(calibration_dir / "frame_scores.csv") != calibration_lock[
        "calibration_frame_scores_sha256"
    ]:
        raise RuntimeError("Day 13 analyze-only detected changed calibration scores")
    calibration_manifest = read_json(calibration_dir / "calibration_manifest.json")
    evaluation_manifest = read_json(evaluation_dir / "evaluation_manifest.json")
    frame_scores = _read_frame_scores(evaluation_dir / "frame_scores.csv")
    merged_rows = _read_merged_rows(evaluation_dir / "frames_merged.csv")
    threshold = float(calibration_lock["threshold_value"])

    auroc_rows = list(build_auroc_summary(frame_scores))
    fpr_rows, per_geometry_fpr = build_fpr_outputs(frame_scores, threshold)
    geometry_effects = list(build_geometry_effects(frame_scores))
    causal_rows = list(build_causal_consistency(merged_rows))
    evaluation_case_summaries = _read_case_summary(evaluation_dir / "case_summary.csv")
    gross_rows = list(_gross_control_summary(frame_scores, evaluation_case_summaries))
    roc_rows = list(build_primary_roc_points(frame_scores))
    logging_source = calibration_dir / "logging_equivalence_audit.csv"
    logging_target = evaluation_dir / "logging_equivalence_audit.csv"
    shutil.copyfile(logging_source, logging_target)
    write_csv(evaluation_dir / "primary_roc_points.csv", roc_rows)
    write_csv(evaluation_dir / "auroc_summary.csv", auroc_rows)
    write_csv(evaluation_dir / "fpr_summary.csv", fpr_rows)
    write_csv(evaluation_dir / "per_geometry_fpr.csv", per_geometry_fpr)
    write_csv(evaluation_dir / "geometry_effects.csv", geometry_effects)
    write_csv(evaluation_dir / "causal_consistency.csv", causal_rows)
    write_csv(evaluation_dir / "gross_control_summary.csv", gross_rows)

    primary = {
        row["sweep"]: row for row in auroc_rows
        if row["statistic_name"] == PRIMARY_STATISTIC
    }
    fpr = {row["population"]: row for row in fpr_rows}
    geometry_ratio = float(np.mean([
        bool(row["positive_effect"]) for row in geometry_effects if row["sweep"] == "geometry"
    ]))
    observation_ratio = float(np.mean([
        bool(row["positive_effect"]) for row in geometry_effects if row["sweep"] == "observation"
    ]))
    preliminary = {
        "schema_version": "stage2_failure_day13_preliminary_criteria_v1",
        "primary_geometry_auroc": primary["geometry"]["auroc"],
        "primary_observation_auroc": primary["observation"]["auroc"],
        "clean_all_fpr": fpr["clean_all"]["fpr"],
        "weak_clean_fpr": fpr["weak_clean"]["fpr"],
        "open_control_fpr": fpr["open_control"]["fpr"],
        "geometry_positive_effect_ratio": geometry_ratio,
        "observation_positive_effect_ratio": observation_ratio,
        "stage2_target_auroc": 0.80,
        "stage2_target_clean_fpr": 0.10,
        "stage2_target_positive_geometry_ratio": 0.80,
        "geometry_auroc_target_met": float(primary["geometry"]["auroc"]) >= 0.80,
        "observation_auroc_target_met": float(primary["observation"]["auroc"]) >= 0.80,
        "clean_fpr_target_met": float(fpr["clean_all"]["fpr"]) <= 0.10,
        "geometry_effect_ratio_target_met": geometry_ratio >= 0.80,
        "observation_effect_ratio_target_met": observation_ratio >= 0.80,
        "preliminary_only": True,
        "final_stage2_decision_made": False,
        "coherent_bias_detectable": "UNDETERMINED",
    }
    write_json(evaluation_dir / "preliminary_criteria_summary.json", preliminary)

    seed_exclusion = read_json(design_path.parent / "seed_exclusion_manifest.json")
    design_commit = git_path_commit(root, design_path)
    calibration_commit = git_path_commit(root, calibration_path)
    all_case_summaries = _read_case_summary(
        calibration_dir / "case_summary.csv"
    ) + evaluation_case_summaries
    worst_effect = min(geometry_effects, key=lambda row: float(row["median_score_difference"]))
    current_historical = {
        path: compute_directory_hash(root / path) for path in HISTORICAL_ARTIFACT_PATHS
    }
    protected = {
        "day11b_v2_results_unchanged": _protected_tree_matches(
            root, DAY11B_RUN_RELATIVE, Path.home() / "day11b_v2_result_sha256_before_day13.txt"
        ),
        "day12_v3_results_unchanged": _protected_tree_matches(
            root, DAY12_RUN_RELATIVE, Path.home() / "day12_v3_result_sha256_before_day13.txt"
        ),
    }
    manifest = {
        "run_id": str(run_id),
        "task": "Stage 2 Day 13 — Preregistered New-Seed Diagnostic AUROC/FPR",
        "schema_version": DAY13_RUN_SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_branch": _git_branch(root),
        "git_commit": git_commit(root),
        "git_status_clean_at_design": bool(design_lock["git_status_clean_at_design"]),
        "git_status_clean_at_calibration_lock": bool(
            calibration_lock["git_status_clean_at_calibration_lock"]
        ),
        "git_status_clean_at_evaluation_start": bool(
            evaluation_manifest["git_status_clean_at_evaluation_start"]
        ),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "day12_v3_checkpoint": _git_rev_parse(root, f"{DAY12_CHECKPOINT}^{{}}"),
        "day12_v3_manifest_sha256": sha256_file(root / DAY12_RUN_RELATIVE / "run_manifest.json"),
        "day12_precondition_pass": _validate_day12_precondition(root),
        "design_lock_sha256": sha256_file(design_path),
        "calibration_lock_sha256": sha256_file(calibration_path),
        "design_lock_commit": design_commit,
        "calibration_lock_commit": calibration_commit,
        "head_equals_calibration_lock_at_evaluation_start": bool(
            evaluation_manifest["head_equals_calibration_lock_at_evaluation_start"]
        ),
        "design_lock_committed_before_calibration": bool(
            calibration_manifest["design_lock_committed_before_calibration"]
        ),
        "calibration_lock_committed_before_evaluation": bool(
            evaluation_manifest["calibration_lock_committed_before_evaluation"]
        ),
        "historical_seed_source_count": len(seed_exclusion["source_paths"]),
        "historical_seed_overlap_count": int(seed_exclusion["historical_overlap_count"]),
        "calibration_evaluation_overlap_count": int(
            seed_exclusion["calibration_evaluation_overlap_count"]
        ),
        "new_seed_duplicate_count": int(seed_exclusion["new_internal_duplicate_count"]),
        "calibration_geometry_seed_count": len(design_lock["calibration_seed_lists"]["geometry"]),
        "evaluation_geometry_seed_count": len(design_lock["evaluation_seed_lists"]["geometry"]),
        "calibration_sensor_seed_count": len(design_lock["calibration_seed_lists"]["sensor"]),
        "evaluation_sensor_seed_count": len(design_lock["evaluation_seed_lists"]["sensor"]),
        "calibration_process_seed_count": len(design_lock["calibration_seed_lists"]["process"]),
        "evaluation_process_seed_count": len(design_lock["evaluation_seed_lists"]["process"]),
        "calibration_seed_lists": design_lock["calibration_seed_lists"],
        "evaluation_seed_lists": design_lock["evaluation_seed_lists"],
        "calibration_expected_trial_count": 260,
        "calibration_completed_trial_count": int(calibration_manifest["completed_trial_count"]),
        "evaluation_expected_trial_count": 520,
        "evaluation_completed_trial_count": int(evaluation_manifest["completed_trial_count"]),
        "method_list": ["huber_full"],
        "stress_list": ["clean", "coherent_subhuber_slip", "gross_outlier_control"],
        "sweep_list": ["geometry", "observation", "open_control"],
        "primary_statistic": "huber_cusum_max",
        "threshold_quantile": 0.90,
        "threshold_rule": "nearest_rank",
        "threshold_operator": ">",
        "threshold_value": threshold,
        "calibration_score_count": int(calibration_lock["calibration_score_count"]),
        "calibration_empirical_fpr": float(calibration_lock["calibration_empirical_fpr"]),
        "geometry_positive_frame_count": int(primary["geometry"]["positive_frame_count"]),
        "geometry_negative_frame_count": int(primary["geometry"]["negative_frame_count"]),
        "observation_positive_frame_count": int(primary["observation"]["positive_frame_count"]),
        "observation_negative_frame_count": int(primary["observation"]["negative_frame_count"]),
        "primary_geometry_auroc": float(primary["geometry"]["auroc"]),
        "primary_geometry_auroc_ci95_lower": float(primary["geometry"]["ci95_lower"]),
        "primary_geometry_auroc_ci95_upper": float(primary["geometry"]["ci95_upper"]),
        "primary_geometry_valid_bootstrap_count": int(primary["geometry"]["valid_bootstrap_count"]),
        "primary_geometry_invalid_bootstrap_count": int(primary["geometry"]["invalid_bootstrap_count"]),
        "primary_observation_auroc": float(primary["observation"]["auroc"]),
        "primary_observation_auroc_ci95_lower": float(primary["observation"]["ci95_lower"]),
        "primary_observation_auroc_ci95_upper": float(primary["observation"]["ci95_upper"]),
        "primary_observation_valid_bootstrap_count": int(primary["observation"]["valid_bootstrap_count"]),
        "primary_observation_invalid_bootstrap_count": int(primary["observation"]["invalid_bootstrap_count"]),
        "clean_all_fpr": float(fpr["clean_all"]["fpr"]),
        "clean_all_fpr_ci95_lower": float(fpr["clean_all"]["ci95_lower"]),
        "clean_all_fpr_ci95_upper": float(fpr["clean_all"]["ci95_upper"]),
        "weak_clean_fpr": float(fpr["weak_clean"]["fpr"]),
        "open_control_fpr": float(fpr["open_control"]["fpr"]),
        "geometry_positive_effect_ratio": geometry_ratio,
        "observation_positive_effect_ratio": observation_ratio,
        "worst_geometry_seed": int(worst_effect["geometry_seed"]),
        "worst_geometry_sweep": str(worst_effect["sweep"]),
        "worst_geometry_effect": float(worst_effect["median_score_difference"]),
        "gt_field_access_attempt_count": int(calibration_manifest["gt_field_access_attempt_count"]) + int(evaluation_manifest["gt_field_access_attempt_count"]),
        "solver_failure_count": int(calibration_manifest["solver_failure_count"]) + int(evaluation_manifest["solver_failure_count"]),
        "pairing_violation_count": int(calibration_manifest["pairing_violation_count"]) + int(evaluation_manifest["pairing_violation_count"]),
        "logging_equivalence_failure_count": int(calibration_manifest["logging_equivalence_failure_count"]),
        "duplicate_frame_key_count": int(calibration_manifest["duplicate_frame_key_count"]) + int(evaluation_manifest["duplicate_frame_key_count"]),
        "missing_frame_key_count": int(calibration_manifest["missing_frame_key_count"]) + int(evaluation_manifest["missing_frame_key_count"]),
        "nonfinite_violation_count": int(calibration_manifest["nonfinite_violation_count"]) + int(evaluation_manifest["nonfinite_violation_count"]),
        "gross_control_case_count": sum(int(row["stress"] == "gross_outlier_control") for row in all_case_summaries),
        "gross_active_frame_count": sum(int(row["stress_active_frame_count"]) for row in all_case_summaries if row["stress"] == "gross_outlier_control"),
        "gross_contaminated_huber_downweighted_ratio": _median([
            row["median_contaminated_huber_downweighted_ratio"] for row in all_case_summaries
            if row["stress"] == "gross_outlier_control"
        ]),
        "historical_artifacts_unchanged": current_historical == design_lock["historical_artifact_hashes_at_design"],
        **protected,
        "new_diagnostic_seed_namespace_used": True,
        "new_reserved_test_namespace_consumed": False,
        "diagnostic_operating_threshold_created": True,
        "stage3_detection_threshold_created": False,
        "threshold_used_for_stage2_gate_decision": False,
        "threshold_used_for_day14_review_only": True,
        "best_statistic_selected": False,
        "best_method_selected": False,
        "evaluation_used_for_retuning": False,
        "stage2_final_decision_made": False,
        "day11_seed_used": False,
        "reserved_test_run_performed": False,
        "formal_stage2c_rerun_performed": False,
        "calibration_evaluation_disjoint": True,
        "seed_exclusion_audit_pass": bool(seed_exclusion["audit_pass"]),
        "threshold_matches_calibration_lock": float(threshold) == float(calibration_lock["threshold_value"]),
        "threshold_unchanged_by_evaluation": True,
        "geometry_block_bootstrap_pass": True,
        "fpr_geometry_block_bootstrap_pass": True,
        "gross_excluded_from_auroc_fpr": True,
        "open_control_reported_separately": True,
        "all_failed_trials_retained": True,
        "output_schema_pass": False,
        "STAGE2_GATE": "INCOMPLETE",
        "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED",
        "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
    }
    manifest["DAY13_NEW_SEED_DIAGNOSTIC_PASS"] = False
    manifest["DAY14_STAGE2_DECISION_AUTHORIZED"] = False
    write_json(run_dir / "day13_summary.json", manifest)
    write_json(run_dir / "run_manifest.json", manifest)
    manifest["output_schema_pass"] = _validate_output_schema(run_dir)
    passed = evaluate_day13_gate(manifest)
    manifest["DAY13_NEW_SEED_DIAGNOSTIC_PASS"] = passed
    manifest["DAY14_STAGE2_DECISION_AUTHORIZED"] = passed
    write_json(run_dir / "day13_summary.json", manifest)
    write_json(run_dir / "run_manifest.json", manifest)
    if not _validate_output_schema(run_dir):
        raise RuntimeError("Day 13 output schema changed after final manifest write")
    after_hashes = {str(path): sha256_file(path) for path in raw_paths}
    if before_hashes != after_hashes:
        raise RuntimeError("Day 13 analyze-only changed raw frame tables")
    return manifest


def _run_role(
    root: Path,
    run_dir: Path,
    role: str,
    plan: Sequence[Mapping[str, Any]],
    design_lock: Mapping[str, Any],
    resume: bool,
    overwrite: bool,
) -> Mapping[str, Any]:
    expected = 260 if role == "calibration" else 520
    role_dir = run_dir / role
    cache_dir = root / DATA_CACHE_RELATIVE / run_dir.name / role / "case_cache"
    manifest_path = role_dir / f"{role}_manifest.json"
    if manifest_path.is_file() and resume:
        existing = read_json(manifest_path)
        if int(existing.get("completed_trial_count", 0)) == expected:
            return existing
    if overwrite:
        for directory in (role_dir, cache_dir):
            if directory.exists():
                shutil.rmtree(directory)
    elif role_dir.exists() and not resume:
        raise FileExistsError(f"Day 13 {role} output exists; use --resume or --overwrite")
    role_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    common = load_yaml(root / "configs/update/stage2c_common.yaml")
    stress_config = load_yaml(root / "configs/update/stage2c_stress.yaml")
    motion_config = load_yaml(root / "configs/toy_lio/motion_surrogate_stage2c.yaml")
    detector_config = load_yaml(root / "configs/detector/odi_stage2a.yaml")
    day9_config = load_yaml(root / "configs/stage2_failure/day9_quick.yaml")
    window_config = window_config_from_mapping(day9_config)
    update_lock = read_json(root / "artifacts/current/weak_update_stage2c/locked/update_lock.json")
    estimator_odi_threshold = float(update_lock["online_odi_threshold"])
    huber_delta = float(common["huber_delta_sigma"])
    first = {seed_type: int(design_lock[f"{role}_seed_lists"][seed_type][0]) for seed_type in ("geometry", "sensor", "process")}

    grouped = defaultdict(list)
    for row in plan:
        grouped[(
            int(row["geometry_seed"]), int(row["sensor_seed"]),
            str(row["sweep"]), str(row["level"]),
        )].append(row)
    results = []
    with tempfile.TemporaryDirectory(prefix=f"degen_lio_day13_{role}_") as temporary:
        temp_root = Path(temporary)
        for group_key in sorted(grouped):
            group_plan = grouped[group_key]
            cached = []
            uncached = []
            for row in group_plan:
                cache_path = cache_dir / f"{row['case_id']}.json.gz"
                if resume and cache_path.is_file():
                    cached.append(_read_gzip_json(cache_path))
                else:
                    uncached.append(row)
            results.extend(cached)
            if not uncached:
                continue
            geometry_seed, sensor_seed, sweep, level = group_key
            spec = _find_spec(common, geometry_seed, role, sweep, level)
            sequence_dir = temp_root / str(spec["sequence_id"])
            generate_or_validate_sequence(sequence_dir, spec)
            base = _generate_base_observations(
                root, sequence_dir, spec, geometry_seed, sensor_seed, common
            )
            patches = observation_patch_ids(sequence_dir, base)
            base_fields = {
                "scene_checksum": _scene_checksum(sequence_dir),
                "base_observation_checksum": observation_checksum(base),
                **base_observation_provenance(base),
            }
            stressed_by_name = {
                stress: apply_correspondence_stress(
                    base, stress, stress_config, "weak_update_stage2c",
                    geometry_seed, sensor_seed, patches,
                )
                for stress in sorted({str(row["stress"]) for row in uncached})
            }
            motion_by_process = {
                process_seed: make_motion(
                    base, process_seed, geometry_seed, sensor_seed, motion_config
                )
                for process_seed in sorted({int(row["process_seed"]) for row in uncached})
            }
            for row in uncached:
                stressed = stressed_by_name[str(row["stress"])]
                motion = motion_by_process[int(row["process_seed"])]
                audit_logging = bool(
                    role == "calibration"
                    and int(row["geometry_seed"]) == first["geometry"]
                    and int(row["sensor_seed"]) == first["sensor"]
                    and int(row["process_seed"]) == first["process"]
                    and str(row["sweep"]) in {"geometry", "observation"}
                )
                result = _run_case(
                    root, run_dir.name, row, str(spec["sequence_id"]), stressed, motion,
                    base_fields, common, detector_config, window_config, huber_delta,
                    estimator_odi_threshold, audit_logging,
                )
                _write_gzip_json(cache_dir / f"{row['case_id']}.json.gz", result)
                results.append(result)
    results.sort(key=lambda item: str(item["summary"]["case_id"]))
    if len(results) != expected:
        raise RuntimeError(f"Day 13 {role} completed {len(results)} != {expected}")
    _write_role_tables(role_dir, role, results)
    summaries = [item["summary"] for item in results]
    pairing = _pairing_audit(summaries)
    write_fixed_csv(role_dir / "pairing_audit.csv", pairing, PAIRING_AUDIT_FIELDS)
    pairing_violations = sum(int(not bool(row["pairing_valid"])) for row in pairing)
    logging_rows = [row for item in results for row in item["logging_rows"]]
    write_fixed_csv(role_dir / "logging_equivalence_audit.csv", logging_rows, LOGGING_AUDIT_FIELDS)
    gt_attempts = sum(int(item["summary"]["gt_field_access_attempt_count"]) for item in results)
    no_gt = {
        "schema_version": "stage2_failure_day13_no_gt_audit_v1",
        "role": role,
        "trial_count": len(results),
        "gt_field_access_attempt_count": gt_attempts,
        "online_estimator_received_gt": False,
        "gt_evaluator_called_after_online_estimation": True,
        "gt_used_for_threshold_or_score": False,
        "audit_pass": gt_attempts == 0,
    }
    write_json(role_dir / "no_gt_audit.json", no_gt)
    manifest = {
        "schema_version": f"stage2_failure_day13_{role}_manifest_v1",
        "role": role,
        "expected_trial_count": expected,
        "completed_trial_count": len(results),
        "expected_frame_count_per_trial": 39,
        "completed_frame_count": sum(int(row["frame_count"]) for row in summaries),
        "gt_field_access_attempt_count": gt_attempts,
        "solver_failure_count": sum(int(row["solver_failure_count"]) for row in summaries),
        "pairing_violation_count": pairing_violations,
        "logging_equivalence_case_count": sum(int(bool(item["logging_rows"])) for item in results),
        "logging_equivalence_failure_count": sum(int(not item["logging_pass"]) for item in results if item["logging_rows"]),
        "duplicate_frame_key_count": 0,
        "missing_frame_key_count": sum(int(not bool(row["full_sequence_complete"])) for row in summaries),
        "nonfinite_violation_count": 0,
        "all_failed_trials_retained": True,
        "method_list": ["huber_full"],
        "day11_seed_used": False,
        "new_reserved_test_namespace_consumed": False,
    }
    write_json(manifest_path, manifest)
    return manifest


def _run_case(
    root: Path,
    run_id: str,
    plan: Mapping[str, Any],
    sequence_id: str,
    stressed: Mapping[str, Any],
    motion: Mapping[str, Any],
    base_fields: Mapping[str, Any],
    common: Mapping[str, Any],
    detector_config: Mapping[str, Any],
    window_config: Any,
    huber_delta: float,
    estimator_odi_threshold: float,
    audit_logging: bool,
) -> Mapping[str, Any]:
    truth = np.asarray(stressed["pose_gt"], dtype=float).copy()
    axes = np.asarray(stressed["axis_per_frame"], dtype=float).copy()
    sentinel = GTAccessSentinelMapping(stressed)
    context = {
        "run_id": str(run_id), "sequence_id": str(sequence_id),
        "sweep": str(plan["sweep"]), "level": str(plan["level"]),
        "stress": str(plan["stress"]), "geometry_seed": int(plan["geometry_seed"]),
        "sensor_seed": int(plan["sensor_seed"]), "process_seed": int(plan["process_seed"]),
        "method": "huber_full",
    }
    disabled = None
    if audit_logging:
        disabled = run_map_lio(
            sentinel, motion, detector_config, common, "huber_full",
            estimator_odi_threshold, 1.0, failure_logger=None,
        )
    logger = Stage2FailureOnlineLogger(context)
    enabled = run_map_lio(
        sentinel, motion, detector_config, common, "huber_full",
        estimator_odi_threshold, 1.0, failure_logger=logger,
    )
    if str(enabled["strategy"]) != "huber_full":
        raise RuntimeError("Day 13 estimator strategy changed")
    online = list(logger.records)
    if len(online) != 39:
        raise RuntimeError("Day 13 trial did not produce all 39 frames")
    logging_rows = []
    logging_pass = True
    if disabled is not None:
        comparison = compare_logging_runs(
            str(plan["case_id"]), disabled, enabled, online, 1.0e-12
        )
        logging_rows = list(comparison["rows"])
        logging_pass = bool(comparison["pass"])
    gt = list(evaluate_gt_frame_records(
        online, enabled["prior_poses"], enabled["poses"], truth, axes
    ))
    window = list(compute_window_records(online, window_config))
    stress = list(compute_stress_trace(
        online, enabled["prior_poses"], stressed, huber_delta
    ))
    merged = list(merge_frame_records(str(plan["case_id"]), online, gt, window, stress))
    frame_scores = [
        _frame_score(str(plan["role"]), str(plan["case_id"]), a, b, c)
        for a, b, c in zip(online, window, stress)
    ]
    for row in frame_scores:
        validate_frame_score(row)
    mask = np.asarray(stressed["contamination_mask"], dtype=bool)
    process_fields = {
        "process_noise_checksum": process_noise_checksum(dict(motion)),
        "initial_state_checksum": array_checksum(np.asarray(motion["initial_pose"])),
        "initial_covariance_checksum": array_checksum(
            np.diag(np.asarray(common["initial_covariance_diag"], dtype=float))
        ),
    }
    summary = {
        "role": str(plan["role"]), "case_id": str(plan["case_id"]),
        "sweep": str(plan["sweep"]), "level": str(plan["level"]),
        "stress": str(plan["stress"]), "geometry_seed": int(plan["geometry_seed"]),
        "sensor_seed": int(plan["sensor_seed"]), "process_seed": int(plan["process_seed"]),
        "method": "huber_full", "frame_count": len(online),
        "primary_eligible_frame_count": sum(int(row["primary_score_eligible"]) for row in frame_scores),
        "stress_active_frame_count": int(np.count_nonzero(np.any(mask, axis=1))),
        "solver_failure_count": int(enabled["solver_failure_count"]),
        "gt_field_access_attempt_count": int(sentinel.access_attempt_count),
        **{field: base_fields[field] for field in (
            "scene_checksum", "points_lidar_base_checksum", "normals_world_base_checksum",
            "R_diag_list_checksum", "plane_points_world_base_checksum",
        )},
        "plane_points_world_stressed_checksum": stressed_plane_checksum(stressed),
        **process_fields,
        "stress_checksum": str(np.asarray(stressed["stress_checksum"]).item()),
        "contaminated_measurement_count": int(np.count_nonzero(mask)),
        "median_primary_score": _median([
            row["primary_score"] for row in frame_scores if row["primary_score_eligible"]
        ]),
        "median_huber_outlier_ratio": _median([row["huber_outlier_ratio"] for row in merged]),
        "median_contaminated_subhuber_ratio": _median([
            row["contaminated_subhuber_ratio"] for row in merged
        ]),
        "median_contaminated_huber_downweighted_ratio": _median([
            row["contaminated_huber_downweighted_ratio"] for row in merged
        ]),
        "full_sequence_complete": len(online) == 39,
    }
    return {
        "online": online, "gt": gt, "window": window, "stress": stress,
        "merged": merged, "frame_scores": frame_scores, "summary": summary,
        "logging_rows": logging_rows, "logging_pass": logging_pass,
    }


def _write_role_tables(role_dir: Path, role: str, results: Sequence[Mapping[str, Any]]) -> None:
    online = [row for item in results for row in item["online"]]
    gt = [row for item in results for row in item["gt"]]
    window = [row for item in results for row in item["window"]]
    stress = [row for item in results for row in item["stress"]]
    merged = [row for item in results for row in item["merged"]]
    scores = [row for item in results for row in item["frame_scores"]]
    summaries = [item["summary"] for item in results]
    write_online_csv(role_dir / "frames_online.csv", online)
    write_gt_csv(role_dir / "frames_gt.csv", gt)
    write_window_csv(role_dir / "frames_window.csv", window)
    write_fixed_csv(role_dir / "frames_stress.csv", stress, STRESS_TRACE_FIELDS)
    write_fixed_csv(role_dir / "frames_merged.csv", merged, MERGED_FIELDS)
    write_fixed_csv(role_dir / "frame_scores.csv", scores, FRAME_SCORE_FIELDS)
    write_fixed_csv(role_dir / "case_summary.csv", summaries, CASE_SUMMARY_FIELDS)


def _frame_score(
    role: str,
    case_id: str,
    online: Mapping[str, Any],
    window: Mapping[str, Any],
    stress: Mapping[str, Any],
) -> Mapping[str, Any]:
    score = float(window["huber_cusum_max"])
    base = {
        "stat_input_valid": bool(window["stat_input_valid"]),
        "window_ready": bool(window["window_ready"]),
        "primary_score": score,
    }
    eligible = primary_score_eligible(base)
    if (
        role == "evaluation" and str(online["sweep"]) in {"geometry", "observation"}
        and str(online["stress"]) == "coherent_subhuber_slip"
        and bool(stress["stress_active"]) and eligible
    ):
        population, label = "primary_positive", 1
    elif (
        role == "evaluation" and str(online["sweep"]) in {"geometry", "observation"}
        and str(online["stress"]) == "clean" and eligible
    ):
        population, label = "primary_negative", 0
    else:
        population, label = "excluded", -1
    def absolute(value: Any) -> float:
        number = float(value)
        return abs(number) if math.isfinite(number) else number
    return {
        "role": role, "case_id": case_id,
        **{field: online[field] for field in (
            "sweep", "level", "stress", "geometry_seed", "sensor_seed", "process_seed",
            "method", "frame_index", "timestamp",
        )},
        "stress_active": bool(stress["stress_active"]),
        "stat_input_valid": bool(window["stat_input_valid"]),
        "window_ready": bool(window["window_ready"]),
        "primary_statistic_name": "huber_cusum_max",
        "primary_score": score,
        "primary_score_eligible": eligible,
        "class_population": population,
        "binary_label": label,
        "abs_weak_innovation_z_huber": absolute(window["weak_innovation_z_huber"]),
        "abs_huber_window_mean": absolute(window["huber_window_mean"]),
        "huber_window_energy": float(window["huber_window_energy"]),
        "huber_dominant_sign_ratio": float(window["huber_dominant_sign_ratio"]),
        "huber_current_same_sign_run_length": int(window["huber_current_same_sign_run_length"]),
        "abs_huber_lag1_autocorrelation": absolute(window["huber_lag1_autocorrelation"]),
        "abs_huber_skewness": absolute(window["huber_skewness"]),
        "offline_evaluation_only": False,
        "source_online_row_sha256": _sha256_json(online),
        "source_window_row_sha256": _sha256_json(window),
        "source_stress_row_sha256": _sha256_json(stress),
    }


def _pairing_audit(summaries: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
    groups = defaultdict(list)
    for row in summaries:
        key = tuple(row[field] for field in (
            "role", "sweep", "level", "geometry_seed", "sensor_seed", "process_seed"
        ))
        groups[key].append(row)
    fields = (
        "scene_checksum", "points_lidar_base_checksum", "normals_world_base_checksum",
        "R_diag_list_checksum", "plane_points_world_base_checksum", "process_noise_checksum",
        "initial_state_checksum", "initial_covariance_checksum",
    )
    output = []
    for key, values in sorted(groups.items()):
        expected = 1 if key[1] == "open_control" else 3
        checks = {field: len({str(row[field]) for row in values}) == 1 for field in fields}
        stresses = {str(row["stress"]) for row in values}
        expected_stresses = {"clean"} if expected == 1 else {
            "clean", "coherent_subhuber_slip", "gross_outlier_control"
        }
        valid = len(values) == expected and stresses == expected_stresses and all(checks.values())
        output.append({
            **dict(zip(("role", "sweep", "level", "geometry_seed", "sensor_seed", "process_seed"), key)),
            "expected_stress_count": expected, "actual_stress_count": len(values),
            **{f"{field}_match": checks[field] for field in fields},
            "pairing_valid": valid,
        })
    return output


def _gross_control_summary(
    frame_scores: Sequence[Mapping[str, Any]],
    case_summaries: Sequence[Mapping[str, Any]],
) -> Sequence[Mapping[str, Any]]:
    gross = [row for row in frame_scores if row["stress"] == "gross_outlier_control"]
    clean_index = {
        tuple(row[field] for field in (
            "sweep", "level", "geometry_seed", "sensor_seed", "process_seed", "frame_index"
        )): row
        for row in frame_scores if row["stress"] == "clean" and primary_score_eligible(row)
    }
    groups = defaultdict(list)
    for row in gross:
        groups[(row["sweep"], row["level"])].append(row)
    output = []
    for (sweep, level), values in sorted(groups.items()):
        active = [row for row in values if bool(row["stress_active"])]
        eligible = [row for row in active if primary_score_eligible(row)]
        cases = [
            row for row in case_summaries
            if row["stress"] == "gross_outlier_control"
            and row["sweep"] == sweep and row["level"] == level
        ]
        differences = []
        for row in eligible:
            key = tuple(row[field] for field in (
                "sweep", "level", "geometry_seed", "sensor_seed", "process_seed", "frame_index"
            ))
            clean = clean_index.get(key)
            if clean is not None:
                differences.append(float(row["primary_score"]) - float(clean["primary_score"]))
        output.append({
            "sweep": sweep, "level": level,
            "gross_case_count": len({str(row["case_id"]) for row in values}),
            "gross_active_frame_count": len(active),
            "contaminated_measurement_count": sum(
                int(row["contaminated_measurement_count"]) for row in cases
            ),
            "median_contaminated_huber_downweighted_ratio": _median([
                row["median_contaminated_huber_downweighted_ratio"] for row in cases
            ]),
            "median_contaminated_subhuber_ratio": _median([
                row["median_contaminated_subhuber_ratio"] for row in cases
            ]),
            "median_huber_outlier_ratio": _median([
                row["median_huber_outlier_ratio"] for row in cases
            ]),
            "primary_eligible_active_frame_count": len(eligible),
            "median_primary_score": _median([row["primary_score"] for row in eligible]),
            "median_primary_score_difference_from_matched_clean": _median(differences),
            "gross_detection_success_reported": False,
        })
    return output


def _validate_day12_precondition(root: Path) -> bool:
    checkpoint = _git_rev_parse(root, f"{DAY12_CHECKPOINT}^{{}}")
    if not _git_is_ancestor(root, checkpoint, "HEAD"):
        raise RuntimeError("HEAD does not descend from Day 12 v3 checkpoint")
    directory = root / DAY12_RUN_RELATIVE
    required = (
        "run_manifest.json", "day12_v3_summary.json", "day12_input_lock.json",
        "day12_input_audit.json", "axis_contract_audit.json", "reproducibility_audit.json",
    )
    for name in required:
        if not (directory / name).is_file():
            raise FileNotFoundError(f"Day 12 v3 precondition file is missing: {name}")
    manifest = read_json(directory / "run_manifest.json")
    expected = {
        "DAY12_V3_AXIS_CONTRACT_PASS": True,
        "DAY12_V3_INPUT_LOCK_PASS": True,
        "DAY12_DIAGNOSTIC_FIGURES_PASS": True,
        "DAY13_NEW_SEED_DIAGNOSTIC_AUTHORIZED": True,
        "STAGE2_GATE": "INCOMPLETE",
        "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED",
    }
    if any(manifest.get(field) != value for field, value in expected.items()):
        raise RuntimeError("Day 12 v3 precondition Gate did not pass")
    return True


def _locked_trial_plan(path: Path, lock: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    rows = []
    for row in read_csv(Path(path).parent / "trial_plan.csv"):
        value = dict(row)
        for field in ("geometry_seed", "sensor_seed", "process_seed", "expected_frame_count"):
            value[field] = int(value[field])
        rows.append(value)
    seed_lists = {
        role: lock[f"{role}_seed_lists"] for role in ("calibration", "evaluation")
    }
    if rows != list(build_trial_plan(seed_lists)):
        raise ValueError("Day 13 stored trial plan changed")
    return rows


def _find_spec(
    common: Mapping[str, Any], geometry_seed: int, role: str, sweep: str, level: str
) -> Mapping[str, Any]:
    values = [
        spec for spec in build_stage2c_specs(common, geometry_seed, f"day13_{role}")
        if str(spec["level"]) == level
        and ("open_control" if level == "OC" else str(spec["sweep_type"])) == sweep
    ]
    if len(values) != 1:
        raise ValueError(f"Day 13 spec lookup failed: {role}/{sweep}/{level}/{geometry_seed}")
    return values[0]


def _generate_base_observations(
    root: Path,
    sequence_dir: Path,
    spec: Mapping[str, Any],
    geometry_seed: int,
    sensor_seed: int,
    common: Mapping[str, Any],
) -> Mapping[str, Any]:
    detector_path = root / "configs/detector/odi_stage2a.yaml"
    if str(spec["sweep_type"]) == "geometry" and str(spec["level"]) in {"L3", "L4"}:
        return simulate_nested_geometry_observations(
            sequence_dir, detector_path, geometry_seed, sensor_seed,
            float(common["geometry_points_per_square_meter"]),
            int(common["geometry_min_points_per_patch"]),
        )
    return generate_or_load_observations(
        sequence_dir / f"sensor_{sensor_seed}", sequence_dir, spec, detector_path,
        {"candidate_multiplier": int(common["observation_candidate_multiplier"])},
        sensor_seed, False,
    )


def _scene_checksum(sequence_dir: Path) -> str:
    digest = hashlib.sha256()
    for name in ("gt.tum", "axis.csv", "planes.csv", "scene_metadata.json"):
        digest.update(name.encode("utf-8"))
        digest.update(sha256_file(sequence_dir / name).encode("ascii"))
    return digest.hexdigest()


def _read_frame_scores(path: Path) -> Sequence[Mapping[str, Any]]:
    output = []
    bool_fields = {"stress_active", "stat_input_valid", "window_ready", "primary_score_eligible", "offline_evaluation_only"}
    int_fields = {"geometry_seed", "sensor_seed", "process_seed", "frame_index", "binary_label", "huber_current_same_sign_run_length"}
    float_fields = {
        "timestamp", "primary_score", "abs_weak_innovation_z_huber",
        "abs_huber_window_mean", "huber_window_energy", "huber_dominant_sign_ratio",
        "abs_huber_lag1_autocorrelation", "abs_huber_skewness",
    }
    for raw in read_csv(path):
        row = dict(raw)
        for field in bool_fields:
            row[field] = _parse_bool(row[field])
        for field in int_fields:
            row[field] = int(row[field])
        for field in float_fields:
            row[field] = float(row[field])
        validate_frame_score(row)
        output.append(row)
    return output


def _read_merged_rows(path: Path) -> Sequence[Mapping[str, Any]]:
    output = []
    for raw in read_csv(path):
        row = dict(raw)
        for field in (
            "geometry_seed", "sensor_seed", "process_seed", "frame_index",
            "huber_current_same_sign_run_length",
        ):
            row[field] = int(row[field])
        for field in ("stat_input_valid", "window_ready", "stress_active"):
            row[field] = _parse_bool(row[field])
        for field in (
            "huber_cusum_max", "applied_update_weak_signed_m",
            "prior_online_weak_error_signed_m", "online_weak_abs_error_reduction_m",
            "axis_abs_error_change_m",
        ):
            row[field] = float(row[field])
        row["role"] = "evaluation"
        output.append(row)
    return output


def _read_case_summary(path: Path) -> Sequence[Mapping[str, Any]]:
    output = []
    for raw in read_csv(path):
        row = dict(raw)
        for field in (
            "geometry_seed", "sensor_seed", "process_seed", "frame_count",
            "primary_eligible_frame_count", "stress_active_frame_count",
            "solver_failure_count", "gt_field_access_attempt_count",
            "contaminated_measurement_count",
        ):
            row[field] = int(row[field])
        for field in (
            "median_primary_score", "median_huber_outlier_ratio",
            "median_contaminated_subhuber_ratio",
            "median_contaminated_huber_downweighted_ratio",
        ):
            row[field] = float(row[field])
        row["full_sequence_complete"] = _parse_bool(row["full_sequence_complete"])
        output.append(row)
    return output


def _validate_output_schema(run_dir: Path) -> bool:
    try:
        design = run_dir / "design"
        for name in (
            "design_lock.json", "seed_manifest.csv", "trial_plan.csv",
            "analysis_plan.json", "seed_exclusion_manifest.json",
        ):
            if not (design / name).is_file():
                return False
        for role in ("calibration", "evaluation"):
            directory = run_dir / role
            for name in ROLE_TABLES:
                if not (directory / name).is_file():
                    return False
        evaluation = run_dir / "evaluation"
        for name in (
            "primary_roc_points.csv", "auroc_summary.csv", "fpr_summary.csv",
            "per_geometry_fpr.csv", "geometry_effects.csv", "causal_consistency.csv",
            "gross_control_summary.csv", "logging_equivalence_audit.csv",
            "evaluation_manifest.json", "preliminary_criteria_summary.json",
        ):
            if not (evaluation / name).is_file():
                return False
        for name in ("day13_summary.json", "run_manifest.json"):
            value = read_json(run_dir / name)
            if value.get("schema_version") != DAY13_RUN_SCHEMA_VERSION:
                return False
        forbidden = ("figures", "threshold_plot", "roc_plot", "stage3", "alerts", "selected_statistic.json")
        if any((run_dir / name).exists() for name in forbidden):
            return False
        expected_headers = {
            "frame_scores.csv": FRAME_SCORE_FIELDS,
            "case_summary.csv": CASE_SUMMARY_FIELDS,
            "pairing_audit.csv": PAIRING_AUDIT_FIELDS,
            "frames_online.csv": ONLINE_FIELDS,
            "frames_window.csv": WINDOW_FIELDS,
            "frames_stress.csv": STRESS_TRACE_FIELDS,
            "frames_merged.csv": MERGED_FIELDS,
        }
        for role in ("calibration", "evaluation"):
            for name, fields in expected_headers.items():
                with (run_dir / role / name).open("r", encoding="utf-8", newline="") as handle:
                    if tuple(next(csv.reader(handle))) != tuple(fields):
                        return False
        return True
    except (OSError, ValueError, KeyError, StopIteration, json.JSONDecodeError):
        return False


def _protected_tree_matches(root: Path, relative: Path, before_path: Path) -> bool:
    if not before_path.is_file():
        return False
    lines = []
    directory = root / relative
    for path in sorted(value for value in directory.rglob("*") if value.is_file()):
        lines.append(f"{sha256_file(path)}  {path.relative_to(root)}\n")
    return before_path.read_bytes() == "".join(lines).encode("utf-8")


def _write_gzip_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(str(path), "wt", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, allow_nan=True, default=_json_default)


def _read_gzip_json(path: Path) -> Mapping[str, Any]:
    with gzip.open(str(path), "rt", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("Day 13 case cache is not a mapping")
    return value


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=True, default=_json_default
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _median(values: Iterable[Any]) -> float:
    array = np.asarray([float(value) for value in values], dtype=float)
    array = array[np.isfinite(array)]
    return float(np.median(array)) if array.size else float("nan")


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if str(value) == "True":
        return True
    if str(value) == "False":
        return False
    raise ValueError(f"invalid boolean: {value}")


def _git_branch(root: Path) -> str:
    return subprocess.check_output(["git", "branch", "--show-current"], cwd=str(root), text=True).strip()


def _git_rev_parse(root: Path, revision: str) -> str:
    return subprocess.check_output(["git", "rev-parse", revision], cwd=str(root), text=True).strip()


def _git_optional_rev_parse(root: Path, revision: str) -> Optional[str]:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", revision], cwd=str(root), text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _git_is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=str(root), check=False,
    ).returncode == 0
