import numpy as np

from eval.time_alignment_audit import exact_future_error_growth


def test_fixed_position_bias_has_absolute_error_but_no_error_growth():
    timestamps = np.arange(1.0e9, 1.0e9 + 12.0)
    reference = np.column_stack([timestamps - timestamps[0], np.zeros((timestamps.size, 2))])
    estimated = reference + np.asarray([2.0, -3.0, 4.0])
    growth, available = exact_future_error_growth(timestamps, estimated, reference)
    np.testing.assert_allclose(growth[available], 0.0, atol=1e-15)
