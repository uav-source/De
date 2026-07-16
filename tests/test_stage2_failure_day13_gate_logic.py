from eval.stage2_failure_day13_schema import evaluate_day13_gate


def _manifest():
    value = {
        "schema_version": "stage2_failure_day13_v1", "method_list": ["huber_full"], "stress_list": ["clean", "coherent_subhuber_slip", "gross_outlier_control"], "sweep_list": ["geometry", "observation", "open_control"], "primary_statistic": "huber_cusum_max", "threshold_quantile": 0.9, "threshold_rule": "nearest_rank", "threshold_operator": ">", "calibration_expected_trial_count": 260, "calibration_completed_trial_count": 260, "evaluation_expected_trial_count": 520, "evaluation_completed_trial_count": 520, "calibration_geometry_seed_count": 5, "evaluation_geometry_seed_count": 10, "calibration_sensor_seed_count": 2, "evaluation_sensor_seed_count": 2, "calibration_process_seed_count": 2, "evaluation_process_seed_count": 2, "historical_seed_overlap_count": 0, "calibration_evaluation_overlap_count": 0, "new_seed_duplicate_count": 0, "gt_field_access_attempt_count": 0, "solver_failure_count": 0, "pairing_violation_count": 0, "logging_equivalence_failure_count": 0, "duplicate_frame_key_count": 0, "missing_frame_key_count": 0, "nonfinite_violation_count": 0, "gross_control_case_count": 240, "new_diagnostic_seed_namespace_used": True, "new_reserved_test_namespace_consumed": False, "diagnostic_operating_threshold_created": True, "stage3_detection_threshold_created": False, "threshold_used_for_stage2_gate_decision": False, "threshold_used_for_day14_review_only": True, "best_statistic_selected": False, "best_method_selected": False, "evaluation_used_for_retuning": False, "stage2_final_decision_made": False, "day11_seed_used": False, "reserved_test_run_performed": False, "formal_stage2c_rerun_performed": False, "STAGE2_GATE": "INCOMPLETE", "STAGE3_GATE": "NOT_STARTED", "COHERENT_BIAS_DETECTABLE": "UNDETERMINED", "RISK_WARNING_AUTHORIZED": False, "FAST_LIO2_INTEGRATION_AUTHORIZED": False, "PUBLIC_DISCLOSURE_AUTHORIZED": False,
    }
    for field in ("day12_precondition_pass", "git_status_clean_at_design", "git_status_clean_at_calibration_lock", "git_status_clean_at_evaluation_start", "head_equals_calibration_lock_at_evaluation_start", "design_lock_committed_before_calibration", "calibration_lock_committed_before_evaluation", "calibration_evaluation_disjoint", "seed_exclusion_audit_pass", "threshold_matches_calibration_lock", "threshold_unchanged_by_evaluation", "geometry_block_bootstrap_pass", "fpr_geometry_block_bootstrap_pass", "gross_excluded_from_auroc_fpr", "open_control_reported_separately", "all_failed_trials_retained", "historical_artifacts_unchanged", "day11b_v2_results_unchanged", "day12_v3_results_unchanged", "output_schema_pass"):
        value[field] = True
    for field in ("historical_seed_source_count", "calibration_score_count", "geometry_positive_frame_count", "geometry_negative_frame_count", "observation_positive_frame_count", "observation_negative_frame_count", "gross_active_frame_count"):
        value[field] = 1
    for field in ("threshold_value", "calibration_empirical_fpr", "primary_geometry_auroc", "primary_observation_auroc", "clean_all_fpr", "weak_clean_fpr", "open_control_fpr", "geometry_positive_effect_ratio", "observation_positive_effect_ratio"):
        value[field] = 0.5
    for prefix in ("primary_geometry", "primary_observation"):
        value[f"{prefix}_valid_bootstrap_count"] = 5000
        value[f"{prefix}_invalid_bootstrap_count"] = 0
    return value


def test_engineering_gate_ignores_scientific_target_values():
    assert evaluate_day13_gate(_manifest()) is True


def test_selection_retuning_stage2_decision_or_method_change_fails_gate():
    for field, bad in (("best_statistic_selected", True), ("evaluation_used_for_retuning", True), ("STAGE2_GATE", "PASS"), ("method_list", ["huber_projected_gain"]), ("primary_statistic", "abs_huber_window_mean")):
        value = _manifest()
        value[field] = bad
        assert evaluate_day13_gate(value) is False
