from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from degen_detector.whitened_info import compute_axis_information, compute_axis_information_ratio  # noqa: E402


def test_axis_information_formulas_on_manual_matrix():
    matrix = np.diag([2.0, 4.0, 6.0])
    axis = np.array([1.0, 0.0, 0.0])
    assert compute_axis_information(matrix, axis) == 2.0
    assert np.isclose(compute_axis_information_ratio(matrix, axis), 2.0 / 4.0)
