from phase_a_execution_chain_test_support import actual_execution_chain, load_results


def test_nonidentity_reference_fixture_preserves_transform_direction(actual_execution_chain):
    rows = [row for row in load_results(actual_execution_chain["output"]) if row["condition"] == "FIXTURE_NONIDENTITY_REFERENCE"]
    assert len(rows) == 2
    assert all(not row["solver_failure"] for row in rows)
    assert all(row["translation_update_m"] < 1e-4 for row in rows)
