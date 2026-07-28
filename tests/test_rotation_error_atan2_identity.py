import numpy as np

from zero_perturbation.rotation_metrics import rotation_metric_audit


def test_identity_rotation_error_is_exactly_zero():
    audit = rotation_metric_audit(np.eye(3), np.eye(3))
    assert audit["rotation_error_rad"] == 0.0
    assert audit["rotation_matrix_quality_pass"] is True
