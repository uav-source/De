from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from degen_detector.weak_direction import estimate_primary_direction  # noqa: E402


def test_primary_direction_is_returned_without_degeneracy_trigger():
    estimate = estimate_primary_direction(
        np.array([1.0, 5.0, 10.0]),
        np.eye(3),
        min_eigengap_ratio=0.02,
    )
    assert np.allclose(estimate.direction, [1.0, 0.0, 0.0])
    assert estimate.lambda_min_ratio == 0.1
    assert estimate.eigengap_ratio == 0.4
    assert estimate.direction_stable is True
