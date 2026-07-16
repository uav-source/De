from eval.stage2_failure_day13_correction_schema import (
    CORRECTION_ID,
    CORRECTION_SCHEMA_VERSION,
    evaluate_correction_gate,
)


def _passing_gate_input():
    value = {
        "schema_version": CORRECTION_SCHEMA_VERSION,
        "correction_id": CORRECTION_ID,
        "matching_key_fields": [
            "sweep", "level", "geometry_seed", "sensor_seed", "process_seed",
            "method", "frame_index",
        ],
        "locked_threshold": 13.745952939169019,
        "threshold_unchanged": True,
        "calibration_trial_rerun": False, "evaluation_trial_rerun": False,
        "estimator_invoked": False, "seed_changed": False,
        "stress_changed": False, "statistic_changed": False,
        "threshold_changed": False, "retuning_performed": False,
        "original_geometry_positive_count": 1600,
        "original_geometry_negative_count": 2800,
        "corrected_geometry_positive_count": 1600,
        "corrected_geometry_negative_count": 1600,
        "original_observation_positive_count": 1600,
        "original_observation_negative_count": 2800,
        "corrected_observation_positive_count": 1600,
        "corrected_observation_negative_count": 1600,
        "geometry_missing_match_count": 0, "observation_missing_match_count": 0,
        "duplicate_positive_key_count": 0, "duplicate_clean_key_count": 0,
        "invalid_pair_count": 0, "unpaired_selected_row_count": 0,
        "geometry_excluded_unmatched_clean_count": 1200,
        "observation_excluded_unmatched_clean_count": 1200,
        "primary_geometry_valid_bootstrap_count": 5000,
        "primary_geometry_invalid_bootstrap_count": 0,
        "primary_observation_valid_bootstrap_count": 5000,
        "primary_observation_invalid_bootstrap_count": 0,
        "v1_locked_files_unchanged": True, "v1_raw_inputs_unchanged": True,
        "v1_analysis_outputs_unchanged": True,
        "matched_population_audit_pass": True, "input_immutability_pass": True,
        "bootstrap_pass": True, "fpr_breakdown_pass": True,
        "operating_point_pass": True, "gross_control_reporting_pass": True,
        "output_schema_pass": True, "STAGE2_GATE": "INCOMPLETE",
        "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED",
        "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
        "corrected_geometry_auroc": 0.6,
        "corrected_geometry_ci95_lower": 0.5,
        "corrected_geometry_ci95_upper": 0.7,
        "corrected_observation_auroc": 0.68,
        "corrected_observation_ci95_lower": 0.6,
        "corrected_observation_ci95_upper": 0.75,
        "geometry_locked_threshold_tpr": 0.15,
        "geometry_matched_clean_fpr": 0.09,
        "observation_locked_threshold_tpr": 0.22,
        "observation_matched_clean_fpr": 0.08,
    }
    return value


def test_gate_requires_matched_counts_and_protocol_immutability():
    value = _passing_gate_input()
    assert evaluate_correction_gate(value) is True
    value["corrected_geometry_negative_count"] = 2800
    assert evaluate_correction_gate(value) is False
    value = _passing_gate_input()
    value["v1_analysis_outputs_unchanged"] = False
    assert evaluate_correction_gate(value) is False

