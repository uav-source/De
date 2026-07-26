from capture_range.capture_radius import (
    build_direction_recovery_curve,
    capture_radius_from_fitted,
)


def test_d50_is_first_discrete_fitted_probability_at_or_below_half():
    radius, censored = capture_radius_from_fitted(
        [0.0, 0.02, 0.05, 0.10], [1.0, 0.8, 0.5, 0.2], 0.5
    )
    assert radius == 0.05
    assert censored is False


def test_direction_curve_d50_uses_fitted_not_raw_probabilities():
    curve = build_direction_recovery_curve(
        direction_id="x_positive",
        direction=[1.0, 0.0, 0.0],
        signed_side=1,
        amplitudes=[0.0, 0.1, 0.2, 0.3],
        successful_trials=[3, 1, 2, 0],
        total_trials=[3, 3, 3, 3],
    )
    assert list(curve.raw_probabilities) == [1.0, 1.0 / 3.0, 2.0 / 3.0, 0.0]
    assert list(curve.fitted_probabilities) == [1.0, 0.5, 0.5, 0.0]
    assert curve.d50 == 0.1
