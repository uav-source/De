import numpy as np
import pytest

from eval.time_alignment_audit import (
    discrete_future_error_growth,
    exact_future_error_growth,
)


def test_nonuniform_timestamps_distinguish_exact_target_from_first_later_sample():
    timestamps = np.asarray([0.0, 1.7, 4.9, 5.4, 7.3, 10.0]) + 1.0e9
    reference = np.zeros((timestamps.size, 3))
    estimated = np.column_stack([timestamps - timestamps[0], np.zeros((timestamps.size, 2))])
    exact, exact_available = exact_future_error_growth(timestamps, estimated, reference, window_seconds=5.0)
    discrete, discrete_available, horizon = discrete_future_error_growth(timestamps, estimated, reference, window_seconds=5.0)
    assert exact_available[0] and discrete_available[0]
    assert exact[0] == 5.0
    assert discrete[0] == pytest.approx(5.4)
    assert horizon[0] == pytest.approx(5.4)


def test_sparse_reference_is_linearly_interpolated_at_query_times():
    timestamps = np.asarray([1.0e9, 1.0e9 + 2.0, 1.0e9 + 7.0])
    reference = np.column_stack([timestamps - timestamps[0], np.zeros((3, 2))])
    growth, available = exact_future_error_growth(timestamps, reference, reference, window_seconds=5.0)
    assert available[0]
    assert growth[0] == 0.0
