from fastlio2_adapter.day6_statistical_characterization import (
    aligned_output_differences,
    summarize_aligned_differences,
)


def output(value):
    return {
        "valid": True,
        "degeneracy_triggered": False,
        "primary_direction_stable": True,
        "actionable_direction": False,
        "odi_trans": value,
        "ais_trans": value,
        "lambda_min_trans": value,
        "condition_number_trans": value,
        "primary_eigengap_ratio": value,
        "primary_weak_direction": [1.0, 0.0, 0.0],
    }


def test_cross_run_statistics_are_descriptive_not_bitwise():
    row = aligned_output_differences(output(1.0), output(2.0))
    summary = summarize_aligned_differences([row])
    assert summary["aligned_record_count"] == 1
    assert (
        summary["difference_quantiles"]["odi_trans_absolute_difference"]["max"]
        == 1.0
    )
    assert summary["valid_agreement_fraction"] == 1.0


def test_cross_run_direction_comparison_is_sign_invariant():
    left = output(1.0)
    right = output(1.0)
    right["primary_weak_direction"] = [-1.0, 0.0, 0.0]
    row = aligned_output_differences(left, right)
    assert row["weak_direction_sign_invariant_angle_deg"] == 0.0
