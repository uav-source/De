from eval.stage2_failure_window_stats import (
    CausalInnovationWindow,
    WindowStatisticConfig,
)


def test_two_sided_cusum_matches_frozen_recurrence():
    monitor = CausalInnovationWindow(
        WindowStatisticConfig(5, 0.5, 1.0e-12, 1.0e-12)
    )
    outputs = [monitor.update(value, True) for value in [1.0, 1.0, -1.0]]
    assert [row.cusum_positive for row in outputs] == [0.5, 1.0, 0.0]
    assert outputs[-1].cusum_negative == 0.5
    assert outputs[-1].cusum_max == 0.5
    assert outputs[-1].cusum_signed == -0.5
