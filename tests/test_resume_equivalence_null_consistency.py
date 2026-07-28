from zero_perturbation.phase_a_resume_scientific_equivalence import compare_optional_float


def test_null_consistency_requires_both_values_null():
    assert compare_optional_float(None, None, planned_trial_id="trial", path="metric") == []
    rows = compare_optional_float(None, 0.0, planned_trial_id="trial", path="metric")
    assert rows[0]["comparison_class"] == "NULL_CONSISTENCY"
    assert rows[0]["passed"] is False
