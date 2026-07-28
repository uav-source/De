from resume_equivalence_test_support import result_pair
from zero_perturbation.phase_a_resume_scientific_equivalence import compare_trial_results


def test_failure_classification_change_fails_exact_comparison():
    fresh, resumed = result_pair()
    resumed["failure_classification"] = "NO_CORRESPONDENCES"
    rows = compare_trial_results(fresh, resumed)
    assert any(row["json_field_path"] == "failure_classification" and not row["passed"] for row in rows)
