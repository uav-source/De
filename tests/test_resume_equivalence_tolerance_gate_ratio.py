from phase_a_execution_chain_test_support import ROOT
from zero_perturbation.phase_a_resume_scientific_equivalence import load_equivalence_contract


def test_tolerance_is_negligible_relative_to_scientific_gates():
    value = load_equivalence_contract(ROOT)
    ratios = value["tolerance_negligibility"]
    assert float(ratios["translation_threshold_to_atol_ratio"]) == 1.0e9
    assert float(ratios["rotation_threshold_to_atol_ratio"]) > 1.0e8
