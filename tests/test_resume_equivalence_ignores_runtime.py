from resume_equivalence_test_support import result_pair
from zero_perturbation.phase_a_resume_scientific_equivalence import compare_trial_results


def test_runtime_difference_is_reported_but_non_decisive():
    fresh, resumed = result_pair()
    resumed["runtime_ms"] += 100.0
    rows = compare_trial_results(fresh, resumed)
    assert len(rows) == 1
    assert rows[0]["comparison_class"] == "IGNORED_RUNTIME_METADATA"
    assert rows[0]["passed"] is True
