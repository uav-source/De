import numpy as np
import pytest

from eval.time_alignment_audit import (
    discrete_future_error_growth,
    exact_future_error_growth,
    exact_future_error_growth_against_reference,
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


def test_missing_internal_reference_samples_use_native_reference_interpolation():
    estimator_times = np.arange(1.0e9, 1.0e9 + 11.0)
    estimator = np.column_stack(
        [estimator_times - estimator_times[0], np.zeros((estimator_times.size, 2))]
    )
    # RTK samples at 3 s and 6 s are deliberately absent.  Interpolation is
    # performed once on the native sparse reference grid at t and t+5.
    reference_times = estimator_times[[0, 1, 2, 4, 5, 7, 8, 9, 10]]
    reference = np.column_stack(
        [reference_times - reference_times[0], np.zeros((reference_times.size, 2))]
    )
    growth, available = exact_future_error_growth_against_reference(
        estimator_times, estimator, reference_times, reference
    )
    np.testing.assert_allclose(growth[available], 0.0, atol=1e-15)
    assert int(np.sum(~available)) == 5


def test_nonfinite_reference_sample_fails_closed():
    timestamps = np.arange(1.0e9, 1.0e9 + 11.0)
    positions = np.column_stack(
        [timestamps - timestamps[0], np.zeros((timestamps.size, 2))]
    )
    missing = positions.copy()
    missing[4] = np.nan
    with pytest.raises(ValueError, match="finite"):
        exact_future_error_growth_against_reference(
            timestamps, positions, timestamps, missing
        )
