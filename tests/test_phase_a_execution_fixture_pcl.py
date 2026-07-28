from phase_a_execution_chain_test_support import actual_execution_chain, load_results


def test_actual_pcl_fixture_chain_has_three_schema_results(actual_execution_chain):
    rows = [row for row in load_results(actual_execution_chain["output"]) if row["backend"] == "pcl_point_to_plane"]
    assert len(rows) == 3
    assert all("exit_code" in row["backend_diagnostics"] for row in rows)
