import pytest

from phase_a_execution_chain_test_support import sample_result
from zero_perturbation.phase_a_trial_result_schema import TrialResultValidationError, validate_phase_a_trial_result_strict


def test_unknown_top_level_field_is_rejected():
    value = sample_result()
    value["unknown"] = 1
    with pytest.raises(TrialResultValidationError):
        validate_phase_a_trial_result_strict(value)
