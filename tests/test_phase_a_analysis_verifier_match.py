from phase_a_execution_chain_test_support import actual_execution_chain


def test_primary_analysis_and_independent_verifier_match(actual_execution_chain):
    result = actual_execution_chain["verifier"]
    assert result["PHASE_A_EXECUTION_CHAIN_INDEPENDENT_VERIFIER_PASS"] is True
    assert result["PHASE_A_EXECUTION_CHAIN_ANALYSIS_VERIFIER_MATCH"] is True
    assert result["difference_count"] == 0
