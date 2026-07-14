from pathlib import Path

import numpy as np

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from degen_detector.weak_direction import compute_subspace_axis_alignment, compute_weak_projector  # noqa: E402


def test_projector_handles_two_dimensional_weak_subspace():
    eigvals = np.array([100.0, 1.0, 0.5])
    eigvecs = np.eye(3)
    projector = compute_weak_projector(eigvals, eigvecs, tau_w=0.02)
    assert np.allclose(projector @ projector, projector)
    assert np.isclose(np.trace(projector), 2.0)
    assert compute_subspace_axis_alignment(projector, np.array([0.0, 1.0, 0.0])) == 1.0
    assert compute_subspace_axis_alignment(projector, np.array([1.0, 0.0, 0.0])) == 0.0

