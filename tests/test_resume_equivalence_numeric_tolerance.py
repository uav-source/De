from zero_perturbation.phase_a_resume_scientific_equivalence import compare_optional_float


def test_tiny_numeric_difference_is_reported_and_passes():
    rows = compare_optional_float(2.0296317638433184e-8, 2.029631763843318e-8, planned_trial_id="trial", path="inlier_rmse")
    assert len(rows) == 1
    assert rows[0]["passed"] is True
    assert rows[0]["comparison_class"] == "NUMERIC_TOLERANCE"
