import pytest

from backend_phase_a_v1_1_test_support import ROOT, V1_ARTIFACT
from zero_perturbation.backend_phase_a_v1_1 import (
    RunnerContractError,
    validate_v1_1_lock_document,
)


def test_runner_rejects_old_v1_lock_before_execution():
    with pytest.raises(RunnerContractError, match="old v1"):
        validate_v1_1_lock_document(
            V1_ARTIFACT / "backend_phase_a_protocol_lock.json", ROOT
        )

