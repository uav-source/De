import copy

import pytest

from eval.stage2_failure_day11b_v2_schema import evaluate_day11b_v2_gate


def _passing():
    values = {
        "git_status_clean_at_start": True,
        "head_descends_from_day11b_v1_checkpoint": True,
        "case_lock_verification_pass": True,
        "historical_artifacts_unchanged": True,
        "day11b_v1_result_tree_unchanged": True,
        "v1_v2_replay_plan_byte_identical": True,
        "axial_only_audit_pass": True,
        "DAY11B_V1_RUNTIME_RESULT": "PASS",
        "DAY11B_V1_PROVENANCE_COMPLETE": False,
        "DAY11B_V2_RUNTIME_RESULT": "PASS",
        "method_list": ["huber_full", "huber_projected_gain"],
        "replay_stress_list": ["clean", "coherent_subhuber_slip"],
        "expected_replay_count": 8, "completed_replay_count": 8,
        "strategy_chain_comparison_count": 8, "v1_v2_case_comparison_count": 8,
        "contaminated_measurement_count": 4, "contaminated_axial_support_count": 4,
        "v1_v2_max_numeric_difference": 0.0,
        "logging_max_trajectory_difference": 0.0,
        "logging_max_covariance_difference": 0.0,
        "logging_max_applied_delta_difference": 0.0,
        "logging_max_full_delta_difference": 0.0,
        "STAGE2_GATE": "INCOMPLETE", "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED",
        "RISK_WARNING_AUTHORIZED": False, "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
        "gross_outlier_control_replayed": False, "stress_name_alias_used": False,
        "legacy_stage2b_stress_name_used": False, "figures_generated": False,
        "threshold_created": False, "auroc_computed": False, "fpr_computed": False,
        "f1_computed": False, "detection_delay_computed": False,
        "fast_lio2_integrated": False,
    }
    for field in (
        "strategy_chain_mismatch_count", "contaminated_non_axial_support_count",
        "points_lidar_method_pair_mismatch_count", "normals_world_method_pair_mismatch_count",
        "R_diag_method_pair_mismatch_count", "points_lidar_clean_stress_mismatch_count",
        "normals_world_clean_stress_mismatch_count", "R_diag_clean_stress_mismatch_count",
        "v1_v2_failure_count", "v1_v2_key_mismatch_count",
        "logging_equivalence_failure_count", "logging_checksum_mismatch_count",
        "gt_field_access_attempt_count", "solver_failure_count", "pairing_violation_count",
        "duplicate_frame_key_count", "missing_frame_key_count", "nonfinite_violation_count",
        "clean_contaminated_measurement_count", "incomplete_sequence_count",
        "stress_mechanism_failure_count",
    ):
        values[field] = 0
    return values


def test_v2_gate_passing_fixture_passes():
    assert evaluate_day11b_v2_gate(_passing()) is True


@pytest.mark.parametrize("field", [
    "strategy_chain_mismatch_count", "contaminated_non_axial_support_count",
    "points_lidar_method_pair_mismatch_count", "normals_world_method_pair_mismatch_count",
    "R_diag_method_pair_mismatch_count", "points_lidar_clean_stress_mismatch_count",
    "normals_world_clean_stress_mismatch_count", "R_diag_clean_stress_mismatch_count",
    "v1_v2_failure_count", "v1_v2_key_mismatch_count",
])
def test_any_provenance_mismatch_fails_gate(field):
    values = _passing()
    values[field] = 1
    assert evaluate_day11b_v2_gate(values) is False


def test_gross_control_replay_and_nonidentical_plan_fail_gate():
    values = _passing()
    values["gross_outlier_control_replayed"] = True
    assert evaluate_day11b_v2_gate(values) is False
    values = _passing()
    values["v1_v2_replay_plan_byte_identical"] = False
    assert evaluate_day11b_v2_gate(values) is False
