import numpy as np

from zero_perturbation.backend_phase_a_metrics import transform_update


def test_transform_semantics_are_source_to_target_and_reference_relative():
    reference = np.eye(4)
    reference[:3, 3] = [1.0, 2.0, 3.0]
    estimate = reference.copy()
    estimate[0, 3] += 0.0005
    result = transform_update(reference, estimate)
    assert np.allclose(result["T_delta"][:3, 3], [0.0005, 0.0, 0.0])
    assert np.isclose(result["translation_update_m"], 0.0005)
    assert result["rotation_update_rad"] == 0.0
