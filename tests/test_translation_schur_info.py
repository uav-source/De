from pathlib import Path

import numpy as np

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from degen_detector.whitened_info import (  # noqa: E402
    compute_effective_sample_size,
    compute_translation_schur_info,
    normalize_information_matrix,
)


def test_translation_schur_matches_block_formula():
    A = np.diag([10.0, 12.0, 14.0])
    B = np.diag([1.0, 2.0, 3.0])
    C = np.diag([8.0, 9.0, 11.0])
    H = np.block([[A, B], [B.T, C]])
    ratio = 1.0e-6
    scale = max(float(np.max(np.diag(A))), float(np.trace(A)) / 3.0, 1.0)
    expected = C - B.T @ np.linalg.solve(A + ratio * scale * np.eye(3), B)
    actual = compute_translation_schur_info(H, ratio)
    assert actual.shape == (3, 3)
    assert np.allclose(actual, expected)
    assert np.all(np.linalg.eigvalsh(actual) >= 0.0)


def test_effective_sample_normalization():
    variances = np.array([1.0, 1.0, 2.0, 2.0])
    n_eff = compute_effective_sample_size(variances)
    assert 0.0 < n_eff <= 4.0
    assert np.allclose(normalize_information_matrix(np.eye(3) * n_eff, n_eff), np.eye(3))

