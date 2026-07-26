from pathlib import Path

from capture_range.day2_protocol import load_effective_day2_protocol


ROOT = Path(__file__).resolve().parents[1]


def test_rich_room_axis_tie_separation_and_block_bootstrap_are_exact():
    contract = load_effective_day2_protocol(ROOT).amendment[
        "rich_room_bootstrap_resolution"
    ]

    assert contract["evaluated_test_blocks"] == 6
    assert contract["evaluated_axes"] == ("x", "y", "z")
    assert contract["per_block_axis_radius"] == (
        "conservative_minimum_of_positive_and_negative_d50"
    )
    assert contract["right_censored_axis_radius_for_ordering"] == "positive_infinity"
    assert contract["minimum_axis_tie"] == {
        "tolerance_m": 1.0e-12,
        "nonunique_minimum_means_no_single_axis_for_that_block": True,
    }
    assert contract["per_block_separation_formula"] == (
        "1 - minimum_axis_radius / median(other_two_axis_lower_bounds)"
    )
    assert contract["bootstrap"] == {
        "unit": "test_block",
        "repetitions": 2000,
        "seed": 161803,
        "resample_six_blocks_with_replacement": True,
        "statistic": "median_separation_over_resampled_blocks",
        "ci_method": "percentile",
        "ci_lower_quantile": 0.025,
    }


def test_rich_room_pseudo_weak_requires_all_four_conditions_and_resolvable_axes():
    contract = load_effective_day2_protocol(ROOT).amendment[
        "rich_room_bootstrap_resolution"
    ]

    assert contract["same_axis_minimum_count"] == {
        "count_only_blocks_with_unique_minimum_axis": True,
        "required_blocks": 5,
    }
    assert contract["pseudo_weak_flag_requires_all"] == (
        "same_unique_axis_is_minimum_in_at_least_five_blocks",
        "scene_median_separation_at_least_0p30",
        "median_minimum_axis_d50_at_most_0p20_m",
        "bootstrap_separation_ci_lower_greater_than_0p20",
    )
    assert contract["if_any_required_axis_radius_is_unresolvable"] == {
        "flag_status": "inconclusive",
        "geometry_rich_control_pass": False,
    }
