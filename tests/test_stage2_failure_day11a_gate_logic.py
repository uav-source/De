import pytest

from eval.stage2_failure_day11a import evaluate_day11a_gate


def passing_values():
    return {
        "git_status_clean_at_start": True,
        "git_status_clean_at_lock": True,
        "day10_precondition_pass": True,
        "head_descends_from_day10_checkpoint": True,
        "stage2c_source_verified": True,
        "seed_source_consistency_pass": True,
        "stress_source_validation_pass": True,
        "day11b_replay_matches_historical_test_stress": True,
        "lock_roundtrip_pass": True,
        "selection_reproducibility_pass": True,
        "candidate_order_independence_pass": True,
        "forbidden_dependency_audit_pass": True,
        "historical_artifacts_unchanged": True,
        "recovery_audit_pass": False,
        "history_trial_tables_available": False,
        "selection_used_metrics": False,
        "selection_used_innovation": False,
        "selection_used_cusum": False,
        "selection_used_gt_error": False,
        "selection_used_plot_visibility": False,
        "selection_used_manual_override": False,
        "selection_used_random_sampling": False,
        "stress_name_alias_used": False,
        "legacy_stage2b_stress_name_used": False,
        "gross_outlier_control_replayed": False,
        "replay_performed": False,
        "estimator_imported": False,
        "gt_evaluator_imported": False,
        "window_statistics_imported": False,
        "figures_generated": False,
        "threshold_created": False,
        "auroc_computed": False,
        "fpr_computed": False,
        "f1_computed": False,
        "fast_lio2_integrated": False,
        "ast_parse_failure_count": 0,
        "forbidden_import_count": 0,
        "forbidden_selection_parameter_count": 0,
        "forbidden_runtime_call_count": 0,
        "candidate_duplicate_count": 0,
        "geometry_selected_row_count": 1,
        "observation_selected_row_count": 1,
        "expected_day11b_method_replay_count": 8,
    }


def test_day11a_gate_accepts_only_the_complete_lock_contract():
    assert evaluate_day11a_gate(passing_values()) is True


@pytest.mark.parametrize(
    ("field", "failure_value"),
    [
        ("day10_precondition_pass", False),
        ("git_status_clean_at_start", False),
        ("stage2c_source_verified", False),
        ("seed_source_consistency_pass", False),
        ("candidate_duplicate_count", 1),
        ("geometry_selected_row_count", 0),
        ("observation_selected_row_count", 2),
        ("forbidden_dependency_audit_pass", False),
        ("replay_performed", True),
        ("figures_generated", True),
        ("threshold_created", True),
        ("selection_used_manual_override", True),
        ("historical_artifacts_unchanged", False),
        ("stress_name_alias_used", True),
        ("legacy_stage2b_stress_name_used", True),
        ("gross_outlier_control_replayed", True),
        ("day11b_replay_matches_historical_test_stress", False),
        ("expected_day11b_method_replay_count", 10),
    ],
)
def test_any_gate_violation_refuses_day11b(field, failure_value):
    values = passing_values()
    values[field] = failure_value
    assert evaluate_day11a_gate(values) is False
