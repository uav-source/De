import numpy as np

from backend_phase_a_v1_2_test_support import synthetic_snapshot


def test_float64_guard_uses_frozen_256_eps_and_scale_formula():
    snapshot = synthetic_snapshot()
    parents = snapshot.target_points[snapshot.parent_indices].astype(float)
    translation_norm = np.linalg.norm(snapshot.reference_pose[:3, 3])
    scale = np.maximum.reduce((np.ones(len(parents)), np.linalg.norm(parents, axis=1), np.linalg.norm(snapshot.source_float64, axis=1), np.full(len(parents), translation_norm)))
    guard = 256.0 * np.finfo(np.float64).eps * scale
    assert guard.min() > 0.0
    assert np.array_equal(guard, 256.0 * np.finfo(np.float64).eps * scale)
