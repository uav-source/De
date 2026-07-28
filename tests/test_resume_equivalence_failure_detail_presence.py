from resume_equivalence_test_support import result_pair
from zero_perturbation.phase_a_resume_scientific_equivalence import compare_trial_results


def test_failure_detail_text_can_differ_when_both_are_present():
    fresh, resumed = result_pair()
    for value, detail in ((fresh, "failure at /tmp/a"), (resumed, "failure at /tmp/b")):
        value["solver_failure"] = True
        value["failure_classification"] = "NO_CORRESPONDENCES"
        value["failure_detail"] = detail
    rows = compare_trial_results(fresh, resumed)
    detail = next(row for row in rows if row["json_field_path"] == "failure_detail")
    assert detail["comparison_class"] == "FAILURE_DETAIL_PRESENCE"
    assert detail["passed"] is True
