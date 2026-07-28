from backend_qualification_test_support import ROOT
from zero_perturbation.backend_qualification_verification import (
    verify_backend_qualification,
)


def test_stopped_backend_qualification_artifact_verifies_independently():
    result = verify_backend_qualification(ROOT)
    assert result["verification_pass"], result["errors"]
