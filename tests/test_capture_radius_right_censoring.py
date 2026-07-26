from capture_range.capture_radius import (
    build_direction_recovery_curve,
    capture_radius_from_fitted,
)


def test_radius_is_none_and_right_censored_without_sampled_crossing():
    radius, censored = capture_radius_from_fitted([0.0, 0.1, 0.2], [1.0, 1.0, 0.95], 0.9)
    assert radius is None
    assert censored is True


def test_curve_records_d50_and_d90_censoring_independently_without_extrapolation():
    curve = build_direction_recovery_curve(
        direction_id="x_positive",
        direction=[1.0, 0.0, 0.0],
        signed_side=1,
        amplitudes=[0.0, 0.1, 0.2],
        successful_trials=[3, 3, 2],
        total_trials=[3, 3, 3],
    )
    assert curve.d90 == 0.2
    assert curve.d90_right_censored is False
    assert curve.d50 is None
    assert curve.d50_right_censored is True
