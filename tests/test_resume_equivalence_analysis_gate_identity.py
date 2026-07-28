import copy

from resume_equivalence_test_support import analysis_output
from zero_perturbation.phase_a_resume_scientific_equivalence import compare_analysis_outputs


def test_analysis_gate_change_is_detected_exactly():
    fresh = analysis_output()
    resumed = copy.deepcopy(fresh)
    resumed["decision"]["PHASE_A_EXECUTION_CHAIN_FIXTURE_PASS"] = False
    rows = compare_analysis_outputs(fresh, resumed)
    assert any(row["json_field_path"] == "decision" and not row["passed"] for row in rows)
