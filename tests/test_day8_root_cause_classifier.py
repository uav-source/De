from fastlio2_adapter.day8_query_root_cause import (
    classify_query_difference,
)


A = "a" * 64


def _query(**changes):
    value = {
        "candidate_point_sha256": "c" * 64,
        "voxel_identity": "0" * 48, "query_box_checksum": 1,
        "rebuild_active": 0, "rebuild_subtree_observed_count": 0,
        "no_intersection_prune_count": 0,
        "full_cover_subtree_count": 0,
        "partial_intersection_node_count": 1,
    }
    value.update(changes)
    return value


def _shadow(shadow=A, formal=A):
    return {
        "shadow_member_hashes": shadow,
        "formal_result_hashes": formal,
    }


def _token(**changes):
    value = {
        "token_index": 0, "depth": 0, "node_point_sha256": A,
        "node_range_checksum": 1, "query_relation": "PARTIAL_INTERSECTION",
        "point_deleted": 0, "tree_deleted": 0,
        "current_point_inside_query": 1, "current_point_returned": 1,
        "left_child_considered": 0, "left_child_visited": 0,
        "right_child_considered": 0, "right_child_visited": 0,
        "subtree_flatten_result_count": 0, "rebuild_active": 0,
        "rebuild_generation": 0, "token_checksum": 1,
    }
    value.update(changes)
    return value


def _class(left_q, right_q, left_s, right_s, left_t=(), right_t=()):
    return classify_query_difference(
        left_query=left_q, right_query=right_q,
        left_shadow=left_s, right_shadow=right_s,
        left_tokens=left_t, right_tokens=right_t,
    )["classification"]


def test_input_shadow_and_same_trace_classifications():
    assert _class(
        _query(), _query(query_box_checksum=2), _shadow(), _shadow()
    ) == "QUERY_INPUT_DIVERGED"
    assert _class(
        _query(), _query(), _shadow(), _shadow(shadow="b" * 64)
    ) == "SHADOW_LOGICAL_VOXEL_MEMBERSHIP_DIVERGED"
    assert _class(
        _query(), _query(), _shadow(formal=A), _shadow(formal=""),
        [_token()], [_token()],
    ) == "SAME_QUERY_TRACE_DIFFERENT_RESULT"


def test_deleted_pruning_and_tree_shape_classifications():
    assert _class(
        _query(), _query(), _shadow(formal=A), _shadow(formal=""),
        [_token()], [_token(point_deleted=1, current_point_returned=0)],
    ) == "DELETION_FLAG_VISIBILITY_DIVERGED"
    assert _class(
        _query(), _query(no_intersection_prune_count=1),
        _shadow(formal=A), _shadow(formal=""),
        [_token()], [_token(query_relation="NO_INTERSECTION")],
    ) == "TREE_TRAVERSAL_PRUNING_DIVERGED"
    assert _class(
        _query(), _query(), _shadow(), _shadow(),
        [_token()], [_token(depth=1)],
    ) == "TREE_SHAPE_DIFFERED_BUT_RESULT_COMPLETE"


def test_classifier_never_auto_proves_bug_or_authorizes_day9():
    result = classify_query_difference(
        left_query=_query(), right_query=_query(),
        left_shadow=_shadow(), right_shadow=_shadow(),
        left_tokens=[], right_tokens=[],
    )
    assert result["bug_proven"] is False
    assert result["day9_authorized"] is False
