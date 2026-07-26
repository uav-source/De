from fastlio2_adapter.day8_focused_traversal_remediation import (
    DETAILED_TOKEN_SCAN_END,
    DETAILED_TOKEN_SCAN_START,
    QUERY_SUMMARY_SCAN_END,
    QUERY_SUMMARY_SCAN_START,
    token_capture_coverage,
)


def test_focused_windows_are_exact_and_scan157_is_covered():
    assert (QUERY_SUMMARY_SCAN_START, QUERY_SUMMARY_SCAN_END) == (155, 165)
    assert (DETAILED_TOKEN_SCAN_START, DETAILED_TOKEN_SCAN_END) == (156, 158)
    query = {
        "run_id": "r1", "query_sequence": 1, "scan_index": 157,
        "map_mutation_call_index": 1, "batch_id": "b",
        "batch_point_index": 42, "candidate_point_sha256": "a" * 64,
        "voxel_identity": "0" * 48, "query_box_checksum": 1,
        "visited_node_count": 2,
    }
    rows, summary = token_capture_coverage(
        [query], {1: [{"token_index": 0}]}
    )
    assert rows[0]["token_capture_status"] == "CAPTURED_NONEMPTY"
    assert summary["scan157_token_coverage_pass"] is True
