from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from degen_detector.exposure_metrics import (  # noqa: E402
    cumulative_inverse_axis_information,
    harmonic_axis_information,
    longest_condition_duration,
    low_axis_information_ratio,
    mean_inverse_axis_information,
)


def test_exposure_formulas_and_longest_duration():
    values = np.array([1.0, 2.0, 4.0, 8.0])
    timestamps = np.arange(4) * 0.5
    expected_sum = 0.5 * np.sum(1.0 / values)
    assert np.isclose(cumulative_inverse_axis_information(values, timestamps), expected_sum)
    assert np.isclose(mean_inverse_axis_information(values, timestamps), np.mean(1.0 / values))
    assert np.isclose(harmonic_axis_information(values, timestamps), 1.0 / np.mean(1.0 / values))
    assert low_axis_information_ratio(values, 3.0) == 0.5
    assert longest_condition_duration([False, True, True, False], timestamps) == 1.0
