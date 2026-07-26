import csv
import hashlib
import struct

import pytest

from fastlio2_adapter.day8_range_query import (
    load_query_summaries,
    validate_two_record_binary,
)


def _query_row():
    return {
        "schema_version": "Day8RangeQuerySummaryV1",
        "run_id": "r1", "query_sequence": 1, "scan_index": 155,
        "map_mutation_call_index": 1, "batch_id": 1,
        "batch_point_index": 0, "candidate_point_sha256": "a" * 64,
        "voxel_identity": "0" * 48,
        "query_box_min_x": 0, "query_box_min_y": 0,
        "query_box_min_z": 0, "query_box_max_x": 1,
        "query_box_max_y": 1, "query_box_max_z": 1,
        "query_box_checksum": 9,
        "query_box_matches_formal_voxel_contract": 1,
        "rebuild_active": 0, "rebuild_generation": 0,
        "logical_mutation_epoch": 0, "formal_result_count": 1,
        "formal_result_ordered_checksum": 2,
        "formal_result_multiset_checksum": 3,
        "formal_result_point_sha256_list": "b" * 64,
        "visited_node_count": 1,
        "returned_current_node_point_count": 1,
        "no_intersection_prune_count": 0,
        "full_cover_subtree_count": 0,
        "partial_intersection_node_count": 1,
        "point_deleted_skip_count": 0, "tree_deleted_skip_count": 0,
        "left_child_visit_count": 0, "right_child_visit_count": 0,
        "rebuild_subtree_observed_count": 0,
        "traversal_ordered_checksum": 4,
        "traversal_multiset_checksum": 5, "query_summary_checksum": 6,
        "schema_pass": 1, "internal_error": 0,
    }


def test_query_schema_accepts_bounded_formal_members(tmp_path):
    path = tmp_path / "queries.csv"
    row = _query_row()
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    loaded = load_query_summaries(path)
    assert loaded[0]["formal_result_members"] == ("b" * 64,)


def test_query_schema_rejects_window_and_formal_contract(tmp_path):
    path = tmp_path / "queries.csv"
    row = _query_row()
    row["scan_index"] = 166
    row["query_box_matches_formal_voxel_contract"] = 0
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
    with pytest.raises(ValueError):
        load_query_summaries(path)


def test_two_record_binary_checks_trailer_and_fnv(tmp_path):
    path = tmp_path / "trace.bin"
    metadata = b"ABCD"
    members = b"xy"
    body = metadata + members
    checksum = 14695981039346656037
    for byte in body:
        checksum ^= byte
        checksum = (checksum * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    payload = (
        b"D8RQUERYV1" + bytes(6)
        + struct.pack("<QQQQQ", 1, 4, 1, 1, 2)
        + body + b"D8RQENDV1" + bytes(7) + struct.pack("<Q", checksum)
    )
    path.write_bytes(payload)
    path.with_name(path.name + ".sha256").write_text(
        f"{hashlib.sha256(payload).hexdigest()}  {path.name}\n",
        encoding="utf-8",
    )
    result = validate_two_record_binary(
        path, b"D8RQUERYV1", b"D8RQENDV1"
    )
    assert result["metadata_count"] == 1
    assert result["member_count"] == 2
