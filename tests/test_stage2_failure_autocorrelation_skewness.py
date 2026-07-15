import math

import numpy as np

from eval.stage2_failure_window_stats import (
    CausalInnovationWindow,
    WindowStatisticConfig,
)


def _run(values):
    monitor = CausalInnovationWindow(
        WindowStatisticConfig(len(values), 0.5, 1.0e-12, 1.0e-12)
    )
    output = None
    for value in values:
        output = monitor.update(value, True)
    return output


def test_lag1_autocorrelation_uses_frozen_window_mean_formula():
    alternating = _run([1.0, -1.0, 1.0, -1.0])
    assert np.isclose(alternating.lag1_autocorrelation, -0.75)
    assert math.isnan(_run([1.0, 1.0, 1.0]).lag1_autocorrelation)


def test_skewness_uses_population_moments_and_rejects_constant_window():
    symmetric = _run([-2.0, -1.0, 0.0, 1.0, 2.0])
    assert np.isclose(symmetric.skewness, 0.0, atol=1.0e-12)
    assert math.isnan(_run([1.0, 1.0, 1.0]).skewness)
