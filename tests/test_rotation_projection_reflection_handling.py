import numpy as np

from zero_perturbation.rotation_metrics import project_to_so3, rotation_metric_audit


def test_reflection_is_corrected_to_proper_rotation_but_fails_quality_gate():
    reflection = np.diag([-1.0, 1.0, 1.0])
    projected, _ = project_to_so3(reflection)
    assert np.linalg.det(projected) > 0.0
    audit = rotation_metric_audit(reflection, np.eye(3))
    assert audit["raw_rotation_determinant_positive"] is False
    assert audit["rotation_matrix_quality_pass"] is False
