from pathlib import Path

import pytest

from capture_range.day2_protocol import (
    load_effective_day2_protocol,
    resolve_cv_value,
)


ROOT = Path(__file__).resolve().parents[1]


def test_zero_mean_cv_is_null_ineligible_and_still_reports_standard_deviation():
    result = resolve_cv_value(
        finite_mean_d50=0.0,
        bootstrap_standard_deviation=0.004,
        uncensored_fraction=1.0,
    )

    assert result["cv"] is None
    assert result["eligible"] is False
    assert result["reason"] == "ZERO_MEAN_D50"
    assert result["bootstrap_standard_deviation"] == 0.004


def test_cv_requires_both_uncensored_fraction_and_strictly_positive_mean():
    insufficient = resolve_cv_value(
        finite_mean_d50=0.1,
        bootstrap_standard_deviation=0.01,
        uncensored_fraction=0.799,
    )
    eligible = resolve_cv_value(
        finite_mean_d50=0.1,
        bootstrap_standard_deviation=0.01,
        uncensored_fraction=0.80,
    )

    assert insufficient["cv"] is None
    assert insufficient["eligible"] is False
    assert insufficient["reason"] == "INSUFFICIENT_UNCENSORED_FRACTION"
    assert eligible["cv"] == pytest.approx(0.1)
    assert eligible["eligible"] is True
    assert eligible["reason"] == "ELIGIBLE"


def test_right_censoring_and_aggregate_cv_gate_rules_are_frozen():
    contract = load_effective_day2_protocol(ROOT).amendment[
        "repeatability_cv_resolution"
    ]

    assert contract["bootstrap_d50_eligibility"] == {
        "minimum_uncensored_fraction": 0.80,
        "finite_mean_required": True,
        "mean_d50_strictly_greater_than_m": 1.0e-12,
    }
    assert contract["zero_mean_rule"] == {
        "cv_value": None,
        "eligible_for_cv": False,
        "reason_code": "ZERO_MEAN_D50",
        "report_bootstrap_standard_deviation": True,
    }
    assert contract["right_censored_rule"] == {
        "do_not_impute_finite_values": True,
        "report_uncensored_fraction": True,
    }
    assert contract["aggregate_gate"] == {
        "eligible_pair_denominator": (
            "all_translation_scene_direction_pairs_with_at_least_one_exact_observed_d50"
        ),
        "eligible_fraction_min": 0.70,
        "statistic": "median_cv_over_eligible_pairs",
        "median_cv_max": 0.20,
        "if_denominator_is_zero": "fail",
    }
