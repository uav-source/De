from zero_perturbation.phase_a_resume_scientific_equivalence import compare_optional_float


def test_large_numeric_change_is_outside_frozen_tolerance():
    rows = compare_optional_float(0.0, 1.0e-9, planned_trial_id="trial", path="translation_update_m")
    assert rows[0]["passed"] is False
    assert rows[0]["absolute_difference"] > rows[0]["allowed_tolerance"]
