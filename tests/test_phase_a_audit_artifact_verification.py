from phase_a_execution_chain_test_support import actual_execution_chain, published_execution_chain
from zero_perturbation.phase_a_execution_chain_artifact_verifier import verify_phase_a_execution_chain_artifact


def test_independent_artifact_and_sha_verification_pass(published_execution_chain):
    result = verify_phase_a_execution_chain_artifact(published_execution_chain["artifact"])
    assert result["PHASE_A_EXECUTION_CHAIN_ARTIFACT_VERIFICATION_PASS"] is True
    assert result["sha256_validation_pass"] is True
