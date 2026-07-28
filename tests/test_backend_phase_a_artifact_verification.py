from backend_phase_a_test_support import ROOT
from zero_perturbation.backend_phase_a_verification import (
    verify_backend_phase_a_lock,
)


def test_phase_a_lock_artifact_verifies_without_executing_phase_a():
    result = verify_backend_phase_a_lock(ROOT)
    assert result["verification_pass"] is True, result["errors"]
    assert result["planned_snapshot_count"] == 210
    assert result["planned_trial_count"] == 420
    assert result["native_planned_trial_count"] == 0
    assert result["artifact_sha_verification_pass"] is True
    assert result["backend_phase_a_executed"] is False
    assert result["day1_scientific_validation_pass"] == "NOT_EVALUATED"
