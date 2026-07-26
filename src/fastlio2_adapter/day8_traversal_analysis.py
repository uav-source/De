"""Deterministic comparison helpers for bounded Day 8 traversal tokens."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Mapping, Sequence


TOKEN_FIELDS = (
    "token_index", "depth", "node_point_sha256", "node_range_checksum",
    "query_relation", "point_deleted", "tree_deleted",
    "current_point_inside_query", "current_point_returned",
    "left_child_considered", "left_child_visited",
    "right_child_considered", "right_child_visited",
    "subtree_flatten_result_count", "rebuild_active",
    "rebuild_generation", "token_checksum",
)


def group_tokens(
    rows: Sequence[Mapping[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["query_sequence"])].append(dict(row))
    for sequence, values in grouped.items():
        values.sort(key=lambda row: int(row["token_index"]))
        if [int(row["token_index"]) for row in values] != list(range(len(values))):
            raise ValueError(f"non-contiguous token order for query {sequence}")
    return dict(grouped)


def traversal_signature(rows: Sequence[Mapping[str, Any]]) -> str:
    canonical = [
        {field: row.get(field) for field in TOKEN_FIELDS}
        for row in rows
    ]
    return hashlib.sha256(
        json.dumps(
            canonical, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def first_token_difference(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
    *,
    left_capture_status: str | None = None,
    right_capture_status: str | None = None,
) -> dict[str, Any]:
    if left_capture_status is not None or right_capture_status is not None:
        from .day8_token_capture_status import compare_token_capture

        if left_capture_status is None or right_capture_status is None:
            raise ValueError("both token capture statuses are required")
        applicability = compare_token_capture(
            left_capture_status,
            right_capture_status,
            token_sequence_equal=None,
        )
        if applicability["token_comparison_status"] != "APPLICABLE":
            return {
                **applicability,
                "first_differing_token_index": None,
                "differing_fields": [],
                "left_token": None,
                "right_token": None,
            }
    limit = max(len(left), len(right))
    for index in range(limit):
        a = left[index] if index < len(left) else None
        b = right[index] if index < len(right) else None
        differing = (
            ["record_presence"]
            if a is None or b is None
            else [
                field for field in TOKEN_FIELDS
                if a.get(field) != b.get(field)
            ]
        )
        if differing:
            return {
                "first_differing_token_index": index,
                "differing_fields": differing,
                "left_token": dict(a) if a is not None else None,
                "right_token": dict(b) if b is not None else None,
                "token_sequence_equal": False,
                "token_comparison_status": "APPLICABLE",
            }
    return {
        "first_differing_token_index": None,
        "differing_fields": [],
        "left_token": None,
        "right_token": None,
        "token_sequence_equal": True,
        "token_comparison_status": "APPLICABLE",
    }


def missing_point_witness(
    missing_point: str,
    tokens: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    matches = [
        dict(row) for row in tokens
        if row.get("node_point_sha256") == missing_point
    ]
    return {
        "missing_point_sha256": missing_point,
        "visited": bool(matches),
        "visited_token_count": len(matches),
        "point_deleted_when_visited": any(
            int(row.get("point_deleted", 0)) == 1 for row in matches
        ),
        "tree_deleted_when_visited": any(
            int(row.get("tree_deleted", 0)) == 1 for row in matches
        ),
        "returned_when_visited": any(
            int(row.get("current_point_returned", 0)) == 1
            for row in matches
        ),
        "tokens": matches,
    }


def traversal_diff_rows(
    left_run_id: str,
    right_run_id: str,
    query_identity: str,
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(max(len(left), len(right))):
        a = left[index] if index < len(left) else {}
        b = right[index] if index < len(right) else {}
        fields = [
            field for field in TOKEN_FIELDS
            if a.get(field) != b.get(field)
        ]
        if fields:
            rows.append({
                "left_run_id": left_run_id,
                "right_run_id": right_run_id,
                "query_identity": query_identity,
                "token_index": index,
                "differing_fields": ";".join(fields),
                "left_token": json.dumps(
                    dict(a), sort_keys=True, separators=(",", ":")
                ),
                "right_token": json.dumps(
                    dict(b), sort_keys=True, separators=(",", ":")
                ),
            })
    return rows
