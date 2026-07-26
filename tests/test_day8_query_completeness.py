from fastlio2_adapter.day8_shadow_voxel_replay import (
    compare_query_to_shadow,
)


def _query(members):
    return {
        "scan_index": 161, "map_mutation_call_index": 1,
        "batch_point_index": 200, "query_sequence": 1,
        "candidate_point_sha256": "c" * 64, "voxel_identity": "0" * 48,
        "query_box_checksum": 1, "formal_result_members": tuple(members),
    }


def test_complete_and_missing_unexpected_members_are_explicit():
    a, b = "a" * 64, "b" * 64
    complete = compare_query_to_shadow(
        _query([a]), {"0" * 48: {a}}, run_id="r1"
    )
    assert complete["formal_query_completeness_pass"] == 1
    missing = compare_query_to_shadow(
        _query([]), {"0" * 48: {a}}, run_id="r1"
    )
    assert missing["missing_from_formal_result"] == a
    unexpected = compare_query_to_shadow(
        _query([a, b]), {"0" * 48: {a}}, run_id="r1"
    )
    assert unexpected["unexpected_in_formal_result"] == b
    assert unexpected["formal_query_completeness_pass"] == 0
