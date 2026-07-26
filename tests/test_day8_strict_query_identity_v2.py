from fastlio2_adapter.day8_strict_query_identity_v2 import (
    align_strict_query_streams,
    check_previous_query_identity,
    compare_formal_members,
    strict_query_identity,
)


def query(candidate, sequence=1, formal=()):
    return {
        "scan_index": 155,
        "map_mutation_call_index": 1,
        "batch_id": "batch",
        "batch_point_index": sequence - 1,
        "candidate_point_sha256": candidate,
        "voxel_identity": "0" * 48,
        "query_box_checksum": 7,
        "formal_result_members": tuple(formal),
    }


def test_identity_includes_all_v2_fields():
    value = strict_query_identity(query("a" * 64))
    assert value == (155, 1, "batch", 0, "a" * 64, "0" * 48, 7)


def test_equal_partial_and_disjoint_identity_streams():
    first = query("a" * 64)
    left = [first, query("b" * 64, 2)]
    equal = align_strict_query_streams(left, [dict(row) for row in left])
    assert equal["identity_stream_equal"]
    assert equal["common_identity_count"] == 2
    partial = align_strict_query_streams(
        left, [dict(first), query("c" * 64, 2)]
    )
    assert partial["common_identity_count"] == 1
    assert partial["aligned_prefix_length"] == 1
    disjoint = align_strict_query_streams(
        [first], [query("d" * 64)]
    )
    assert disjoint["identity_stream_classification"] == (
        "NO_STRICT_QUERY_IDENTITY_OVERLAP"
    )
    assert disjoint["aligned_prefix_length"] == 0


def test_alignment_is_not_positional():
    common = query("a" * 64)
    left = [query("x" * 64), common]
    right = [common, query("y" * 64)]
    value = align_strict_query_streams(left, right)
    assert value["common_identity_count"] == 1
    assert value["_common_identities"] == [strict_query_identity(common)]
    assert value["aligned_prefix_length"] == 0


def test_member_set_and_order_are_separate():
    same_set = compare_formal_members(
        {"formal_result_members": ("a", "b")},
        {"formal_result_members": ("b", "a")},
    )
    assert same_set["classification"] == (
        "FORMAL_RESULT_ORDER_DIVERGED_SET_EQUAL"
    )
    different = compare_formal_members(
        {"formal_result_members": ("a",)},
        {"formal_result_members": ("b",)},
    )
    assert different["classification"] == (
        "STRICT_IDENTITY_FORMAL_MEMBER_SET_DIVERGED"
    )


def test_previous_query_rejects_earlier_stream_divergence():
    current = query("a" * 64, 2)
    left = [query("x" * 64), current]
    right = [query("y" * 64), dict(current)]
    alignment = align_strict_query_streams(left, right)
    value = check_previous_query_identity(
        alignment=alignment,
        current_identity=strict_query_identity(current),
        left_shadow_by_identity={},
        right_shadow_by_identity={},
        left_formal_by_identity={},
        right_formal_by_identity={},
        left_token_status_by_identity={},
        right_token_status_by_identity={},
        left_token_signature_by_identity={},
        right_token_signature_by_identity={},
    )
    assert not value["PREVIOUS_QUERY_IDENTITY_PASS"]
    assert value["classification"] == (
        "QUERY_STREAM_DIVERGED_BEFORE_RESULT_WITNESS"
    )


def test_previous_query_accepts_complete_matched_context():
    previous = query("p" * 64)
    current = query("c" * 64, 2)
    alignment = align_strict_query_streams(
        [previous, current], [dict(previous), dict(current)]
    )
    prior = strict_query_identity(previous)
    value = check_previous_query_identity(
        alignment=alignment,
        current_identity=strict_query_identity(current),
        left_shadow_by_identity={prior: ("a",)},
        right_shadow_by_identity={prior: ("a",)},
        left_formal_by_identity={prior: ("a",)},
        right_formal_by_identity={prior: ("a",)},
        left_token_status_by_identity={prior: "CAPTURED_NONEMPTY"},
        right_token_status_by_identity={prior: "CAPTURED_NONEMPTY"},
        left_token_signature_by_identity={prior: "one"},
        right_token_signature_by_identity={prior: "one"},
    )
    assert value["PREVIOUS_QUERY_IDENTITY_PASS"]
    assert value["classification"] == "PREVIOUS_QUERY_IDENTITY_MATCHED"
