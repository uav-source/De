import pytest

from capture_range.capture_radius import wilson_interval, wilson_intervals


def test_wilson_interval_has_expected_day1_n3_extremes():
    lower_zero, upper_zero = wilson_interval(0, 3)
    lower_full, upper_full = wilson_interval(3, 3)
    assert lower_zero == 0.0
    assert upper_zero == pytest.approx(0.5614970318)
    assert lower_full == pytest.approx(1.0 - upper_zero)
    assert upper_full == 1.0


def test_vector_wilson_interval_preserves_amplitude_order():
    lower, upper = wilson_intervals([0, 1, 3], [3, 3, 3])
    assert lower.shape == upper.shape == (3,)
    assert list(lower) == sorted(lower)
    assert list(upper) == sorted(upper)


@pytest.mark.parametrize("successes,total", [(-1, 3), (4, 3), (0, 0)])
def test_invalid_wilson_counts_fail(successes, total):
    with pytest.raises(ValueError):
        wilson_interval(successes, total)
