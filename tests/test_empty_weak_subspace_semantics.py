from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from degen_detector.weak_direction import (  # noqa: E402
    compute_subspace_axis_alignment,
    estimate_weak_subspace,
)


def test_empty_weak_subspace_is_not_zero_alignment():
    estimate = estimate_weak_subspace(np.array([1.0, 1.0, 1.0]), np.eye(3), tau_w=0.02)
    assert estimate.triggered is False
    assert estimate.dimension == 0
    assert estimate.projector is None
    assert np.isnan(compute_subspace_axis_alignment(None, np.array([1.0, 0.0, 0.0])))
