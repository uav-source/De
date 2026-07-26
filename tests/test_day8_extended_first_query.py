from fastlio2_adapter.day8_extended_query_root_cause import (
    compare_extended_query_runs,
    extended_query_identity,
)
from fastlio2_adapter.day8_token_capture_status import CAPTURED_NONEMPTY


def _query(sequence, formal=()):
    return {
        "run_id": "run",
        "query_sequence": sequence,
        "scan_index": 162,
        "map_mutation_call_index": 1,
        "batch_id": "7",
        "batch_point_index": sequence,
        "candidate_point_sha256": "c" * 64,
        "voxel_identity": "d" * 48,
        "query_box_checksum": sequence,
        "formal_result_members": formal,
        "no_intersection_prune_count": 0,
    }


def _shadow(sequence, formal):
    return {
        "query_sequence": sequence,
        "shadow_member_hashes": "a" * 64,
        "formal_result_hashes": ";".join(formal),
        "shadow_state_accounting_pass": 1,
    }


def _token(sequence, **updates):
    value = {
        "query_sequence": sequence,
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


def test_extended_identity_includes_batch_id():
    left = _query(1)
    right = dict(left, batch_id="8")
    assert extended_query_identity(left) != extended_query_identity(right)


def test_first_formal_divergence_and_previous_query_identity():
    point = "a" * 64
    left_queries = [_query(1, (point,)), _query(2, (point,))]
    right_queries = [_query(1, (point,)), _query(2, ())]
    left_shadow = [_shadow(1, (point,)), _shadow(2, (point,))]
    right_shadow = [_shadow(1, (point,)), _shadow(2, ())]
    tokens = {1: [_token(1)], 2: [_token(2)]}
    result = compare_extended_query_runs(
        left_run_id="left",
        right_run_id="right",
        left_queries=left_queries,
        right_queries=right_queries,
        left_shadow_rows=left_shadow,
        right_shadow_rows=right_shadow,
        left_tokens_by_query=tokens,
        right_tokens_by_query=tokens,
        left_status_by_query={1: CAPTURED_NONEMPTY, 2: CAPTURED_NONEMPTY},
        right_status_by_query={1: CAPTURED_NONEMPTY, 2: CAPTURED_NONEMPTY},
    )
    first = result["first_divergence"]
    assert first["aligned_query_index"] == 1
    assert first["previous_query_equal"] is True
    assert first["root_cause"]["classification"] == (
        "SAME_CAPTURED_QUERY_TRACE_DIFFERENT_RESULT"
    )


def test_no_query_divergence():
    point = "a" * 64
    queries = [_query(1, (point,))]
    shadow = [_shadow(1, (point,))]
    tokens = {1: [_token(1)]}
    result = compare_extended_query_runs(
        left_run_id="left",
        right_run_id="right",
        left_queries=queries,
        right_queries=queries,
        left_shadow_rows=shadow,
        right_shadow_rows=shadow,
        left_tokens_by_query=tokens,
        right_tokens_by_query=tokens,
        left_status_by_query={1: CAPTURED_NONEMPTY},
        right_status_by_query={1: CAPTURED_NONEMPTY},
    )
    assert result["first_divergence"]["aligned_query_index"] is None
