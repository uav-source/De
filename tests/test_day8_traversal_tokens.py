import csv

import pytest

from fastlio2_adapter.day8_range_query import load_traversal_tokens
from fastlio2_adapter.day8_traversal_analysis import (
    first_token_difference,
    missing_point_witness,
)


def _token(index=0, point="a" * 64):
    return {
        "schema_version": "Day8RangeTraversalTokenV1",
        "run_id": "r1", "query_sequence": 1, "token_index": index,
        "depth": index, "node_point_sha256": point,
        "node_range_checksum": 1, "query_relation": "PARTIAL_INTERSECTION",
        "point_deleted": 0, "tree_deleted": 0,
        "current_point_inside_query": 1, "current_point_returned": 1,
        "left_child_considered": 1, "left_child_visited": 1,
        "right_child_considered": 1, "right_child_visited": 0,
        "subtree_flatten_result_count": 0, "rebuild_active": 0,
        "rebuild_generation": 0, "token_checksum": index + 1,
    }


def test_token_order_and_relation_schema(tmp_path):
    path = tmp_path / "tokens.csv"
    rows = [_token(0), _token(1, "b" * 64)]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    assert [row["token_index"] for row in load_traversal_tokens(path)] == [0, 1]
    rows[1]["token_index"] = 2
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError):
        load_traversal_tokens(path)


def test_deleted_missing_point_witness_and_first_diff():
    left = [_token()]
    right = [_token()]
    right[0]["point_deleted"] = 1
    right[0]["current_point_returned"] = 0
    witness = missing_point_witness("a" * 64, right)
    assert witness["visited"] and witness["point_deleted_when_visited"]
    diff = first_token_difference(left, right)
    assert "point_deleted" in diff["differing_fields"]
