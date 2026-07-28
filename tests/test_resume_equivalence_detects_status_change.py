from resume_equivalence_test_support import result_pair
from zero_perturbation.phase_a_resume_scientific_equivalence import compare_trial_results


def test_solver_status_change_fails_exact_comparison():
    fresh, resumed = result_pair()
    resumed["solver_failure"] = True
    rows = compare_trial_results(fresh, resumed)
    assert any(row["json_field_path"] == "solver_failure" and not row["passed"] for row in rows)
