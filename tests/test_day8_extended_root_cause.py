from fastlio2_adapter.day8_extended_query_root_cause import (
    classify_extended_query_difference,
)
from fastlio2_adapter.day8_token_capture_status import (
    CAPTURED_NONEMPTY,
    NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
)


POINT = "a" * 64
OTHER = "b" * 64


def _query(**updates):
    value = {
        "run_id": "run",
        "scan_index": 162,
        "map_mutation_call_index": 1,
        "batch_id": "7",
        "batch_point_index": 24,
        "candidate_point_sha256": "c" * 64,
        "voxel_identity": "d" * 48,
        "query_box_checksum": 9,
        "no_intersection_prune_count": 0,
    }
    value.update(updates)
    return value


def _shadow(formal):
    return {
        "shadow_member_hashes": POINT,
        "formal_result_hashes": ";".join(formal),
    }


def _token(**updates):
    value = {
        "token_index": 0,
        "depth": 0,
        "node_point_sha256": POINT,
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


def _classify(right_token, **right_query_updates):
    return classify_extended_query_difference(
        left_query=_query(),
        right_query=_query(**right_query_updates),
        left_shadow=_shadow((POINT,)),
        right_shadow=_shadow(()),
        left_status=CAPTURED_NONEMPTY,
        right_status=CAPTURED_NONEMPTY,
        left_tokens=[_token()],
        right_tokens=[right_token],
    )


def test_missing_member_visited_with_point_deleted():
    result = _classify(_token(
        point_deleted=1, current_point_returned=0
    ))
    assert result["classification"] == "DELETION_FLAG_VISIBILITY_DIVERGED"


def test_missing_member_visited_with_tree_deleted():
    result = _classify(_token(
        tree_deleted=1, current_point_returned=0
    ))
    assert result["classification"] == "DELETION_FLAG_VISIBILITY_DIVERGED"


def test_missing_member_unvisited_due_to_child_or_prune():
    result = _classify(
        _token(
            node_point_sha256=OTHER,
            query_relation="NO_INTERSECTION",
            current_point_inside_query=0,
            current_point_returned=0,
            left_child_visited=0,
        ),
        no_intersection_prune_count=1,
    )
    assert result["classification"] == "TREE_TRAVERSAL_PRUNING_DIVERGED"


def test_full_cover_flatten_result_difference():
    result = _classify(_token(
        query_relation="FULL_COVER",
        subtree_flatten_result_count=2,
        current_point_returned=0,
    ))
    assert result["classification"] == (
        "FULL_COVER_SUBTREE_FLATTEN_RESULT_DIVERGED"
    )


def test_not_captured_is_evidence_gap_not_same_trace():
    result = classify_extended_query_difference(
        left_query=_query(),
        right_query=_query(),
        left_shadow=_shadow((POINT,)),
        right_shadow=_shadow(()),
        left_status=NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        right_status=NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        left_tokens=[],
        right_tokens=[],
    )
    assert result["classification"] == "EVIDENCE_GAP"
    assert result["token_comparison_status"] == "NOT_APPLICABLE"
    assert result["token_sequence_equal"] is None


def test_same_captured_trace_different_result():
    result = _classify(_token())
    assert result["classification"] == (
        "SAME_CAPTURED_QUERY_TRACE_DIFFERENT_RESULT"
    )
