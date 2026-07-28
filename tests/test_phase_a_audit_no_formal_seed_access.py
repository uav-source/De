from phase_a_execution_chain_test_support import actual_execution_chain


def test_audit_records_zero_formal_seed_access(actual_execution_chain):
    assert actual_execution_chain["manifest"]["FORMAL_PHASE_A_SEED_ACCESS_COUNT"] == 0
