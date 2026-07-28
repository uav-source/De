import pytest

from phase_a_execution_chain_test_support import sample_result
from zero_perturbation.phase_a_trial_result_schema import TrialResultValidationError, validate_phase_a_trial_result_strict


def test_nonfinite_runtime_is_rejected():
    value = sample_result()
    value["runtime_ms"] = float("nan")
    with pytest.raises(TrialResultValidationError):
        validate_phase_a_trial_result_strict(value)
