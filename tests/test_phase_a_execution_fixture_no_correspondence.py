from phase_a_execution_chain_test_support import actual_execution_chain, load_results


def test_separated_fixture_is_a_valid_failure_result(actual_execution_chain):
    rows = [row for row in load_results(actual_execution_chain["output"]) if row["condition"] == "FIXTURE_NO_CORRESPONDENCE"]
    assert len(rows) == 2
    assert all(row["solver_failure"] for row in rows)
    assert all(row["failure_classification"] in {"NO_CORRESPONDENCES", "SCIENTIFIC_SOLVER_FAILURE"} for row in rows)
