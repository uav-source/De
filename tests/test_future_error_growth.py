import numpy as np

from eval.time_alignment_audit import exact_future_error_growth


def test_uniform_motion_without_error_has_zero_future_growth_and_tail_nan():
    timestamps = np.arange(0.0, 11.0)
    reference = np.column_stack([timestamps, np.zeros((timestamps.size, 2))])
    growth, available = exact_future_error_growth(timestamps, reference, reference, window_seconds=5.0)
    np.testing.assert_array_equal(growth[available], 0.0)
    assert int(np.sum(~available)) == 5
    assert np.all(np.isnan(growth[~available]))


def test_linear_drift_produces_window_scaled_error_growth():
    timestamps = np.arange(0.0, 11.0)
    reference = np.zeros((timestamps.size, 3))
    estimated = reference.copy()
    estimated[:, 0] = 0.1 * timestamps
    growth, available = exact_future_error_growth(timestamps, estimated, reference, window_seconds=5.0)
    np.testing.assert_allclose(growth[available], 0.5, atol=1e-15)
