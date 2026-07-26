import numpy as np

from capture_range.capture_radius import fit_nonincreasing_isotonic


def test_decreasing_pava_fixes_only_monotonicity_violations_and_keeps_raw():
    raw = np.array([1.0, 0.6, 0.8, 0.2])
    original = raw.copy()
    fitted = fit_nonincreasing_isotonic(raw)
    assert np.array_equal(raw, original)
    assert np.allclose(fitted, [1.0, 0.7, 0.7, 0.2])
    assert np.all(np.diff(fitted) <= 0.0)


def test_decreasing_pava_uses_trial_counts_as_weights():
    fitted = fit_nonincreasing_isotonic([1.0, 0.6, 0.8], [1.0, 1.0, 3.0])
    assert np.allclose(fitted, [1.0, 0.75, 0.75])


def test_already_monotonic_curve_is_unchanged():
    raw = np.array([1.0, 0.9, 0.5, 0.0])
    assert np.array_equal(fit_nonincreasing_isotonic(raw), raw)
