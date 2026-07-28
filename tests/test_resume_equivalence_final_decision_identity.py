from zero_perturbation.phase_a_resume_scientific_equivalence import compare_final_decisions


def test_final_decision_must_be_exactly_identical():
    rows = compare_final_decisions({"PASS": True}, {"PASS": False})
    assert len(rows) == 1
    assert rows[0]["comparison_class"] == "EXACT"
    assert rows[0]["passed"] is False
