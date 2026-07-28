from phase_a_execution_chain_test_support import actual_execution_chain


def test_every_fixture_backend_input_matches_the_snapshot_lock(actual_execution_chain):
    audit = actual_execution_chain["analysis"]["input_pairing_audit"]
    assert len(audit) == 6
    assert all(row["checksum_match"] for row in audit)
