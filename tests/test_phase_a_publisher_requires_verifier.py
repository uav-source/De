import pytest

from phase_a_execution_chain_test_support import AUDIT_LOCK, actual_execution_chain
from zero_perturbation.phase_a_stage1_publisher import publish_phase_a_execution_chain_audit


def test_publisher_refuses_without_independent_verifier_pass(tmp_path, actual_execution_chain):
    verification = dict(actual_execution_chain["verifier"])
    verification["PHASE_A_EXECUTION_CHAIN_INDEPENDENT_VERIFIER_PASS"] = False
    with pytest.raises(PermissionError):
        publish_phase_a_execution_chain_audit(artifact_dir=tmp_path / "artifact", analysis=actual_execution_chain["analysis"], verification=verification, fixture_run_manifest=actual_execution_chain["manifest"], resume_audit={}, tamper_audit={}, audit_protocol_lock=AUDIT_LOCK)
