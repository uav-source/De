import pytest

from phase_a_execution_chain_test_support import sample_result
from zero_perturbation.phase_a_trial_result_schema import TrialResultValidationError, validate_phase_a_trial_result_strict


def test_failure_cannot_use_none_classification():
    value = sample_result()
    value["solver_failure"] = True
    value["failure_detail"] = "failed"
    with pytest.raises(TrialResultValidationError):
        validate_phase_a_trial_result_strict(value)
