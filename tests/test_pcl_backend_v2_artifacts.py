from pcl_backend_v2_test_support import ROOT
from zero_perturbation.backend_qualification_v2_verification import (
    verify_backend_qualification_v2,
)


def test_stopped_v2_artifact_verifies_independently():
    result = verify_backend_qualification_v2(ROOT)
    assert result["verification_pass"] is True, result["errors"]
    assert result["microtest_pass_count"] == 2
    assert result["microtest_failure_count"] == 1
    assert result["pcl_backend_implementation_valid"] is False
    assert result["phase_a_authorized"] is False
