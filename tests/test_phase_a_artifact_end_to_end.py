import json

from phase_a_execution_chain_test_support import actual_execution_chain, published_execution_chain


def test_published_artifact_has_relock_but_not_execution_authority(published_execution_chain):
    decision = json.loads((published_execution_chain["artifact"] / "final_decision.json").read_text())
    assert decision["PHASE_A_EXECUTION_CHAIN_AUDIT_PASS"] is True
    assert decision["PHASE_A_STAGE1_RELOCK_AUTHORIZED"] is True
    assert decision["PHASE_A_STAGE1_BACKEND_RUN_AUTHORIZED"] is False
    assert decision["DAY1_SCIENTIFIC_VALIDATION_PASS"] == "NOT_EVALUATED"
