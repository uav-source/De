from phase_a_execution_chain_test_support import actual_execution_chain, load_results


def test_identity_fixture_produces_two_valid_success_results(actual_execution_chain):
    rows = [row for row in load_results(actual_execution_chain["output"]) if row["condition"] == "FIXTURE_IDENTITY"]
    assert len(rows) == 2
    assert all(not row["solver_failure"] and row["finite_output"] for row in rows)
