from fastlio2_adapter.day8_query_root_cause import compare_query_runs


def _query(sequence, formal):
    return {
        "query_sequence": sequence, "scan_index": 161,
        "map_mutation_call_index": 1, "batch_point_index": sequence,
        "candidate_point_sha256": "c" * 64,
        "voxel_identity": "0" * 48, "query_box_checksum": sequence,
        "formal_result_members": tuple(formal),
        "no_intersection_prune_count": 0, "full_cover_subtree_count": 0,
        "partial_intersection_node_count": 1,
    }


def _shadow(sequence, values, formal):
    return {
        "query_sequence": sequence,
        "shadow_member_hashes": ";".join(values),
        "formal_result_hashes": ";".join(formal),
    }


def test_first_divergence_preserves_previous_query_identity():
    a = "a" * 64
    left = [_query(1, [a]), _query(2, [a])]
    right = [_query(1, [a]), _query(2, [])]
    result = compare_query_runs(
        left_run_id="r1", right_run_id="r2",
        left_queries=left, right_queries=right,
        left_shadow_rows=[_shadow(1, [a], [a]), _shadow(2, [a], [a])],
        right_shadow_rows=[_shadow(1, [a], [a]), _shadow(2, [a], [])],
        left_tokens_by_query={}, right_tokens_by_query={},
    )
    first = result["first_divergence"]
    assert first["aligned_query_index"] == 1
    assert first["previous_query_equal"] is True
