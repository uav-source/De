from resume_equivalence_test_support import result_pair
from zero_perturbation.phase_a_resume_scientific_equivalence import compare_trial_results


def test_exact_fields_are_identical_for_equal_results():
    fresh, resumed = result_pair()
    assert compare_trial_results(fresh, resumed) == []
