from eval.stage2_failure_day12_schema import evaluate_day12_gate


def _passing():
    values = {
        "git_status_clean_at_start": True, "head_descends_from_day11b_v2_checkpoint": True,
        "day12_input_audit_pass": True, "axial_only_audit_pass": True,
        "repro_plot_data_byte_identical": True, "repro_png_pixel_hash_identical": True,
        "repro_summary_byte_identical": True, "repro_captions_byte_identical": True,
        "day11b_v2_results_unchanged": True, "figures_for_diagnosis_only": True,
        "coherent_shared_sign_pass": True, "historical_artifacts_unchanged": True,
        "expected_case_count": 8, "actual_case_count": 8,
        "day11b_v2_checkpoint_commit": "480960def270d2739a21bfc4967990318d2ed3c3",
        "expected_merged_row_count": 312, "actual_merged_row_count": 312,
        "strategy_chain_comparison_count": 8,
        "method_expanded_contaminated_measurement_count": 872,
        "external_unique_contaminated_measurement_count": 436,
        "method_expanded_stress_active_frame_count": 80,
        "external_unique_stress_active_frame_count": 40, "coherent_burst_count": 2,
        "coherent_burst_lengths": [20, 20], "coherent_offset_abs_m": 0.03,
        "plot_data_file_count": 4, "expected_figure_count": 4,
        "png_figure_count": 4, "pdf_figure_count": 4,
        "STAGE2_GATE": "INCOMPLETE", "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED", "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False, "PUBLIC_DISCLOSURE_AUTHORIZED": False,
    }
    for field in ("strategy_chain_mismatch_count", "duplicate_frame_key_count", "missing_frame_key_count",
                  "case_identity_mismatch_count",
                  "nonfinite_violation_count", "plot_data_audit_failure_count", "source_row_hash_mismatch_count",
                  "source_value_mismatch_count",
                  "unexpected_figure_count", "figure_qc_failure_count", "contaminated_non_axial_support_count",
                  "forbidden_output_count",
                  "points_lidar_mismatch_count", "normals_world_mismatch_count", "R_diag_mismatch_count"):
        values[field] = 0
    for field in ("estimator_replayed", "new_seed_used", "day11b_results_modified",
                  "figure_data_selected_after_viewing", "best_statistic_selected", "best_method_selected",
                  "threshold_created", "threshold_line_drawn", "auroc_computed", "fpr_computed", "f1_computed",
                  "detection_delay_computed", "significance_test_performed", "replay_is_independent_test",
                  "replay_is_representative"):
        values[field] = False
    return values


def test_complete_gate_passes():
    assert evaluate_day12_gate(_passing()) is True


def test_best_statistic_or_representative_claim_fails():
    for field in ("best_statistic_selected", "replay_is_representative", "estimator_replayed"):
        values = _passing(); values[field] = True
        assert evaluate_day12_gate(values) is False


def test_scientific_decision_outputs_fail_gate():
    for field in (
        "threshold_created", "threshold_line_drawn", "auroc_computed",
        "fpr_computed", "f1_computed", "detection_delay_computed",
        "significance_test_performed", "best_method_selected",
    ):
        values = _passing()
        values[field] = True
        assert evaluate_day12_gate(values) is False
