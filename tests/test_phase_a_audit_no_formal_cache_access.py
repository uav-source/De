from phase_a_execution_chain_test_support import actual_execution_chain


def test_audit_records_zero_formal_stage0_cache_reads(actual_execution_chain):
    assert actual_execution_chain["manifest"]["FORMAL_STAGE0_CACHE_READ_COUNT"] == 0
