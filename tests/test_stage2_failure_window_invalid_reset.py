import math

from eval.stage2_failure_window_stats import (
    CausalInnovationWindow,
    WindowStatisticConfig,
)


def test_invalid_frame_clears_window_cusum_and_run_state():
    monitor = CausalInnovationWindow(
        WindowStatisticConfig(5, 0.5, 1.0e-12, 1.0e-12)
    )
    monitor.update(1.0, True)
    monitor.update(1.0, True)
    reset = monitor.update(float("nan"), False)
    assert not reset.valid
    assert reset.window_count == 0
    assert reset.consecutive_valid_count == 0
    assert reset.current_same_sign_run_length == 0
    assert math.isnan(reset.cusum_positive)

    restarted = monitor.update(1.0, True)
    assert restarted.window_count == 1
    assert restarted.consecutive_valid_count == 1
    assert restarted.current_same_sign_run_length == 1
    assert restarted.cusum_positive == 0.5
