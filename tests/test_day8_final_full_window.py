from fastlio2_adapter.day8_final_full_window_analysis import (
    DETAILED_TOKEN_SCAN_END,
    DETAILED_TOKEN_SCAN_START,
    MAIN_RUN_ID,
    ROS_MASTER_PORTS,
    RUN_IDS,
    token_capture_coverage,
)


def test_final_batch_identity_and_ports_are_frozen():
    assert MAIN_RUN_ID == "multihyp_day8_final_full_window_reproduction_v1"
    assert len(RUN_IDS) == 4
    assert list(ROS_MASTER_PORTS.values()) == [20911, 20912, 20913, 20914]
    assert (DETAILED_TOKEN_SCAN_START, DETAILED_TOKEN_SCAN_END) == (155, 165)


def test_full_window_coverage_requires_every_scan():
    queries = []
    tokens = {}
    sequence = 0
    for scan in range(155, 166):
        sequence += 1
        queries.append({
            "run_id": "run",
            "query_sequence": sequence,
            "scan_index": scan,
            "map_mutation_call_index": 1,
            "batch_id": "b",
            "batch_point_index": 0,
            "candidate_point_sha256": "a" * 64,
            "voxel_identity": "0" * 48,
            "query_box_checksum": 1,
            "visited_node_count": 1,
        })
        tokens[sequence] = [{"token_index": 0}]
    rows, summary = token_capture_coverage(queries, tokens)
    assert len(rows) == 11
    assert summary["FULL_WINDOW_QUERY_SUMMARY_COVERAGE_PASS"]
    assert summary["FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS"]
    assert all(
        value["query_with_detailed_token_count"] == value["query_count"] == 1
        for value in summary["per_scan"].values()
    )


def test_missing_one_scan_fails_full_window_coverage():
    queries = [{
        "run_id": "run",
        "query_sequence": 1,
        "scan_index": 155,
        "map_mutation_call_index": 1,
        "batch_id": "b",
        "batch_point_index": 0,
        "candidate_point_sha256": "a" * 64,
        "voxel_identity": "0" * 48,
        "query_box_checksum": 1,
        "visited_node_count": 1,
    }]
    _, summary = token_capture_coverage(queries, {1: [{"token_index": 0}]})
    assert not summary["FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS"]
