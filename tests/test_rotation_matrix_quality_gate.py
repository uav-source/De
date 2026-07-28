import numpy as np

from zero_perturbation.rotation_metrics import rotation_metric_audit


def test_quality_gate_accepts_v2_near_so3_matrix_and_rejects_large_defect():
    near = np.eye(3) * (1.0 - 1.0e-8)
    assert rotation_metric_audit(near, np.eye(3))["rotation_matrix_quality_pass"] is True
    poor = np.eye(3) * 0.99
    audit = rotation_metric_audit(poor, np.eye(3))
    assert audit["orthogonality_defect_fro"] > 1.0e-5
    assert audit["rotation_matrix_quality_pass"] is False
