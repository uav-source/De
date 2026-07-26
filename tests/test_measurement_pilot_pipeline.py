import math

import pytest

from eval.measurement_real_analysis import (
    binary_ranking_metrics,
    evaluate_pilot_gates,
    maximum_consecutive_true,
    summary_statistics,
)


def test_measurement_statistics_and_binary_metrics_are_reproducible():
    summary = summary_statistics([1, 2, 3, 4])
    assert summary["median"] == 2.5
    assert summary["iqr"] == 1.5
    perfect = binary_ranking_metrics([1, 1, 0, 0], [4, 3, 2, 1])
    assert perfect["auroc"] == 1.0
    assert perfect["pr_auc_average_precision"] == 1.0
    assert maximum_consecutive_true([False, True, True, False, True]) == 2


def test_scientific_gate_requires_reliable_frames_to_be_more_accurate():
    inputs = {
        "python311_full_pytest_pass": True,
        "bag_validation_pass": True,
        "point_time_unit_pass": True,
        "extrinsic_direction_pass": True,
        "reference_input_count": 0,
        "same_call_mutation_count": 0,
        "detector_feedback_count": 0,
        "frozen_mismatch_count": 0,
        "nonfinite_output_count": 0,
        "fastlio2_crash_count": 0,
        "valid_detector_ratio": 0.99,
        "detector_core_mean_ms": 1.0,
        "total_added_q95_ms": 5.0,
        "frozen_intervals_available": True,
        "same_input_all_metrics": True,
        "structural_direction_median_deg": 20.0,
        "reliable_direction_median_deg": 25.0,
        "unreliable_direction_median_deg": 15.0,
        "odi_auroc": 0.8,
        "odi_spearman_rho": math.nan,
        "control_trigger_ratio": 0.1,
        "control_max_consecutive_triggers": 2,
    }
    gates = evaluate_pilot_gates(inputs)
    assert gates["engineering_gate_pass"] is True
    assert gates["runtime_gate_target_pass"] is True
    assert gates["scientific_pilot_gate_pass"] is False
    assert gates["SECOND_DATASET_EXPANSION_AUTHORIZED"] is False


def test_odi_effectiveness_accepts_frozen_auroc_or_absolute_correlation():
    result = binary_ranking_metrics([1, 1, 0, 0], [4.0, 3.0, 2.0, 1.0])
    assert result["auroc"] == pytest.approx(1.0)
