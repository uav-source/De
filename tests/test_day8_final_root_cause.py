from fastlio2_adapter.day8_final_traversal_root_cause import (
    _classify_path,
)


def witness(*, point_deleted=False, tree_deleted=False):
    return {
        "point_deleted_when_visited": point_deleted,
        "tree_deleted_when_visited": tree_deleted,
    }


def test_deleted_visibility_classification():
    value = _classify_path(
        {"differing_fields": ["point_deleted"]},
        witness(),
        witness(point_deleted=True),
        token_equal=False,
    )
    assert value == "DELETION_FLAG_VISIBILITY_DIVERGED"


def test_child_prune_and_flatten_classification():
    prune = _classify_path(
        {"differing_fields": ["left_child_visited"]},
        witness(),
        witness(),
        token_equal=False,
    )
    flatten = _classify_path(
        {"differing_fields": ["subtree_flatten_result_count"]},
        witness(),
        witness(),
        token_equal=False,
    )
    assert prune == "TREE_TRAVERSAL_PRUNING_DIVERGED"
    assert flatten == "FULL_COVER_SUBTREE_FLATTEN_RESULT_DIVERGED"


def test_same_trace_different_result_is_not_localized_bug():
    value = _classify_path(
        {"differing_fields": []},
        witness(),
        witness(),
        token_equal=True,
    )
    assert value == "SAME_CAPTURED_QUERY_TRACE_DIFFERENT_RESULT"
