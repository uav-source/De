from pathlib import Path

import pytest

from capture_range.day2_protocol import (
    load_effective_day2_protocol,
    stable_nonzero_effect_sign,
)


ROOT = Path(__file__).resolve().parents[1]


def test_only_six_predeclared_scene_direction_strata_are_allowed():
    contract = load_effective_day2_protocol(ROOT).amendment[
        "full_vs_frozen_stable_sign_resolution"
    ]
    strata = {
        (row["scene_variant"], direction)
        for row in contract["predeclared_comparison_strata"]
        for direction in row["direction_ids"]
    }

    assert strata == {
        ("END_FACE_TRANSITION_WEAK", "pos_x"),
        ("END_FACE_TRANSITION_WEAK", "neg_x"),
        ("END_FACE_TRANSITION_ABSENT", "pos_x"),
        ("END_FACE_TRANSITION_ABSENT", "neg_x"),
        ("REPEATED_STRUCTURE", "pos_x"),
        ("REPEATED_STRUCTURE", "neg_x"),
    }
    assert contract["value_gate"] == {
        "evaluated_without_posthoc_direction_selection": True,
        "pass_if_any_predeclared_stratum_passes_exact_or_curve_effect": True,
        "require_stable_sign_and_magnitude": True,
        "if_no_stratum_has_enough_eligible_blocks": False,
    }


@pytest.mark.parametrize(
    ("effects", "expected"),
    [
        ((0.1, 0.2, 0.3, 0.4, 0.5, -0.1), 1),
        ((-0.1, -0.2, -0.3, -0.4, -0.5, 0.1), -1),
        ((0.1, 0.2, 0.3, 0.4, -0.5, -0.6), None),
        ((0.1, 0.2, 0.3, 0.4, None, None), None),
    ],
)
def test_stable_sign_requires_the_same_nonzero_sign_in_five_of_six_blocks(
    effects, expected
):
    assert stable_nonzero_effect_sign(
        effects,
        blocks_per_stratum=6,
        minimum_same_nonzero_sign_blocks=5,
        zero_tolerance=1.0e-12,
    ) == expected


def test_exact_d50_and_curve_effect_contracts_keep_sign_and_magnitude_together():
    contract = load_effective_day2_protocol(ROOT).amendment[
        "full_vs_frozen_stable_sign_resolution"
    ]

    assert contract["exact_d50_effect"] == {
        "signed_effect_formula": "d50_full_minus_d50_frozen",
        "zero_tolerance_m": 1.0e-12,
        "stable_sign_rule": {
            "blocks_per_stratum": 6,
            "minimum_same_nonzero_sign_blocks": 5,
        },
        "magnitude_statistic": (
            "median_absolute_relative_d50_difference_over_exact_pairs"
        ),
        "magnitude_threshold": 0.20,
        "minimum_exact_pair_blocks": 4,
    }
    curve = contract["recovery_curve_effect"]
    assert curve["signed_effect_formula"] == (
        "trapezoidal_integral_over_amplitude_of_P_full_minus_P_frozen"
    )
    assert curve["stable_sign_rule"] == {
        "blocks_per_stratum": 6,
        "minimum_same_nonzero_sign_blocks": 5,
    }
    assert curve["magnitude_statistic"] == (
        "median_over_blocks_of_maximum_absolute_probability_gap"
    )
    assert curve["magnitude_threshold"] == 0.25
    assert curve["minimum_eligible_blocks"] == 5


def test_d50_zero_tolerance_never_counts_a_numerical_zero_as_a_sign():
    assert stable_nonzero_effect_sign(
        (1.0e-13, 1.0e-13, 1.0e-13, 1.0e-13, 1.0e-13, 1.0),
        blocks_per_stratum=6,
        minimum_same_nonzero_sign_blocks=5,
        zero_tolerance=1.0e-12,
    ) is None
