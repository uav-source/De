from fastlio2_adapter.day8_token_capture_status import (
    CAPTURED_EMPTY_FORMAL_QUERY,
    CAPTURED_NONEMPTY,
    CAPTURE_FAILED,
    NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
    OVERFLOWED,
    compare_token_capture,
    resolve_token_capture_status,
)


def _query(scan=157, visited=1):
    return {"scan_index": scan, "visited_node_count": visited}


def _status(query, tokens=(), **changes):
    values = {
        "trace_enabled": True,
        "detailed_scan_start": 156,
        "detailed_scan_end": 158,
    }
    values.update(changes)
    return resolve_token_capture_status(query, tokens, **values)


def test_both_and_one_not_captured_are_not_applicable():
    outside = _status(_query(scan=157), detailed_scan_start=160,
                      detailed_scan_end=163)
    assert outside == NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW
    both = compare_token_capture(
        outside, outside, token_sequence_equal=True
    )
    assert both["token_comparison_status"] == "NOT_APPLICABLE"
    assert both["token_sequence_equal"] is None
    one = compare_token_capture(
        CAPTURED_NONEMPTY, outside, token_sequence_equal=False
    )
    assert one["root_cause_classification"] == (
        "EVIDENCE_GAP_DETAILED_TRACE_NOT_CAPTURED"
    )


def test_real_empty_nonempty_equal_and_different():
    empty = _status(_query(visited=0))
    assert empty == CAPTURED_EMPTY_FORMAL_QUERY
    assert compare_token_capture(
        empty, empty, token_sequence_equal=True
    )["token_sequence_equal"] is True
    token = [{"token_index": 0}]
    assert _status(_query(), token) == CAPTURED_NONEMPTY
    assert compare_token_capture(
        CAPTURED_NONEMPTY, CAPTURED_NONEMPTY, token_sequence_equal=True
    )["token_sequence_equal"] is True
    assert compare_token_capture(
        CAPTURED_NONEMPTY, CAPTURED_NONEMPTY, token_sequence_equal=False
    )["token_sequence_equal"] is False


def test_overflow_and_capture_failure_fail_capture_gate():
    assert _status(_query(), overflowed=True) == OVERFLOWED
    assert _status(_query()) == CAPTURE_FAILED
    assert compare_token_capture(
        OVERFLOWED, CAPTURED_NONEMPTY, token_sequence_equal=False
    )["capture_gate_pass"] is False


def test_scan157_old_window_not_captured_new_window_nonempty():
    token = [{"token_index": 0}]
    assert _status(
        _query(), token, detailed_scan_start=160, detailed_scan_end=163
    ) == NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW
    assert _status(_query(), token) == CAPTURED_NONEMPTY
