import pytest

from phase_a_execution_chain_test_support import sample_result
from zero_perturbation.phase_a_trial_result_schema import TrialResultValidationError, validate_phase_a_trial_result_strict


def test_success_cannot_omit_measured_update():
    value = sample_result()
    value["translation_update_m"] = None
    with pytest.raises(TrialResultValidationError):
        validate_phase_a_trial_result_strict(value)
