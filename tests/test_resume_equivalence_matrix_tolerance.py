import numpy as np

from zero_perturbation.phase_a_resume_scientific_equivalence import compare_float_matrix


def test_final_transform_is_compared_elementwise_with_tolerance():
    fresh = np.eye(4).tolist()
    resumed = np.eye(4).tolist()
    resumed[0][3] = 5.0e-13
    rows = compare_float_matrix(fresh, resumed, planned_trial_id="trial")
    assert len(rows) == 1
    assert rows[0]["json_field_path"] == "final_transform_4x4[0][3]"
    assert rows[0]["passed"] is True
