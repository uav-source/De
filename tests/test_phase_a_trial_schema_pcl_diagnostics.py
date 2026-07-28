import pytest

from phase_a_execution_chain_test_support import sample_result
from zero_perturbation.phase_a_trial_result_schema import PCL_BACKEND, TrialResultValidationError, validate_phase_a_trial_result_strict


def test_pcl_cli_exit_code_alias_is_rejected():
    value = sample_result(PCL_BACKEND)
    diagnostics = value["backend_diagnostics"]
    diagnostics["cli_exit_code"] = diagnostics.pop("exit_code")
    with pytest.raises(TrialResultValidationError):
        validate_phase_a_trial_result_strict(value)
