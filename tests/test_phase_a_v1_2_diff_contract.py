from backend_phase_a_v1_2_test_support import ROOT
from zero_perturbation.backend_phase_a_v1_2 import scientific_contract_diff


def test_v1_2_diff_contract_has_only_implementation_and_staging_changes():
    result = scientific_contract_diff(ROOT)
    zero = [
        name
        for name in result
        if name.endswith("_difference_count")
        and not name.startswith(("provenance_", "execution_"))
    ]
    assert all(result[name] == 0 for name in zero)
    assert result["provenance_implementation_difference_count"] > 0
    assert result["execution_staging_difference_count"] > 0
