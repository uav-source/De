from eval.stage2_failure_day13_statistics import (
    calibrate_diagnostic_threshold,
    nearest_rank_threshold,
    threshold_false_positive_rate,
)
from eval.stage2_failure_day13_schema import validate_calibration_lock
import pytest


def test_nearest_rank_90th_percentile_and_strict_operator():
    assert nearest_rank_threshold(range(1, 11), 0.90) == 9.0
    result = threshold_false_positive_rate([8, 9, 10], 9.0)
    assert result["false_positive_frame_count"] == 1
    rows = [{"role": "calibration", "stress": "clean", "stat_input_valid": True, "window_ready": True, "primary_score": x} for x in range(1, 11)]
    lock = calibrate_diagnostic_threshold(rows)
    assert lock["threshold_value"] == 9.0
    assert lock["threshold_comparison_operator"] == ">"


def test_calibration_lock_rejects_greater_equal_operator():
    lock = {
        "schema_version": "stage2_failure_day13_calibration_lock_v1",
        "primary_statistic": "huber_cusum_max",
        "eligibility_rule": "stat_input_valid and window_ready and isfinite(huber_cusum_max)",
        "threshold_quantile": 0.9, "threshold_quantile_rule": "nearest_rank",
        "threshold_comparison_operator": ">=", "evaluation_started_at_lock": False,
        "stage3_threshold": False, "threshold_for_diagnostic_fpr_only": True,
        "calibration_score_count": 1, "threshold_value": 1.0,
        "calibration_empirical_fpr": 0.0, "git_status_clean_at_calibration_lock": True,
    }
    for field in ("design_lock_sha256", "seed_manifest_sha256", "trial_plan_sha256", "analysis_plan_sha256", "calibration_manifest_sha256", "calibration_frame_scores_sha256", "evaluation_seed_hash", "analysis_code_sha256", "config_sha256"):
        lock[field] = "0" * 64
    with pytest.raises(ValueError):
        validate_calibration_lock(lock)
