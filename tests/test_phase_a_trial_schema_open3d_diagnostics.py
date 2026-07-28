import pytest

from phase_a_execution_chain_test_support import sample_result
from zero_perturbation.phase_a_trial_result_schema import TrialResultValidationError, validate_phase_a_trial_result_strict


def test_open3d_correspondence_count_alias_is_rejected():
    value = sample_result()
    diagnostics = value["backend_diagnostics"]
    diagnostics["correspondence_count"] = diagnostics.pop("correspondence_set_size")
    with pytest.raises(TrialResultValidationError):
        validate_phase_a_trial_result_strict(value)
