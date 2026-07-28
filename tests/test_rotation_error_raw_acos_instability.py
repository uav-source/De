import numpy as np

from zero_perturbation.rotation_metrics import rotation_metric_audit


def test_near_identity_nonorthogonal_matrix_proves_raw_acos_instability():
    raw = np.eye(3) * (1.0 - 1.0e-8)
    audit = rotation_metric_audit(raw, np.eye(3))
    assert audit["raw_trace_acos_rotation_error_rad"] > 1.0e-4
    assert audit["rotation_error_rad"] < 1.0e-8
    assert audit["rotation_matrix_quality_pass"] is True
