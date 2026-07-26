"""Detailed, capture-aware traversal witnesses for the Day 8 extension."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .day8_token_comparison_v2 import compare_token_sequences
from .day8_traversal_analysis import (
    TOKEN_FIELDS,
    missing_point_witness,
    traversal_diff_rows,
)


def detailed_traversal_difference(
    *,
    left_run_id: str,
    right_run_id: str,
    query_identity: str,
    left_status: str,
    right_status: str,
    left_tokens: Sequence[Mapping[str, Any]],
    right_tokens: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    comparison = compare_token_sequences(
        left_status, right_status, left_tokens, right_tokens
    )
    if comparison["token_comparison_status"] != "APPLICABLE":
        return {
            **comparison,
            "first_divergent_traversal_token_index": None,
            "first_divergent_node_point_sha256": None,
            "first_divergent_node_range_checksum": None,
            "first_divergent_query_relation": None,
            "differing_fields": [],
            "rows": [],
        }
    rows = traversal_diff_rows(
        left_run_id,
        right_run_id,
        query_identity,
        left_tokens,
        right_tokens,
    )
    first_index = int(rows[0]["token_index"]) if rows else None
    left = (
        left_tokens[first_index]
        if first_index is not None and first_index < len(left_tokens)
        else {}
    )
    right = (
        right_tokens[first_index]
        if first_index is not None and first_index < len(right_tokens)
        else {}
    )
    differing = (
        rows[0]["differing_fields"].split(";") if rows else []
    )
    return {
        **comparison,
        "first_divergent_traversal_token_index": first_index,
        "first_divergent_node_point_sha256": {
            "left": left.get("node_point_sha256"),
            "right": right.get("node_point_sha256"),
        } if first_index is not None else None,
        "first_divergent_node_range_checksum": {
            "left": left.get("node_range_checksum"),
            "right": right.get("node_range_checksum"),
        } if first_index is not None else None,
        "first_divergent_query_relation": {
            "left": left.get("query_relation"),
            "right": right.get("query_relation"),
        } if first_index is not None else None,
        "differing_fields": differing,
        "left_token": dict(left) if left else None,
        "right_token": dict(right) if right else None,
        "rows": rows,
    }


def missing_expected_point_analysis(
    point_sha256: str,
    left_tokens: Sequence[Mapping[str, Any]],
    right_tokens: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    left = missing_point_witness(point_sha256, left_tokens)
    right = missing_point_witness(point_sha256, right_tokens)
    return {
        "missing_expected_point_sha256": point_sha256,
        "left": left,
        "right": right,
        "expected_member_visited": {
            "left": left["visited"],
            "right": right["visited"],
        },
        "point_deleted_difference": (
            left["point_deleted_when_visited"]
            != right["point_deleted_when_visited"]
        ),
        "tree_deleted_difference": (
            left["tree_deleted_when_visited"]
            != right["tree_deleted_when_visited"]
        ),
        "returned_difference": (
            left["returned_when_visited"] != right["returned_when_visited"]
        ),
    }


def first_path_explanation(
    traversal: Mapping[str, Any],
) -> dict[str, Any]:
    left = traversal.get("left_token") or {}
    right = traversal.get("right_token") or {}
    fields = set(traversal.get("differing_fields", ()))
    return {
        "first_divergent_token_index":
            traversal.get("first_divergent_traversal_token_index"),
        "node_identity_or_range_diverged": bool(
            fields & {"node_point_sha256", "node_range_checksum"}
        ),
        "query_relation_diverged": "query_relation" in fields,
        "child_considered_or_visited_diverged": bool(fields & {
            "left_child_considered",
            "left_child_visited",
            "right_child_considered",
            "right_child_visited",
        }),
        "deleted_visibility_diverged": bool(
            fields & {"point_deleted", "tree_deleted"}
        ),
        "full_cover_flatten_diverged":
            "subtree_flatten_result_count" in fields,
        "rebuild_context_diverged": bool(
            fields & {"rebuild_active", "rebuild_generation"}
        ),
        "left": {field: left.get(field) for field in TOKEN_FIELDS},
        "right": {field: right.get(field) for field in TOKEN_FIELDS},
    }
