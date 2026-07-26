"""Bounded readers and validators for Day 8 range-query diagnostics."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .day7_map_point_identity import SHA256_RE


QUERY_SCHEMA = "Day8RangeQuerySummaryV1"
TOKEN_SCHEMA = "Day8RangeTraversalTokenV1"
SNAPSHOT_SCHEMA = "MapPointVoxelIdentitySnapshotV2"
QUERY_MAGIC = b"D8RQUERYV1"
QUERY_TRAILER = b"D8RQENDV1"
TOKEN_MAGIC = b"D8RTOKENV1"
TOKEN_TRAILER = b"D8RTENDV1"
SNAPSHOT_MAGIC = b"D8PVOXELV2"
SNAPSHOT_TRAILER = b"D8PVENDV2"
VOXEL_RE = re.compile(r"^[0-9a-f]{48}$")
RELATIONS = {"NO_INTERSECTION", "FULL_COVER", "PARTIAL_INTERSECTION"}
SCAN_START = 155
SCAN_END = 165
DETAIL_START = 160
DETAIL_END = 163
MAX_QUERY_COUNT = 65536
MAX_TOKEN_COUNT = 1048576
MAX_MEMBER_COUNT = 262144


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_sidecar(path: Path) -> str:
    sidecar = path.with_name(path.name + ".sha256")
    fields = sidecar.read_text(encoding="utf-8").strip().split()
    actual = _sha256_file(path)
    if len(fields) != 2 or fields != [actual, path.name]:
        raise ValueError(f"invalid SHA-256 sidecar for {path.name}")
    return actual


def _tag(value: bytes) -> bytes:
    return value + bytes(16 - len(value))


def _fnv(payload: bytes) -> int:
    value = 14695981039346656037
    for byte in payload:
        value ^= byte
        value = (value * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return value


def validate_single_record_binary(
    path: Path, magic: bytes = TOKEN_MAGIC,
    trailer: bytes = TOKEN_TRAILER,
) -> dict[str, Any]:
    sha = _validate_sidecar(path)
    payload = path.read_bytes()
    if len(payload) < 64 or payload[:16] != _tag(magic):
        raise ValueError(f"binary magic mismatch: {path.name}")
    version, record_size, record_count = struct.unpack_from("<QQQ", payload, 16)
    body_start = 40
    body_end = body_start + record_size * record_count
    if (
        version != 1
        or record_size == 0
        or body_end + 24 != len(payload)
        or payload[body_end:body_end + 16] != _tag(trailer)
        or struct.unpack_from("<Q", payload, body_end + 16)[0]
        != _fnv(payload[body_start:body_end])
    ):
        raise ValueError(f"binary framing/checksum mismatch: {path.name}")
    return {
        "record_size": record_size,
        "record_count": record_count,
        "sha256": sha,
        "checksum_failure_count": 0,
    }


def validate_two_record_binary(
    path: Path, magic: bytes, trailer: bytes,
) -> dict[str, Any]:
    sha = _validate_sidecar(path)
    payload = path.read_bytes()
    if len(payload) < 80 or payload[:16] != _tag(magic):
        raise ValueError(f"binary magic mismatch: {path.name}")
    (
        version,
        metadata_size,
        metadata_count,
        member_size,
        member_count,
    ) = struct.unpack_from("<QQQQQ", payload, 16)
    body_start = 56
    body_end = (
        body_start
        + metadata_size * metadata_count
        + member_size * member_count
    )
    if (
        version != 1
        or metadata_size == 0
        or member_size == 0
        or body_end + 24 != len(payload)
        or payload[body_end:body_end + 16] != _tag(trailer)
        or struct.unpack_from("<Q", payload, body_end + 16)[0]
        != _fnv(payload[body_start:body_end])
    ):
        raise ValueError(f"binary framing/checksum mismatch: {path.name}")
    return {
        "metadata_size": metadata_size,
        "metadata_count": metadata_count,
        "member_size": member_size,
        "member_count": member_count,
        "sha256": sha,
        "checksum_failure_count": 0,
    }


def _integer(row: Mapping[str, str], name: str) -> int:
    try:
        return int(row[name])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"invalid integer field: {name}") from error


def _binary(row: Mapping[str, str], name: str) -> int:
    value = _integer(row, name)
    if value not in (0, 1):
        raise ValueError(f"non-binary field: {name}")
    return value


def _members(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    result = tuple(value.split(";"))
    if any(SHA256_RE.fullmatch(item) is None for item in result):
        raise ValueError("invalid formal result member identity")
    return result


def load_query_summaries(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
    required = {
        "schema_version", "run_id", "query_sequence", "scan_index",
        "map_mutation_call_index", "batch_id", "batch_point_index",
        "candidate_point_sha256", "voxel_identity",
        "query_box_min_x", "query_box_min_y", "query_box_min_z",
        "query_box_max_x", "query_box_max_y", "query_box_max_z",
        "query_box_checksum", "query_box_matches_formal_voxel_contract",
        "formal_result_count", "formal_result_ordered_checksum",
        "formal_result_multiset_checksum",
        "formal_result_point_sha256_list", "visited_node_count",
        "no_intersection_prune_count", "full_cover_subtree_count",
        "partial_intersection_node_count", "traversal_ordered_checksum",
        "traversal_multiset_checksum", "query_summary_checksum",
        "schema_pass", "internal_error",
    }
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError("Day 8 query index schema mismatch")
    if not 0 < len(rows) <= MAX_QUERY_COUNT:
        raise ValueError("Day 8 query count outside bounded contract")
    result: list[dict[str, Any]] = []
    previous = 0
    run_id: str | None = None
    integer_fields = (
        "query_sequence", "scan_index", "map_mutation_call_index",
        "batch_point_index", "query_box_checksum", "rebuild_active",
        "rebuild_generation", "logical_mutation_epoch",
        "formal_result_count", "formal_result_ordered_checksum",
        "formal_result_multiset_checksum", "visited_node_count",
        "returned_current_node_point_count",
        "no_intersection_prune_count", "full_cover_subtree_count",
        "partial_intersection_node_count", "point_deleted_skip_count",
        "tree_deleted_skip_count", "left_child_visit_count",
        "right_child_visit_count", "rebuild_subtree_observed_count",
        "traversal_ordered_checksum", "traversal_multiset_checksum",
        "query_summary_checksum",
    )
    for raw in rows:
        row: dict[str, Any] = dict(raw)
        if row["schema_version"] != QUERY_SCHEMA or not row["run_id"]:
            raise ValueError("Day 8 query schema/run id mismatch")
        run_id = run_id or row["run_id"]
        if row["run_id"] != run_id:
            raise ValueError("mixed run ids in query index")
        for name in integer_fields:
            row[name] = _integer(raw, name)
        for name in (
            "query_box_matches_formal_voxel_contract",
            "schema_pass", "internal_error",
        ):
            row[name] = _binary(raw, name)
        for name in (
            "query_box_min_x", "query_box_min_y", "query_box_min_z",
            "query_box_max_x", "query_box_max_y", "query_box_max_z",
        ):
            row[name] = float(raw[name])
        if row["query_sequence"] != previous + 1:
            raise ValueError("query sequence is not contiguous")
        previous = row["query_sequence"]
        if not SCAN_START <= row["scan_index"] <= SCAN_END:
            raise ValueError("query outside Day 8 window")
        if SHA256_RE.fullmatch(row["candidate_point_sha256"]) is None:
            raise ValueError("invalid query candidate identity")
        if VOXEL_RE.fullmatch(row["voxel_identity"]) is None:
            raise ValueError("invalid query voxel identity")
        members = _members(row["formal_result_point_sha256_list"])
        if len(members) != row["formal_result_count"]:
            raise ValueError("formal result member count mismatch")
        if (
            row["query_box_matches_formal_voxel_contract"] != 1
            or row["schema_pass"] != 1
            or row["internal_error"] != 0
        ):
            raise ValueError("query record reports schema/internal failure")
        row["formal_result_members"] = members
        result.append(row)
    if sum(row["formal_result_count"] for row in result) > MAX_MEMBER_COUNT:
        raise ValueError("formal result member count exceeds bound")
    return result


def load_traversal_tokens(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
    required = {
        "schema_version", "run_id", "query_sequence", "token_index",
        "depth", "node_point_sha256", "node_range_checksum",
        "query_relation", "point_deleted", "tree_deleted",
        "current_point_inside_query", "current_point_returned",
        "left_child_considered", "left_child_visited",
        "right_child_considered", "right_child_visited",
        "subtree_flatten_result_count", "rebuild_active",
        "rebuild_generation", "token_checksum",
    }
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise ValueError("Day 8 traversal token index schema mismatch")
    if not 0 < len(rows) <= MAX_TOKEN_COUNT:
        raise ValueError("Day 8 traversal token count outside bound")
    result: list[dict[str, Any]] = []
    expected_by_query: dict[int, int] = defaultdict(int)
    for raw in rows:
        row: dict[str, Any] = dict(raw)
        if row["schema_version"] != TOKEN_SCHEMA:
            raise ValueError("traversal token schema mismatch")
        for name in (
            "query_sequence", "token_index", "depth",
            "node_range_checksum", "subtree_flatten_result_count",
            "rebuild_generation", "token_checksum",
        ):
            row[name] = _integer(raw, name)
        for name in (
            "point_deleted", "tree_deleted", "current_point_inside_query",
            "current_point_returned", "left_child_considered",
            "left_child_visited", "right_child_considered",
            "right_child_visited", "rebuild_active",
        ):
            row[name] = _binary(raw, name)
        if row["query_relation"] not in RELATIONS:
            raise ValueError("unclassified query relation")
        if SHA256_RE.fullmatch(row["node_point_sha256"]) is None:
            raise ValueError("invalid traversal point identity")
        if row["token_index"] != expected_by_query[row["query_sequence"]]:
            raise ValueError("non-contiguous per-query token order")
        expected_by_query[row["query_sequence"]] += 1
        result.append(row)
    return result


def load_voxel_snapshots(
    index_path: Path, pair_path: Path,
) -> dict[tuple[int, str], tuple[tuple[str, str], ...]]:
    with index_path.open(newline="", encoding="utf-8") as stream:
        metadata = list(csv.DictReader(stream))
    with pair_path.open(newline="", encoding="utf-8") as stream:
        pairs = list(csv.DictReader(stream))
    if len(metadata) != 22:
        raise ValueError("expected exactly 22 point+voxel snapshots")
    grouped: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for row in pairs:
        point, voxel = row["point_sha256"], row["voxel_identity"]
        if SHA256_RE.fullmatch(point) is None or VOXEL_RE.fullmatch(voxel) is None:
            raise ValueError("invalid point+voxel pair")
        grouped[int(row["record_index"])].append((point, voxel))
    result: dict[tuple[int, str], tuple[tuple[str, str], ...]] = {}
    for row in metadata:
        if row["schema_version"] != SNAPSHOT_SCHEMA:
            raise ValueError("point+voxel snapshot schema mismatch")
        index = int(row["record_index"])
        values = tuple(grouped[index])
        if values != tuple(sorted(values)):
            raise ValueError("point+voxel pairs are not canonical-sorted")
        if (
            int(row["coherence_pass"]) != 1
            or int(row["point_count"]) != len(values)
            or int(row["point_voxel_pair_count"]) != len(values)
        ):
            raise ValueError("point+voxel snapshot count/coherence mismatch")
        key = (int(row["scan_index"]), row["snapshot_stage"])
        if key in result or row["snapshot_stage"] not in {"MAP_BEFORE", "MAP_AFTER"}:
            raise ValueError("duplicate/invalid point+voxel snapshot")
        result[key] = values
    expected = {
        (scan, stage)
        for scan in range(SCAN_START, SCAN_END + 1)
        for stage in ("MAP_BEFORE", "MAP_AFTER")
    }
    if set(result) != expected:
        raise ValueError("point+voxel snapshot window incomplete")
    return result


def query_identity(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        int(row["scan_index"]),
        int(row["map_mutation_call_index"]),
        int(row["batch_point_index"]),
        str(row["candidate_point_sha256"]),
        str(row["voxel_identity"]),
        int(row["query_box_checksum"]),
    )


def validate_run_query_trace(run_dir: Path) -> dict[str, Any]:
    queries = load_query_summaries(
        run_dir / "day8_range_query_summary_index.csv"
    )
    tokens = load_traversal_tokens(
        run_dir / "day8_range_traversal_token_index.csv"
    )
    snapshots = load_voxel_snapshots(
        run_dir / "map_point_voxel_identity_snapshot_index.csv",
        run_dir / "map_point_voxel_identity_snapshot_pairs.csv",
    )
    query_binary = validate_two_record_binary(
        run_dir / "day8_range_query_summaries_v1.bin",
        QUERY_MAGIC, QUERY_TRAILER,
    )
    token_binary = validate_single_record_binary(
        run_dir / "day8_range_traversal_tokens_v1.bin"
    )
    snapshot_binary = validate_two_record_binary(
        run_dir / "map_point_voxel_identity_snapshots_v2.bin",
        SNAPSHOT_MAGIC, SNAPSHOT_TRAILER,
    )
    overflow = json.loads(
        (run_dir / "day8_query_overflow_summary.json").read_text(
            encoding="utf-8"
        )
    )
    trace = json.loads(
        (run_dir / "day8_query_trace_summary.json").read_text(
            encoding="utf-8"
        )
    )
    failures = {
        key: int(overflow.get(key, -1))
        for key in (
            "query_summary_overflow", "traversal_token_overflow",
            "formal_result_member_overflow", "point_voxel_pair_overflow",
            "schema_error_count",
        )
    }
    token_queries = {row["query_sequence"] for row in tokens}
    detailed_sequences = {
        row["query_sequence"] for row in queries
        if DETAIL_START <= row["scan_index"] <= DETAIL_END
    }
    if (
        query_binary["metadata_count"] != len(queries)
        or query_binary["member_count"]
        != sum(row["formal_result_count"] for row in queries)
        or token_binary["record_count"] != len(tokens)
        or snapshot_binary["metadata_count"] != len(snapshots)
        or snapshot_binary["member_count"]
        != sum(len(value) for value in snapshots.values())
        or any(failures.values())
        or not tokens
        or not detailed_sequences.issubset(token_queries)
        or int(trace.get("query_summary_count", -1)) != len(queries)
        or int(trace.get("traversal_token_count", -1)) != len(tokens)
    ):
        raise ValueError("Day 8 query trace completeness gate failed")
    return {
        "schema_version": "day8_query_trace_validation_v1",
        "run_id": queries[0]["run_id"],
        "query_summary_count": len(queries),
        "traversal_token_count": len(tokens),
        "formal_result_member_count": query_binary["member_count"],
        "point_voxel_snapshot_count": len(snapshots),
        "query_binary_sha256": query_binary["sha256"],
        "token_binary_sha256": token_binary["sha256"],
        "snapshot_binary_sha256": snapshot_binary["sha256"],
        "unclassified_query_token_count": 0,
        "query_schema_error_count": 0,
        "overflow": failures,
        "instrumentation_timing_perturbation_present": True,
        "day8_query_trace_validation_pass": True,
    }


def canonical_member_checksum(values: Iterable[str]) -> str:
    return hashlib.sha256(
        json.dumps(sorted(values), separators=(",", ":")).encode("utf-8")
    ).hexdigest()
