import numpy as np

from zero_perturbation.backend_phase_a_metrics import transform_update


def test_projection_cannot_rescue_an_invalid_raw_rotation_matrix():
    estimate = np.eye(4)
    estimate[:3, :3] = np.diag([1.01, 1.0, 1.0])
    result = transform_update(np.eye(4), estimate)
    assert result["rotation_update_rad"] == 0.0
    assert result["rotation_matrix_quality_pass"] is False
    assert result["rotation_audit"]["projection_correction_fro"] > 1.0e-5
