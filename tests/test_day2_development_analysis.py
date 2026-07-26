from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from capture_range.capture_radius import (
    capture_radius_from_fitted,
    fit_nonincreasing_isotonic,
)
from capture_range.day2_development_analysis import (
    TRANSLATION_AMPLITUDES_M,
    aggregate_trial_rows,
    bootstrap_full_translation_curve,
    compare_predeclared_full_vs_frozen,
    compute_axis_separation,
)


def _trial_rows(
    *,
    scene: str = "LONG_CORRIDOR",
    geometry_seed: int = 7,
    measurement_seed: int = 11,
    direction_id: str = "pos_x",
    path: str = "full_reassociation",
    successes: list[int] | list[list[bool]],
) -> list[dict[str, object]]:
    if successes and isinstance(successes[0], list):
        matrix = successes
    else:
        matrix = [
            [repeat_index < int(count) for repeat_index in range(5)]
            for count in successes
        ]
    assert len(matrix) == 8 and all(len(row) == 5 for row in matrix)
    rows = []
    block_id = f"{scene}:g{geometry_seed}:m{measurement_seed}"
    for amplitude, outcomes in zip(TRANSLATION_AMPLITUDES_M, matrix):
        for repeat_index, success in enumerate(outcomes):
            rows.append(
                {
                    "block_id": block_id,
                    "scene_variant": scene,
                    "geometry_seed": geometry_seed,
                    "measurement_seed": measurement_seed,
                    "repeat_index": repeat_index,
                    "perturbation_type": "translation",
                    "direction_id": direction_id,
                    "registration_path": path,
                    "amplitude": amplitude,
                    "success": success,
                    "correspondence_checksum_trace": (
                        ["checksum-a", "checksum-b", "checksum-b"]
                        if path == "full_reassociation"
                        else []
                    ),
                }
            )
    return rows


def _step_counts(d50: float | None) -> list[int]:
    if d50 is None:
        return [5] * 8
    index = TRANSLATION_AMPLITUDES_M.index(d50)
    return [5 if position < index else 0 for position in range(8)]


def _axis_curves(
    radii: dict[str, float | None], *, geometry_seed: int
):
    rows = []
    for direction_id, radius in radii.items():
        rows.extend(
            _trial_rows(
                geometry_seed=geometry_seed,
                direction_id=direction_id,
                successes=_step_counts(radius),
            )
        )
    return aggregate_trial_rows(rows)


def test_aggregate_preserves_raw_wilson_isotonic_radii_and_nonmonotonicity():
    rows = _trial_rows(successes=[5, 4, 5, 2, 3, 1, 0, 0])
    curve = aggregate_trial_rows(rows)[0]

    assert curve.key.block.scene_variant == "LONG_CORRIDOR"
    assert curve.repeat_indices == (0, 1, 2, 3, 4)
    assert curve.total_trials == (5,) * 8
    assert curve.raw_probabilities == pytest.approx(
        [1.0, 0.8, 1.0, 0.4, 0.6, 0.2, 0.0, 0.0]
    )
    assert curve.isotonic_probabilities == pytest.approx(
        [1.0, 0.9, 0.9, 0.5, 0.5, 0.2, 0.0, 0.0]
    )
    assert curve.d50 == 0.05
    assert curve.d90 == 0.01
    assert not curve.d50_right_censored
    assert not curve.d90_right_censored
    assert curve.monotonicity.violation_indices == (1, 3)
    assert curve.monotonicity.violation_amplitude_pairs == (
        (0.01, 0.02),
        (0.05, 0.10),
    )
    assert curve.monotonicity.maximum_upward_jump == pytest.approx(0.2)
    for raw, lower, upper in zip(
        curve.raw_probabilities, curve.wilson_lower, curve.wilson_upper
    ):
        assert lower <= raw + 1.0e-15
        assert raw <= upper + 1.0e-15

    with pytest.raises(ValueError, match="five repeats"):
        aggregate_trial_rows(rows[:-1])


def test_axis_separation_preserves_censoring_nonpositive_and_negative_results():
    evaluable = _axis_curves(
        {
            "pos_x": 0.10,
            "neg_x": 0.20,
            "pos_y": 0.40,
            "neg_y": None,
            "pos_z": 0.20,
            "neg_z": 0.40,
        },
        geometry_seed=13,
    )
    result = compute_axis_separation(evaluable)
    assert result.block_evaluable
    assert result.reason == "EVALUABLE"
    assert result.weak_axis.conservative_exact_radius == 0.10
    assert result.strong_axes[0].lower_bound == 0.40
    assert result.strong_axes[1].lower_bound == 0.20
    assert result.strong_radius == pytest.approx(0.30)
    assert result.separation == pytest.approx(2.0 / 3.0)

    weak_censored = _axis_curves(
        {
            "pos_x": None,
            "neg_x": None,
            "pos_y": 0.40,
            "neg_y": 0.40,
            "pos_z": 0.20,
            "neg_z": 0.20,
        },
        geometry_seed=17,
    )
    result = compute_axis_separation(weak_censored)
    assert not result.block_evaluable
    assert result.separation is None
    assert result.reason == "WEAK_RADIUS_RIGHT_CENSORED"

    zero_denominator = _axis_curves(
        {
            "pos_x": 0.10,
            "neg_x": 0.10,
            "pos_y": 0.00,
            "neg_y": 0.00,
            "pos_z": 0.00,
            "neg_z": 0.00,
        },
        geometry_seed=19,
    )
    result = compute_axis_separation(zero_denominator)
    assert not result.block_evaluable
    assert result.separation is None
    assert result.reason == "NONPOSITIVE_STRONG_RADIUS"

    negative = _axis_curves(
        {
            "pos_x": 0.40,
            "neg_x": 0.40,
            "pos_y": 0.20,
            "neg_y": 0.20,
            "pos_z": 0.20,
            "neg_z": 0.20,
        },
        geometry_seed=23,
    )
    assert compute_axis_separation(negative).separation == pytest.approx(-1.0)


