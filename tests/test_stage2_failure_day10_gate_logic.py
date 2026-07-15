import copy

import pytest

from eval.stage2_failure_day10 import evaluate_day10_gate


def _passing_metrics():
    values = {
        "git_status_clean_at_start": True,
        "output_schema_pass": True,
        "static_audit_pass": True,
        "gt_removed_run_succeeded": True,
        "gt_access_sentinel_run_succeeded": True,
        "gt_poisoned_run_succeeded": True,
        "gt_permuted_run_succeeded": True,
        "filesystem_sandbox_pass": True,
        "output_byte_identical": True,
        "invalid_reset_expected_counts_match": True,
        "invalid_reset_cusum_reset_match": True,
        "invalid_reset_end_to_end_pass": True,
        "historical_artifacts_unchanged": True,
        "gt_file_required": False,
        "fake_gt_file_affected_output": False,
        "reserved_test_run_performed": False,
        "formal_stage2c_rerun_performed": False,
        "representative_stage2c_seed_replayed": False,
        "detection_threshold_created": False,
        "auroc_computed": False,
        "fpr_computed": False,
        "f1_computed": False,
        "detection_delay_computed": False,
        "fast_lio2_integrated": False,
        "invalid_reset_fixture_row_count": 11,
        "invalid_reset_count": 1,
        "online_equivalence_comparison_count": 1,
        "window_equivalence_comparison_count": 1,
    }
    for name in [
        "nonfinite_violation_count",
        "forbidden_import_count",
        "forbidden_signature_parameter_count",
        "forbidden_online_schema_field_count",
        "ast_parse_failure_count",
        "gt_field_access_attempt_count",
        "online_equivalence_failure_count",
        "online_checksum_mismatch_count",
        "online_record_checksum_mismatch_count",
        "window_equivalence_failure_count",
        "window_record_checksum_mismatch_count",
        "no_gt_subprocess_return_code",
        "fake_gt_subprocess_return_code",
    ]:
        values[name] = 0
    for name in [
        "online_max_trajectory_difference",
        "online_max_covariance_difference",
        "online_max_applied_delta_difference",
        "online_max_full_delta_difference",
        "online_max_delta_difference",
    ]:
        values[name] = 0.0
    return values


@pytest.mark.parametrize(
    ("name", "failing_value"),
    [
        ("static_audit_pass", False),
        ("gt_field_access_attempt_count", 1),
        ("online_checksum_mismatch_count", 1),
        ("online_record_checksum_mismatch_count", 1),
        ("window_record_checksum_mismatch_count", 1),
        ("filesystem_sandbox_pass", False),
        ("invalid_reset_end_to_end_pass", False),
        ("historical_artifacts_unchanged", False),
        ("git_status_clean_at_start", False),
    ],
)
def test_day10_gate_rejects_each_required_failure(name, failing_value):
    metrics = copy.deepcopy(_passing_metrics())
    assert evaluate_day10_gate(metrics) is True
    metrics[name] = failing_value
    assert evaluate_day10_gate(metrics) is False
