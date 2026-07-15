import numpy as np

from eval.stage2_failure_window_stats import (
    CausalInnovationWindow,
    WindowStatisticConfig,
)


def _monitor(window_size=3):
    return CausalInnovationWindow(
        WindowStatisticConfig(
            window_size=window_size,
            cusum_reference_sigma=0.5,
            sign_zero_epsilon=1.0e-12,
            moment_epsilon=1.0e-12,
        )
    )


def test_window_mean_median_and_energy_match_frozen_formulas():
    monitor = _monitor(3)
    output = None
    for value in [1.0, 2.0, 3.0]:
        output = monitor.update(value, True)
    assert output.window_mean == 2.0
    assert output.window_median == 2.0
    assert np.isclose(output.window_energy, 14.0 / 3.0)
    assert output.window_count == 3
    assert output.window_ready


def test_partial_window_uses_only_values_seen_so_far():
    monitor = _monitor(3)
    first = monitor.update(1.0, True)
    second = monitor.update(2.0, True)
    assert first.window_count == 1
    assert not first.window_ready
    assert first.window_mean == 1.0
    assert second.window_count == 2
    assert not second.window_ready
    assert second.window_mean == 1.5
    assert second.window_median == 1.5