def test_predeclared_full_vs_frozen_uses_raw_curves_and_exact_censor_pattern():
    rows = _trial_rows(
        scene="END_FACE_TRANSITION_WEAK",
        direction_id="pos_x",
        path="full_reassociation",
        successes=[5, 5, 4, 3, 2, 1, 0, 0],
    )
    rows += _trial_rows(
        scene="END_FACE_TRANSITION_WEAK",
        direction_id="pos_x",
        path="frozen_jacobian",
        successes=[5, 4, 3, 2, 1, 0, 0, 0],
    )
    curves = aggregate_trial_rows(rows)
    comparison = compare_predeclared_full_vs_frozen(curves)[0]
    full = next(
        curve for curve in curves if curve.key.registration_path == "full_reassociation"
    )
    frozen = next(
        curve for curve in curves if curve.key.registration_path == "frozen_jacobian"
    )
    raw_difference = np.asarray(full.raw_probabilities) - np.asarray(
        frozen.raw_probabilities
    )
    expected_integral = np.sum(
        0.5
        * (raw_difference[:-1] + raw_difference[1:])
        * np.diff(TRANSLATION_AMPLITUDES_M)
    )

    assert comparison.raw_maximum_probability_gap == pytest.approx(0.2)
    assert comparison.raw_trapezoidal_integral_difference == pytest.approx(
        expected_integral
    )
    assert comparison.exact_d50_difference == pytest.approx(0.05)
    assert comparison.right_censoring_pattern == "BOTH_EXACT"
    assert comparison.correspondence_checksum_change_count == 40
    assert comparison.descriptive_difference_observed

    censored_full = replace(
        full,
        d50=None,
        d50_right_censored=True,
    )
    pattern = compare_predeclared_full_vs_frozen((censored_full, frozen))[0]
    assert pattern.right_censoring_pattern == "FULL_CENSORED_FROZEN_EXACT"
    assert pattern.exact_d50_difference is None


def test_bootstrap_is_pcg64_deterministic_shared_repeat_draw_and_ddof_one():
    success_matrix = [
        [True, True, True, True, True],
        [True, True, True, True, True],
        [True, True, True, True, True],
        [False, True, True, True, True],
        [False, False, True, True, True],
        [False, False, False, True, True],
        [False, False, False, False, True],
        [False, False, False, False, False],
    ]
    curve = aggregate_trial_rows(_trial_rows(successes=success_matrix))[0]
    first = bootstrap_full_translation_curve(curve)
    second = bootstrap_full_translation_curve(curve)

    assert first == second
    assert first.repetitions == 500
    assert len(first.repeat_index_draws) == 500
    assert all(len(draw) == 5 for draw in first.repeat_index_draws)
    matrix = np.asarray(curve.success_by_amplitude_repeat, dtype=np.float64)
    first_draw = np.asarray(first.repeat_index_draws[0], dtype=np.int64)
    raw = np.mean(matrix[:, first_draw], axis=1)
    fitted = fit_nonincreasing_isotonic(raw, np.full(8, 5.0))
    expected_d50, expected_censored = capture_radius_from_fitted(
        TRANSLATION_AMPLITUDES_M, fitted, 0.5
    )
    assert not expected_censored
    assert first.d50_values[0] == expected_d50

    finite = np.asarray([value for value in first.d50_values if value is not None])
    assert first.uncensored_fraction == 1.0
    assert first.finite_mean_d50 == pytest.approx(float(np.mean(finite)))
    assert first.sample_standard_deviation == pytest.approx(
        float(np.std(finite, ddof=1))
    )
    assert first.cv == pytest.approx(float(np.std(finite, ddof=1) / np.mean(finite)))
    assert first.eligible
    assert first.reason == "ELIGIBLE"


def test_bootstrap_zero_mean_and_right_censor_values_are_never_imputed():
    zero_curve = aggregate_trial_rows(_trial_rows(successes=[0] * 8))[0]
    zero = bootstrap_full_translation_curve(zero_curve)
    assert zero.uncensored_fraction == 1.0
    assert zero.finite_mean_d50 == 0.0
    assert zero.sample_standard_deviation == 0.0
    assert zero.cv is None
    assert not zero.eligible
    assert zero.reason == "ZERO_MEAN_D50"

    mostly_censored_matrix = [
        [True, True, True, True, True],
        [True, True, True, True, True],
        [True, True, True, True, True],
        [True, True, True, True, True],
        [True, True, True, True, True],
        [True, True, True, True, True],
        [True, True, True, True, True],
        [True, True, True, True, False],
    ]
    censored_curve = aggregate_trial_rows(
        _trial_rows(direction_id="neg_x", successes=mostly_censored_matrix)
    )[0]
    censored = bootstrap_full_translation_curve(censored_curve)
    assert None in censored.d50_values
    assert censored.uncensored_fraction < 0.80
    assert censored.cv is None
    assert not censored.eligible
    assert censored.reason == "INSUFFICIENT_UNCENSORED_FRACTION"
