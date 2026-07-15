import numpy as np

from eval.stage2_failure_window_stats import (
    CausalInnovationWindow,
    WindowStatisticConfig,
)


def _monitor(window_size):
    return CausalInnovationWindow(
        WindowStatisticConfig(window_size, 0.5, 1.0e-12, 1.0e-12)
    )


def test_same_sign_run_and_dominant_ratio_are_window_local():
    monitor = _monitor(5)
    runs = []
    result = None
    for value in [1.0, 2.0, 3.0, -1.0, -2.0]:
        result = monitor.update(value, True)
        runs.append(result.current_same_sign_run_length)
    assert runs == [1, 2, 3, 1, 2]
    assert result.max_same_sign_run_length == 3
    assert np.isclose(result.dominant_sign_ratio, 3.0 / 5.0)
    assert result.positive_count == 3
    assert result.negative_count == 2


def test_zero_value_interrupts_same_sign_run():
    monitor = _monitor(4)
    result = None
    for value in [1.0, 1.0, 0.0, 1.0]:
        result = monitor.update(value, True)
    assert result.zero_count == 1
    assert result.current_sign == 1
    assert result.current_same_sign_run_length == 1
    assert result.max_same_sign_run_length == 2
