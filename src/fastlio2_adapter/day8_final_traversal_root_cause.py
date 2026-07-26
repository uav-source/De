"""Token-level witness construction for the final Day 8 replay batch."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Mapping, Sequence

from .day8_strict_query_identity_v2 import (
    check_previous_query_identity,
    identity_key,
    strict_query_identity,
)
from .day8_token_semantics_v3 import compare_token_sequences
from .day8_traversal_analysis import (
    TOKEN_FIELDS,
    missing_point_witness,
    traversal_diff_rows,
    traversal_signature,
)


ROOT_CAUSE_CLASSIFICATIONS = {
    "QUERY_STREAM_IDENTITY_DIVERGED",
    "NO_STRICT_QUERY_IDENTITY_OVERLAP",
    "FORMAL_RESULT_ORDER_DIVERGED_SET_EQUAL",
    "SHADOW_LOGICAL_VOXEL_MEMBERSHIP_DIVERGED",
    "DELETION_FLAG_VISIBILITY_DIVERGED",
    "REBUILD_SUBTREE_VISIBILITY_DIVERGED",
    "TREE_TRAVERSAL_PRUNING_DIVERGED",
    "FULL_COVER_SUBTREE_FLATTEN_RESULT_DIVERGED",
    "FORMAL_RANGE_SEARCH_RESULT_INCOMPLETE_WITH_MATCHED_LOGICAL_MEMBERSHIP",
    "TREE_SHAPE_DIFFERED_BUT_RESULT_COMPLETE",
    "SAME_CAPTURED_QUERY_TRACE_DIFFERENT_RESULT",
    "NO_STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED",
    "EVIDENCE_GAP",
}
LOCALIZED_CLASSIFICATIONS = {
    "DELETION_FLAG_VISIBILITY_DIVERGED",
    "REBUILD_SUBTREE_VISIBILITY_DIVERGED",
    "TREE_TRAVERSAL_PRUNING_DIVERGED",
    "FULL_COVER_SUBTREE_FLATTEN_RESULT_DIVERGED",
}


def _first_token_difference(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    for index in range(max(len(left), len(right))):
        a = left[index] if index < len(left) else None
        b = right[index] if index < len(right) else None
        differing = (
            ["record_presence"]
            if a is None or b is None else
            [field for field in TOKEN_FIELDS if a.get(field) != b.get(field)]
        )
        if differing:
            return {
                "first_divergent_traversal_token_index": index,
                "differing_fields": differing,
                "left_token": dict(a) if a is not None else None,
                "right_token": dict(b) if b is not None else None,
            }
    return {
        "first_divergent_traversal_token_index": None,
        "differing_fields": [],
        "left_token": None,
        "right_token": None,
    }


def _classify_path(
    first: Mapping[str, Any],
    left_witness: Mapping[str, Any],
    right_witness: Mapping[str, Any],
    *,
    token_equal: bool,
) -> str:
    fields = set(first["differing_fields"])
    if (
        left_witness["point_deleted_when_visited"]
        != right_witness["point_deleted_when_visited"]
        or left_witness["tree_deleted_when_visited"]
        != right_witness["tree_deleted_when_visited"]
    ):
        return "DELETION_FLAG_VISIBILITY_DIVERGED"
    if fields & {"rebuild_active", "rebuild_generation"}:
        return "REBUILD_SUBTREE_VISIBILITY_DIVERGED"
    if "subtree_flatten_result_count" in fields:
        return "FULL_COVER_SUBTREE_FLATTEN_RESULT_DIVERGED"
    if fields & {
        "node_point_sha256",
        "node_range_checksum",
        "query_relation",
        "left_child_considered",
        "left_child_visited",
        "right_child_considered",
        "right_child_visited",
        "record_presence",
    }:
        return "TREE_TRAVERSAL_PRUNING_DIVERGED"
    if token_equal:
        return "SAME_CAPTURED_QUERY_TRACE_DIFFERENT_RESULT"
    return "FORMAL_RANGE_SEARCH_RESULT_INCOMPLETE_WITH_MATCHED_LOGICAL_MEMBERSHIP"


def analyze_first_strict_divergence(
    *,
    pair: Mapping[str, Any],
    alignment: Mapping[str, Any],
    left_queries: Sequence[Mapping[str, Any]],
    right_queries: Sequence[Mapping[str, Any]],
    left_shadow_by_identity: Mapping[tuple[Any, ...], Sequence[str]],
    right_shadow_by_identity: Mapping[tuple[Any, ...], Sequence[str]],
    left_tokens_by_sequence: Mapping[int, Sequence[Mapping[str, Any]]],
    right_tokens_by_sequence: Mapping[int, Sequence[Mapping[str, Any]]],
    left_status_by_sequence: Mapping[int, str],
    right_status_by_sequence: Mapping[int, str],
) -> dict[str, Any]:
    witness = pair.get("first_strict_formal_member_set_divergence")
    if witness is None:
        classification = str(pair["root_cause_classification"])
        if classification not in ROOT_CAUSE_CLASSIFICATIONS:
            classification = "EVIDENCE_GAP"
        return {
            "schema_version": "day8_final_traversal_root_cause_v1",
            "first_strict_formal_member_set_divergence": None,
            "previous_query_identity": {
                "PREVIOUS_QUERY_IDENTITY_PASS": False,
                "classification": "NOT_APPLICABLE_NO_STRICT_DIVERGENCE",
            },
            "traversal_diff_rows": [],
            "missing_expected_point_witness": None,
            "root_cause_classification": classification,
            "IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED": False,
        }
    identity = strict_query_identity(witness["left_query"])
    left_sequence = int(witness["left_query_sequence"])
    right_sequence = int(witness["right_query_sequence"])
    left_tokens = left_tokens_by_sequence.get(left_sequence, ())
    right_tokens = right_tokens_by_sequence.get(right_sequence, ())
    token = compare_token_sequences(
        left_status_by_sequence[left_sequence],
        right_status_by_sequence[right_sequence],
        left_tokens,
        right_tokens,
    )
    left_members = tuple(witness["left_formal_members"])
    right_members = tuple(witness["right_formal_members"])
    missing_right = list((Counter(left_members) - Counter(right_members)).elements())
    missing_left = list((Counter(right_members) - Counter(left_members)).elements())
    if missing_right:
        expected = missing_right[0]
        containing_side = "left"
        missing_side = "right"
    elif missing_left:
        expected = missing_left[0]
        containing_side = "right"
        missing_side = "left"
    else:
        raise ValueError("strict divergence has no missing formal member")
    left_expected = missing_point_witness(expected, left_tokens)
    right_expected = missing_point_witness(expected, right_tokens)
    first = _first_token_difference(left_tokens, right_tokens)
    rows = traversal_diff_rows(
        str(pair["left_run_id"]),
        str(pair["right_run_id"]),
        identity_key(identity),
        left_tokens,
        right_tokens,
    )
    classification = (
        "EVIDENCE_GAP"
        if token["token_comparison_status"] != "APPLICABLE" else
        _classify_path(
            first,
            left_expected,
            right_expected,
            token_equal=bool(token["token_sequence_equal"]),
        )
    )
    left_query_index = {
        strict_query_identity(row): row for row in left_queries
    }
    right_query_index = {
        strict_query_identity(row): row for row in right_queries
    }
    left_formal = {
        item: tuple(row.get("formal_result_members", ()))
        for item, row in left_query_index.items()
    }
    right_formal = {
        item: tuple(row.get("formal_result_members", ()))
        for item, row in right_query_index.items()
    }
    left_status = {
        item: left_status_by_sequence[int(row["query_sequence"])]
        for item, row in left_query_index.items()
    }
    right_status = {
        item: right_status_by_sequence[int(row["query_sequence"])]
        for item, row in right_query_index.items()
    }
    left_signature = {
        item: traversal_signature(
            left_tokens_by_sequence.get(int(row["query_sequence"]), ())
        ) if left_status[item].startswith("CAPTURED_") else None
        for item, row in left_query_index.items()
    }
    right_signature = {
        item: traversal_signature(
            right_tokens_by_sequence.get(int(row["query_sequence"]), ())
        ) if right_status[item].startswith("CAPTURED_") else None
        for item, row in right_query_index.items()
    }
    previous = check_previous_query_identity(
        alignment=alignment,
        current_identity=identity,
        left_shadow_by_identity=left_shadow_by_identity,
        right_shadow_by_identity=right_shadow_by_identity,
        left_formal_by_identity=left_formal,
        right_formal_by_identity=right_formal,
        left_token_status_by_identity=left_status,
        right_token_status_by_identity=right_status,
        left_token_signature_by_identity=left_signature,
        right_token_signature_by_identity=right_signature,
    )
    missing_witness = {
        "missing_expected_point_sha256": expected,
        "containing_formal_result_side": containing_side,
        "missing_formal_result_side": missing_side,
        "expected_member_logically_valid_left": (
            expected in left_shadow_by_identity.get(identity, ())
        ),
        "expected_member_logically_valid_right": (
            expected in right_shadow_by_identity.get(identity, ())
        ),
        "expected_member_visited": {
            "left": left_expected["visited"],
            "right": right_expected["visited"],
        },
        "left": left_expected,
        "right": right_expected,
    }
    localized = (
        classification in LOCALIZED_CLASSIFICATIONS
        and previous["PREVIOUS_QUERY_IDENTITY_PASS"] is True
        and missing_witness["expected_member_logically_valid_left"]
        and missing_witness["expected_member_logically_valid_right"]
    )
    return {
        "schema_version": "day8_final_traversal_root_cause_v1",
        "first_strict_formal_member_set_divergence": witness,
        "previous_query_identity": previous,
        "token_comparison": token,
        "first_divergent_traversal_token": first,
        "traversal_diff_rows": rows,
        "missing_expected_point_witness": missing_witness,
        "root_cause_classification": classification,
        "IKDTREE_RANGE_SEARCH_CONTEXT_ROOT_CAUSE_LOCALIZED": localized,
        "FORMAL_IKDTREE_BUG_PROVEN": False,
        "DATA_RACE_PROVEN": False,
        "DAY9_AUTHORIZED": False,
    }


__all__ = [
    "LOCALIZED_CLASSIFICATIONS",
    "ROOT_CAUSE_CLASSIFICATIONS",
    "analyze_first_strict_divergence",
]
