import pytest

from eval.stage2_failure_day11b_schema import evaluate_day11b_gate


def passing_values():
    values = {
        "git_status_clean_at_start": True, "head_descends_from_day11a_checkpoint": True,
        "case_lock_verification_pass": True, "case_selection_reproducibility_pass": True,
        "historical_artifacts_unchanged": True, "replay_for_diagnosis_only": True,
        "method_list": ["huber_full", "huber_projected_gain"],
        "replay_stress_list": ["clean", "coherent_subhuber_slip"],
        "expected_replay_count": 8, "completed_replay_count": 8,
        "logging_equivalence_comparison_count": 8,
        "case_summary_row_count": 8, "pairing_group_count": 6,
        "coherent_contaminated_measurement_count": 1,
        "coherent_stress_active_frame_count": 1,
        "online_row_count": 8, "gt_row_count": 8, "window_row_count": 8,
        "stress_trace_row_count": 8, "merged_row_count": 8,
        "logging_max_trajectory_difference": 0.0,
        "logging_max_covariance_difference": 0.0,
        "logging_max_applied_delta_difference": 0.0,
        "logging_max_full_delta_difference": 0.0,
        "STAGE2_GATE": "INCOMPLETE", "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED",
        "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
    }
    for field in (
        "online_estimator_received_gt", "window_statistics_read_gt",
        "gross_outlier_control_replayed", "stress_name_alias_used",
        "legacy_stage2b_stress_name_used", "historical_trial_tables_available",
        "historical_metric_equivalence_performed", "new_seed_used",
        "full_reserved_test_suite_rerun", "new_reserved_test_namespace_consumed",
        "replay_is_independent_test", "replay_is_representative",
        "replay_used_for_threshold_selection", "replay_used_for_stage2_gate",
        "figures_generated", "threshold_created", "auroc_computed", "fpr_computed",
        "f1_computed", "detection_delay_computed", "fast_lio2_integrated",
    ):
        values[field] = False
    for field in (
        "case_lock_field_mismatch_count", "case_lock_hash_mismatch_count",
        "gt_field_access_attempt_count", "logging_equivalence_failure_count",
        "logging_checksum_mismatch_count", "pairing_violation_count",
        "duplicate_frame_key_count", "missing_frame_key_count", "nonfinite_violation_count",
        "solver_failure_count", "clean_contaminated_measurement_count",
        "incomplete_sequence_count", "stress_mechanism_failure_count",
    ):
        values[field] = 0
    return values


def test_passing_gate_fixture_passes():
    assert evaluate_day11b_gate(passing_values()) is True


@pytest.mark.parametrize(
    "field",
    [
        "git_status_clean_at_start", "case_lock_verification_pass",
        "historical_artifacts_unchanged", "replay_for_diagnosis_only",
    ],
)
def test_required_true_gate_fields_fail_when_false(field):
    values = passing_values()
    values[field] = False
    assert evaluate_day11b_gate(values) is False


@pytest.mark.parametrize(
    "field",
    [
        "historical_metric_equivalence_performed", "replay_is_representative",
        "online_estimator_received_gt", "replay_used_for_stage2_gate",
    ],
)
def test_forbidden_claims_fail_gate(field):
    values = passing_values()
    values[field] = True
    assert evaluate_day11b_gate(values) is False
