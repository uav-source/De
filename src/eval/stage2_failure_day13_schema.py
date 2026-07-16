"""Validation and engineering Gate policy for Stage 2 Day 13."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


DAY13_RUN_SCHEMA_VERSION = "stage2_failure_day13_v1"
CALIBRATION_LOCK_SCHEMA_VERSION = "stage2_failure_day13_calibration_lock_v1"
FRAME_SCORE_FIELDS = (
    "role", "case_id", "sweep", "level", "stress", "geometry_seed", "sensor_seed",
    "process_seed", "method", "frame_index", "timestamp", "stress_active",
    "stat_input_valid", "window_ready", "primary_statistic_name", "primary_score",
    "primary_score_eligible", "class_population", "binary_label",
    "abs_weak_innovation_z_huber", "abs_huber_window_mean", "huber_window_energy",
    "huber_dominant_sign_ratio", "huber_current_same_sign_run_length",
    "abs_huber_lag1_autocorrelation", "abs_huber_skewness",
    "offline_evaluation_only", "source_online_row_sha256", "source_window_row_sha256",
    "source_stress_row_sha256",
)
PAIRING_AUDIT_FIELDS = (
    "role", "sweep", "level", "geometry_seed", "sensor_seed", "process_seed",
    "expected_stress_count", "actual_stress_count", "scene_checksum_match",
    "points_lidar_base_checksum_match", "normals_world_base_checksum_match",
    "R_diag_list_checksum_match", "plane_points_world_base_checksum_match",
    "process_noise_checksum_match", "initial_state_checksum_match",
    "initial_covariance_checksum_match", "pairing_valid",
)
CASE_SUMMARY_FIELDS = (
    "role", "case_id", "sweep", "level", "stress", "geometry_seed", "sensor_seed",
    "process_seed", "method", "frame_count", "primary_eligible_frame_count",
    "stress_active_frame_count", "solver_failure_count", "gt_field_access_attempt_count",
    "scene_checksum", "points_lidar_base_checksum", "normals_world_base_checksum",
    "R_diag_list_checksum", "plane_points_world_base_checksum",
    "plane_points_world_stressed_checksum", "process_noise_checksum",
    "initial_state_checksum", "initial_covariance_checksum", "stress_checksum",
    "contaminated_measurement_count", "median_primary_score",
    "median_huber_outlier_ratio", "median_contaminated_subhuber_ratio",
    "median_contaminated_huber_downweighted_ratio", "full_sequence_complete",
)


def validate_calibration_lock(lock: Mapping[str, Any]) -> None:
    fixed = {
        "schema_version": CALIBRATION_LOCK_SCHEMA_VERSION,
        "primary_statistic": "huber_cusum_max",
        "eligibility_rule": "stat_input_valid and window_ready and isfinite(huber_cusum_max)",
        "threshold_quantile": 0.90,
        "threshold_quantile_rule": "nearest_rank",
        "threshold_comparison_operator": ">",
        "evaluation_started_at_lock": False,
        "stage3_threshold": False,
        "threshold_for_diagnostic_fpr_only": True,
    }
    for field, value in fixed.items():
        if lock.get(field) != value or type(lock.get(field)) is not type(value):
            raise ValueError(f"Day 13 calibration-lock field changed: {field}")
    hashes = (
        "design_lock_sha256", "seed_manifest_sha256", "trial_plan_sha256",
        "analysis_plan_sha256", "calibration_manifest_sha256",
        "calibration_frame_scores_sha256", "evaluation_seed_hash",
        "analysis_code_sha256", "config_sha256",
    )
    for field in hashes:
        value = str(lock.get(field, ""))
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError(f"invalid Day 13 calibration-lock hash: {field}")
    if int(lock.get("calibration_score_count", 0)) <= 0:
        raise ValueError("Day 13 calibration lock has no eligible clean scores")
    for field in ("threshold_value", "calibration_empirical_fpr"):
        if not math.isfinite(float(lock.get(field, float("nan")))):
            raise ValueError(f"Day 13 calibration-lock field is nonfinite: {field}")
    if not 0.0 <= float(lock["calibration_empirical_fpr"]) <= 1.0:
        raise ValueError("Day 13 calibration empirical FPR is outside [0,1]")
    if not bool(lock.get("git_status_clean_at_calibration_lock")):
        raise ValueError("Day 13 calibration lock was created from a dirty worktree")


def validate_frame_score(row: Mapping[str, Any]) -> None:
    if set(row) != set(FRAME_SCORE_FIELDS):
        raise ValueError("Day 13 frame-score schema changed")
    if str(row["method"]) != "huber_full" or str(row["primary_statistic_name"]) != "huber_cusum_max":
        raise ValueError("Day 13 frame score method/statistic changed")
    if str(row["stress"]) not in {
        "clean", "coherent_subhuber_slip", "gross_outlier_control"
    }:
        raise ValueError("Day 13 frame score has an invalid stress")
    eligible = bool(row["stat_input_valid"]) and bool(row["window_ready"])
    score = float(row["primary_score"])
    eligible = eligible and math.isfinite(score)
    if bool(row["primary_score_eligible"]) != eligible:
        raise ValueError("Day 13 primary eligibility changed")
    label = int(row["binary_label"])
    population = str(row["class_population"])
    if str(row["role"]) == "evaluation" and str(row["sweep"]) in {"geometry", "observation"}:
        if str(row["stress"]) == "coherent_subhuber_slip" and bool(row["stress_active"]) and eligible:
            expected = (1, "primary_positive")
        elif str(row["stress"]) == "clean" and eligible:
            expected = (0, "primary_negative")
        else:
            expected = (-1, "excluded")
    else:
        expected = (-1, "excluded")
    if (label, population) != expected:
        raise ValueError("Day 13 frame-score class population changed")
    if bool(row["offline_evaluation_only"]):
        raise ValueError("online frame scores cannot depend on offline GT")
    for field in (
        "source_online_row_sha256", "source_window_row_sha256", "source_stress_row_sha256"
    ):
        value = str(row[field])
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError(f"invalid Day 13 frame-score row hash: {field}")


def evaluate_day13_gate(manifest: Mapping[str, Any]) -> bool:
    """Engineering completeness only; scientific target values are deliberately absent."""

    exact = {
        "schema_version": DAY13_RUN_SCHEMA_VERSION,
        "method_list": ["huber_full"],
        "stress_list": ["clean", "coherent_subhuber_slip", "gross_outlier_control"],
        "sweep_list": ["geometry", "observation", "open_control"],
        "primary_statistic": "huber_cusum_max",
        "threshold_quantile": 0.90,
        "threshold_rule": "nearest_rank",
        "threshold_operator": ">",
        "calibration_expected_trial_count": 260,
        "calibration_completed_trial_count": 260,
        "evaluation_expected_trial_count": 520,
        "evaluation_completed_trial_count": 520,
        "calibration_geometry_seed_count": 5,
        "evaluation_geometry_seed_count": 10,
        "calibration_sensor_seed_count": 2,
        "evaluation_sensor_seed_count": 2,
        "calibration_process_seed_count": 2,
        "evaluation_process_seed_count": 2,
        "historical_seed_overlap_count": 0,
        "calibration_evaluation_overlap_count": 0,
        "new_seed_duplicate_count": 0,
        "gt_field_access_attempt_count": 0,
        "solver_failure_count": 0,
        "pairing_violation_count": 0,
        "logging_equivalence_failure_count": 0,
        "duplicate_frame_key_count": 0,
        "missing_frame_key_count": 0,
        "nonfinite_violation_count": 0,
        "gross_control_case_count": 240,
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
        "STAGE2_GATE": "INCOMPLETE",
        "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED",
        "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
    }
    if any(manifest.get(field) != value or type(manifest.get(field)) is not type(value) for field, value in exact.items()):
        return False
    required_true = (
        "day12_precondition_pass", "git_status_clean_at_design",
        "git_status_clean_at_calibration_lock", "git_status_clean_at_evaluation_start",
        "head_equals_calibration_lock_at_evaluation_start", "design_lock_committed_before_calibration",
        "calibration_lock_committed_before_evaluation", "calibration_evaluation_disjoint",
        "seed_exclusion_audit_pass", "threshold_matches_calibration_lock",
        "threshold_unchanged_by_evaluation", "geometry_block_bootstrap_pass",
        "fpr_geometry_block_bootstrap_pass", "gross_excluded_from_auroc_fpr",
        "open_control_reported_separately", "all_failed_trials_retained",
        "historical_artifacts_unchanged", "day11b_v2_results_unchanged",
        "day12_v3_results_unchanged", "output_schema_pass",
    )
    if not all(manifest.get(field) is True for field in required_true):
        return False
    required_positive = (
        "historical_seed_source_count", "calibration_score_count",
        "geometry_positive_frame_count", "geometry_negative_frame_count",
        "observation_positive_frame_count", "observation_negative_frame_count",
        "gross_active_frame_count",
    )
    if any(int(manifest.get(field, 0)) <= 0 for field in required_positive):
        return False
    for prefix in ("primary_geometry", "primary_observation"):
        if int(manifest.get(f"{prefix}_valid_bootstrap_count", 0)) != 5000:
            return False
        if int(manifest.get(f"{prefix}_invalid_bootstrap_count", -1)) != 0:
            return False
    for field in (
        "threshold_value", "calibration_empirical_fpr", "primary_geometry_auroc",
        "primary_observation_auroc", "clean_all_fpr", "weak_clean_fpr",
        "open_control_fpr", "geometry_positive_effect_ratio",
        "observation_positive_effect_ratio",
    ):
        try:
            value = float(manifest[field])
        except (KeyError, TypeError, ValueError):
            return False
        if not math.isfinite(value):
            return False
    return True
