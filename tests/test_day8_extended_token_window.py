from fastlio2_adapter.day8_extended_token_window import (
    DETAILED_TOKEN_SCAN_END,
    DETAILED_TOKEN_SCAN_START,
    in_detailed_window,
    token_capture_coverage,
)
from fastlio2_adapter.day8_token_capture_status import (
    CAPTURED_NONEMPTY,
    NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
)


def _query(scan, sequence):
    return {
        "run_id": "run",
        "query_sequence": sequence,
        "scan_index": scan,
        "map_mutation_call_index": 1,
        "batch_id": "1",
        "batch_point_index": sequence,
        "candidate_point_sha256": "a" * 64,
        "voxel_identity": "b" * 48,
        "query_box_checksum": sequence,
        "visited_node_count": 1,
    }


def _token(sequence):
    return {"query_sequence": sequence, "token_index": 0}


def test_authorized_detailed_window_boundaries():
    assert (DETAILED_TOKEN_SCAN_START, DETAILED_TOKEN_SCAN_END) == (156, 163)
    assert in_detailed_window(157)
    assert in_detailed_window(162)
    assert in_detailed_window(163)
    assert not in_detailed_window(155)
    assert not in_detailed_window(164)


def test_scan157_and_scan162_full_coverage():
    queries = [_query(scan, index) for index, scan in enumerate(
        [155, 156, 157, 162, 163, 164], start=1
    )]
    tokens = {
        int(query["query_sequence"]): [_token(query["query_sequence"])]
        for query in queries if in_detailed_window(query["scan_index"])
    }
    rows, summary = token_capture_coverage(queries, tokens)
    by_scan = {row["scan_index"]: row for row in rows}
    assert by_scan[155]["token_capture_status"] == (
        NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW
    )
    assert by_scan[157]["token_capture_status"] == CAPTURED_NONEMPTY
    assert by_scan[162]["token_capture_status"] == CAPTURED_NONEMPTY
    assert summary["scan157_token_coverage_pass"] is True
    assert summary["scan162_token_coverage_pass"] is True


def test_missing_in_window_tokens_are_capture_failure():
    queries = [_query(162, 1)]
    rows, summary = token_capture_coverage(queries, {})
    assert rows[0]["token_capture_status"] == "CAPTURE_FAILED"
    assert summary["token_capture_failure_count"] == 1
    assert summary["scan162_token_coverage_pass"] is False
