from pathlib import Path

from zero_perturbation.phase_a_execution_chain_v1_2_artifact_verifier import (
    verify_phase_a_execution_chain_v1_2_artifact,
)


ROOT = Path(__file__).resolve().parents[1]


def test_execution_chain_v1_2_artifact_verifies_independently():
    result = verify_phase_a_execution_chain_v1_2_artifact(
        ROOT / "artifacts/current/zero_perturbation_phase_a_execution_chain_audit_v1_2"
    )
    assert result["EXECUTION_CHAIN_ARTIFACT_VERIFICATION_PASS"] is True
    assert result["sha256_validation_pass"] is True
