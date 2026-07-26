from itertools import product
from pathlib import Path

from capture_range.day2_protocol import load_effective_day2_protocol


ROOT = Path(__file__).resolve().parents[1]


def test_each_scene_variant_has_exactly_six_reserved_test_blocks():
    effective = load_effective_day2_protocol(ROOT)
    contract = effective.amendment["test_block_and_scene_aggregation"]
    test_split = effective.base["splits"]["test"]
    blocks = tuple(
        product(test_split["geometry_seeds"], test_split["measurement_seeds"])
    )

    assert contract["test_block_definition"]["fields"] == (
        "scene_id", "scene_variant", "geometry_seed", "measurement_seed",
    )
    assert contract["test_block_definition"]["expected_blocks_per_scene_variant"] == 6
    assert blocks == (
        (1201, 2203), (1201, 2213),
        (1213, 2203), (1213, 2213),
        (1223, 2203), (1223, 2213),
    )


def test_degraded_scene_separation_requires_all_three_frozen_conditions():
    contract = load_effective_day2_protocol(ROOT).amendment[
        "test_block_and_scene_aggregation"
    ]

    assert contract["degraded_scene_variants_for_separation"] == (
        "LONG_CORRIDOR",
        "PARALLEL_WALLS",
        "END_FACE_TRANSITION_WEAK",
        "END_FACE_TRANSITION_ABSENT",
        "REPEATED_STRUCTURE",
    )
    assert contract["scene_variant_separation_pass"] == {
        "median_separation_ratio_lower_bound_min": 0.30,
        "minimum_individual_blocks_meeting_0p30": 4,
        "minimum_blocks_with_uncensored_weak_radius": 4,
        "all_six_blocks_must_be_reported": True,
    }
    assert contract["global_directionality_gate"] == {
        "long_corridor_scene_median_angle_error_deg_max": 10.0,
        "parallel_walls_scene_median_angle_error_deg_max": 10.0,
        "minimum_number_of_degraded_scene_variants_passing_separation": 2,
    }


def test_angle_gate_uses_all_six_blocks_and_never_gt_selects_a_tie():
    accuracy = load_effective_day2_protocol(ROOT).amendment[
        "test_block_and_scene_aggregation"
    ]["scene_variant_direction_accuracy"]

    assert accuracy == {
        "aggregation": "median_over_six_test_blocks",
        "ambiguous_noncollinear_tie_angle_error_deg": 90.0,
        "require_finite_angle_blocks_minimum": 6,
    }
