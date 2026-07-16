"""Frozen schemas and gate logic for Stage 2 Day 11B provenance v2."""

from __future__ import annotations

import math
from typing import Any, Mapping


DAY11B_V2_RUN_SCHEMA_VERSION = "stage2_failure_day11b_run_v2"
DAY11B_V2_STRESS_MECHANISM_AUDIT_FIELDS = (
    "sweep", "level", "stress", "geometry_seed", "sensor_seed", "process_seed",
    "scene_checksum", "base_observation_checksum", "stressed_observation_checksum",
    "stress_checksum", "process_noise_checksum", "initial_state_checksum",
    "initial_covariance_checksum", "contaminated_measurement_count", "stress_active_frame_count",
    "selected_patch_count", "points_lidar_base_checksum", "normals_world_base_checksum",
    "R_diag_list_checksum", "plane_points_world_base_checksum",
    "plane_points_world_stressed_checksum", "points_lidar_frame_count",
    "normals_world_frame_count", "R_diag_frame_count", "plane_points_world_frame_count",
    "contaminated_axial_support_count", "contaminated_non_axial_support_count",
    "axial_support_mask_list_checksum", "contamination_mask_list_checksum",
    "axial_only", "external_stress_valid",
)


def evaluate_day11b_v2_gate(values: Mapping[str, Any]) -> bool:
    required_true = (
        "git_status_clean_at_start", "head_descends_from_day11b_v1_checkpoint",
        "case_lock_verification_pass", "historical_artifacts_unchanged",
        "day11b_v1_result_tree_unchanged", "v1_v2_replay_plan_byte_identical",
        "axial_only_audit_pass",
    )
    zero_fields = (
        "strategy_chain_mismatch_count", "contaminated_non_axial_support_count",
        "points_lidar_method_pair_mismatch_count",
        "normals_world_method_pair_mismatch_count", "R_diag_method_pair_mismatch_count",
        "points_lidar_clean_stress_mismatch_count",
        "normals_world_clean_stress_mismatch_count", "R_diag_clean_stress_mismatch_count",
        "v1_v2_failure_count", "v1_v2_key_mismatch_count",
        "logging_equivalence_failure_count", "logging_checksum_mismatch_count",
        "gt_field_access_attempt_count", "solver_failure_count", "pairing_violation_count",
        "duplicate_frame_key_count", "missing_frame_key_count", "nonfinite_violation_count",
        "clean_contaminated_measurement_count", "incomplete_sequence_count",
        "stress_mechanism_failure_count",
    )
    if not all(values.get(field) is True for field in required_true):
        return False
    if not all(int(values.get(field, -1)) == 0 for field in zero_fields):
        return False
    if values.get("DAY11B_V1_RUNTIME_RESULT") != "PASS":
        return False
    if values.get("DAY11B_V1_PROVENANCE_COMPLETE") is not False:
        return False
    if values.get("DAY11B_V2_RUNTIME_RESULT") != "PASS":
        return False
    if list(values.get("method_list", [])) != ["huber_full", "huber_projected_gain"]:
        return False
    if list(values.get("replay_stress_list", [])) != ["clean", "coherent_subhuber_slip"]:
        return False
    if int(values.get("expected_replay_count", -1)) != 8:
        return False
    if int(values.get("completed_replay_count", -1)) != 8:
        return False
    if int(values.get("strategy_chain_comparison_count", -1)) != 8:
        return False
    if int(values.get("v1_v2_case_comparison_count", -1)) != 8:
        return False
    contaminated = int(values.get("contaminated_measurement_count", 0))
    contaminated_axial = int(values.get("contaminated_axial_support_count", -1))
    if contaminated <= 0 or contaminated_axial != contaminated:
        return False
    for field in (
        "v1_v2_max_numeric_difference", "logging_max_trajectory_difference",
        "logging_max_covariance_difference", "logging_max_applied_delta_difference",
        "logging_max_full_delta_difference",
    ):
        value = float(values.get(field, float("inf")))
        if not math.isfinite(value) or value > 1.0e-12:
            return False
    fixed = {
        "STAGE2_GATE": "INCOMPLETE", "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED", "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
        "gross_outlier_control_replayed": False, "stress_name_alias_used": False,
        "legacy_stage2b_stress_name_used": False, "figures_generated": False,
        "threshold_created": False, "auroc_computed": False, "fpr_computed": False,
        "f1_computed": False, "detection_delay_computed": False,
        "fast_lio2_integrated": False,
    }
    return all(values.get(field) == expected for field, expected in fixed.items())
