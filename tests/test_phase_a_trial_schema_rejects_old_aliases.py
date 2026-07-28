import pytest

from phase_a_execution_chain_test_support import sample_result
from zero_perturbation.phase_a_trial_result_schema import TrialResultValidationError, validate_phase_a_trial_result_strict


@pytest.mark.parametrize("alias", ["solver_failed", "failure_classifications", "cli_exit_code"])
def test_old_top_level_aliases_are_rejected(alias):
    value = sample_result()
    value[alias] = False
    with pytest.raises(TrialResultValidationError):
        validate_phase_a_trial_result_strict(value)
