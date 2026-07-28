from phase_a_execution_chain_test_support import actual_execution_chain, published_execution_chain


def test_publisher_builds_ten_tables_and_five_figures_from_empty_directory(published_execution_chain):
    result = published_execution_chain["publication"]
    assert result["table_count"] == 10
    assert result["figure_count"] == 5
    assert result["publication_pass"] is True
