import numpy as np

from backend_phase_a_v1_2_test_support import synthetic_snapshot


def test_closure_residual_is_actual_minus_rotated_source_quantization():
    snapshot = synthetic_snapshot()
    pose = snapshot.reference_pose
    parents = snapshot.target_points[snapshot.parent_indices].astype(float)
    quantized = snapshot.source_points.astype(float)
    actual = (pose[:3, :3] @ quantized.T).T + pose[:3, 3] - parents
    predicted = (pose[:3, :3] @ (quantized - snapshot.source_float64).T).T
    residual = actual - predicted
    assert np.linalg.norm(residual, axis=1).max() < 1e-13
