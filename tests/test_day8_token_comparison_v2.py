import json

import pytest

from fastlio2_adapter.day8_token_comparison_v2 import (
    EVIDENCE_GAP_NOT_CAPTURED,
    audit_null_token_semantics,
    compare_token_sequences,
    json_null_roundtrip_pass,
    validate_comparison_record,
)
from fastlio2_adapter.day8_token_capture_status import (
    CAPTURED_EMPTY_FORMAL_QUERY,
    CAPTURED_NONEMPTY,
    CAPTURE_FAILED,
    NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
    NOT_CAPTURED_TRACE_DISABLED,
    OVERFLOWED,
)


def _token(**updates):
    value = {
        "token_index": 0,
        "depth": 0,
        "node_point_sha256": "a" * 64,
        "node_range_checksum": 1,
        "query_relation": "PARTIAL_INTERSECTION",
        "point_deleted": 0,
        "tree_deleted": 0,
        "current_point_inside_query": 1,
        "current_point_returned": 1,
        "left_child_considered": 1,
        "left_child_visited": 1,
        "right_child_considered": 0,
        "right_child_visited": 0,
        "subtree_flatten_result_count": 0,
        "rebuild_active": 0,
        "rebuild_generation": 0,
        "token_checksum": 1,
    }
    value.update(updates)
    return value


@pytest.mark.parametrize(
    "left,right",
    [
        (
            NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
            NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        ),
        (NOT_CAPTURED_TRACE_DISABLED, CAPTURED_NONEMPTY),
        (CAPTURED_NONEMPTY, NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW),
    ],
)
def test_not_captured_is_never_an_equal_empty_trace(left, right):
    value = compare_token_sequences(left, right, (), ())
    assert value["token_comparison_status"] == "NOT_APPLICABLE"
    assert value["token_sequence_equal"] is None
    assert value["classification"] == "EVIDENCE_GAP"
    assert value["root_cause_classification"] == EVIDENCE_GAP_NOT_CAPTURED


def test_captured_nonempty_equal_and_different():
    same = compare_token_sequences(
        CAPTURED_NONEMPTY, CAPTURED_NONEMPTY, [_token()], [_token()]
    )
    different = compare_token_sequences(
        CAPTURED_NONEMPTY,
        CAPTURED_NONEMPTY,
        [_token()],
        [_token(left_child_visited=0)],
    )
    assert same["token_comparison_status"] == "APPLICABLE"
    assert same["token_sequence_equal"] is True
    assert different["token_sequence_equal"] is False


def test_genuinely_captured_empty_query_is_comparable():
    value = compare_token_sequences(
        CAPTURED_EMPTY_FORMAL_QUERY,
        CAPTURED_EMPTY_FORMAL_QUERY,
        (),
        (),
    )
    assert value["token_comparison_status"] == "APPLICABLE"
    assert value["token_sequence_equal"] is True


@pytest.mark.parametrize("fatal", [CAPTURE_FAILED, OVERFLOWED])
def test_capture_failure_or_overflow_fails_gate(fatal):
    value = compare_token_sequences(
        fatal, CAPTURED_NONEMPTY, (), [_token()]
    )
    assert value["capture_gate_pass"] is False
    assert value["token_comparison_status"] == "NOT_APPLICABLE"
    assert value["token_sequence_equal"] is None


def test_null_json_roundtrip_and_nested_audit():
    assert json_null_roundtrip_pass()
    value = compare_token_sequences(
        NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        (),
        (),
    )
    restored = json.loads(json.dumps(value))
    assert restored["token_sequence_equal"] is None
    audit = audit_null_token_semantics({"pairwise": {"rows": [restored]}})
    assert audit["NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS"] is True


def test_validator_rejects_historical_null_token_regression():
    value = compare_token_sequences(
        NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        (),
        (),
    )
    value["token_comparison_status"] = "APPLICABLE"
    value["token_sequence_equal"] = True
    with pytest.raises(ValueError):
        validate_comparison_record(value)
