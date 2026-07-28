import math

import numpy as np

from zero_perturbation.backend_phase_a_metrics import transform_update


def test_phase_a_rotation_update_uses_projected_atan2_metric():
    angle = 1.0e-5
    estimate = np.eye(4)
    estimate[:3, :3] = [
        [math.cos(angle), -math.sin(angle), 0.0],
        [math.sin(angle), math.cos(angle), 0.0],
        [0.0, 0.0, 1.0],
    ]
    result = transform_update(np.eye(4), estimate)
    assert np.isclose(result["rotation_update_rad"], angle, atol=1.0e-15)
    assert result["rotation_audit"]["nearest_so3_projection"] is not None
    assert result["rotation_matrix_quality_pass"] is True
