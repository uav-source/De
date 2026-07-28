import pytest

from phase_a_execution_chain_test_support import sample_result
from zero_perturbation.phase_a_trial_result_schema import TrialResultValidationError, validate_phase_a_trial_result_strict


def test_missing_scene_variant_is_rejected():
    value = sample_result()
    del value["scene_variant"]
    with pytest.raises(TrialResultValidationError):
        validate_phase_a_trial_result_strict(value)
