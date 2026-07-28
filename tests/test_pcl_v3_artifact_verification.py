from pcl_backend_v3_test_support import ROOT
from zero_perturbation.backend_qualification_v3_verification import (
    verify_backend_qualification_v3,
)


def test_backend_qualification_v3_artifact_verifies_independently():
    result = verify_backend_qualification_v3(ROOT)
    assert result["verification_pass"] is True, result["errors"]
    assert result["microtest_pass_count"] == 3
    assert result["pcl_backend_implementation_valid"] is True
    assert result["phase_a_authorized"] is True
    assert result["phase_a_executed"] is False
    assert result["phase_b_executed"] is False
