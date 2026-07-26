from capture_range.capture_radius import capture_radius_from_fitted


def test_d90_is_first_discrete_fitted_probability_at_or_below_ninety_percent():
    radius, censored = capture_radius_from_fitted(
        [0.0, 0.02, 0.05], [1.0, 0.9, 0.4], 0.9
    )
    assert radius == 0.02
    assert censored is False


def test_d90_can_be_smaller_than_d50():
    d90, _ = capture_radius_from_fitted([0.0, 0.1, 0.2], [1.0, 0.8, 0.4], 0.9)
    d50, _ = capture_radius_from_fitted([0.0, 0.1, 0.2], [1.0, 0.8, 0.4], 0.5)
    assert d90 == 0.1
    assert d50 == 0.2
