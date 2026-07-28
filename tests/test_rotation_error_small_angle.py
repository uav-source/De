import math

import numpy as np

from zero_perturbation.rotation_metrics import rotation_metric_audit


def test_atan2_metric_resolves_a_small_rotation():
    angle = 5.0e-7
    rotation = np.array(
        [[math.cos(angle), -math.sin(angle), 0.0], [math.sin(angle), math.cos(angle), 0.0], [0.0, 0.0, 1.0]]
    )
    audit = rotation_metric_audit(rotation, np.eye(3))
    assert math.isclose(audit["rotation_error_rad"], angle, rel_tol=0.0, abs_tol=1.0e-15)
