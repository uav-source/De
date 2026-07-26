"""Canonical point identities and map-point snapshot helpers for Day 7."""

from __future__ import annotations

import csv
import hashlib
import re
import struct
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping


POINT_IDENTITY_ALGORITHM = "SHA256_CANONICAL_POINT_BYTES_V1"
POINT_FIELDS = (
    "x",
    "y",
    "z",
    "intensity",
    "normal_x",
    "normal_y",
    "normal_z",
    "curvature",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAP_BINARY_MAGIC = b"D7MAPID1"
MAP_BINARY_TRAILER = b"D7MAPEND"
MAP_METADATA = struct.Struct("<QBB6xQQQQQ")
FNV_OFFSET = 14695981039346656037
FNV_PRIME = 1099511628211


def point_identity(values: Mapping[str, float]) -> str:
    """Hash eight IEEE-754 float fields in fixed big-endian field order."""

    payload = struct.pack(
        ">8f", *(float(values[field]) for field in POINT_FIELDS)
    )
    return hashlib.sha256(payload).hexdigest()


def validate_identity(value: str) -> str:
    if not SHA256_RE.fullmatch(value):
        raise ValueError("invalid MapPointIdentityV1 SHA-256")
    return value


def load_snapshot_sets(
    path: Path,
) -> dict[tuple[int, str], tuple[str, ...]]:
    grouped: dict[tuple[int, str], list[str]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {
            "record_index",
            "scan_index",
            "snapshot_stage",
            "point_sha256",
        }
        if reader.fieldnames is None or not required.issubset(
            reader.fieldnames
        ):
            raise ValueError("map identity hash CSV schema mismatch")
        for row in reader:
            grouped[
                (int(row["scan_index"]), row["snapshot_stage"])
            ].append(validate_identity(row["point_sha256"]))
    result: dict[tuple[int, str], tuple[str, ...]] = {}
    for key, identities in grouped.items():
        if identities != sorted(identities):
            raise ValueError("map point identities are not canonical-sorted")
        result[key] = tuple(identities)
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fnv_identity_list(values: Iterable[bytes]) -> int:
    checksum = FNV_OFFSET
    for value in values:
        for byte in value:
            checksum ^= byte
            checksum = (checksum * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return checksum


def validate_snapshot_binary(
    binary_path: Path,
    index_path: Path,
    hashes_path: Path,
) -> dict[str, object]:
    sidecar = binary_path.with_name(binary_path.name + ".sha256")
    sidecar_fields = sidecar.read_text(encoding="utf-8").strip().split()
    actual_sha = _sha256_file(binary_path)
    if (
        len(sidecar_fields) != 2
        or sidecar_fields[0] != actual_sha
        or sidecar_fields[1] != binary_path.name
    ):
        raise ValueError("map identity binary SHA sidecar mismatch")
    payload = binary_path.read_bytes()
    if len(payload) < 36 or payload[:8] != MAP_BINARY_MAGIC:
        raise ValueError("map identity binary header mismatch")
    version, record_count = struct.unpack_from("<IQ", payload, 8)
    if version != 1:
        raise ValueError("map identity binary version mismatch")
    offset = 20
    records: list[dict[str, object]] = []
    for record_index in range(record_count):
        if offset + MAP_METADATA.size > len(payload):
            raise ValueError("truncated map identity metadata")
        fields = MAP_METADATA.unpack_from(payload, offset)
        offset += MAP_METADATA.size
        (
            scan_index,
            snapshot_stage,
            coherence_pass,
            rebuild_generation,
            logical_mutation_epoch,
            identity_offset,
            identity_count,
            record_checksum,
        ) = fields
        byte_count = identity_count * 32
        if offset + byte_count > len(payload):
            raise ValueError("truncated map identity record")
        identities = [
            payload[position:position + 32]
            for position in range(offset, offset + byte_count, 32)
        ]
        offset += byte_count
        if identities != sorted(identities):
            raise ValueError("map identity binary record is not sorted")
        if identity_offset != 0:
            raise ValueError("map identity binary offset must be record-local")
        if _fnv_identity_list(identities) != record_checksum:
            raise ValueError("map identity record checksum mismatch")
        records.append({
            "record_index": record_index,
            "scan_index": scan_index,
            "snapshot_stage":
                "MAP_BEFORE" if snapshot_stage == 1 else "MAP_AFTER",
            "coherence_pass": coherence_pass,
            "rebuild_generation": rebuild_generation,
            "logical_mutation_epoch": logical_mutation_epoch,
            "identity_count": identity_count,
            "record_checksum": record_checksum,
            "identities": tuple(value.hex() for value in identities),
        })
    if payload[offset:offset + 8] != MAP_BINARY_TRAILER:
        raise ValueError("map identity binary trailer mismatch")
    trailer_count = struct.unpack_from("<Q", payload, offset + 8)[0]
    if trailer_count != record_count or offset + 16 != len(payload):
        raise ValueError("map identity binary trailer count mismatch")

    with index_path.open(newline="", encoding="utf-8") as stream:
        index_rows = list(csv.DictReader(stream))
    if len(index_rows) != record_count:
        raise ValueError("map identity index count mismatch")
    hash_sets = load_snapshot_sets(hashes_path)
    for record, row in zip(records, index_rows):
        key = (int(record["scan_index"]), str(record["snapshot_stage"]))
        if (
            int(row["record_index"]) != int(record["record_index"])
            or int(row["scan_index"]) != int(record["scan_index"])
            or row["snapshot_stage"] != record["snapshot_stage"]
            or int(row["coherence_pass"]) != 1
            or int(row["identity_count"]) != int(record["identity_count"])
            or int(row["record_checksum"]) != int(
                record["record_checksum"]
            )
            or hash_sets.get(key) != record["identities"]
        ):
            raise ValueError("map identity binary/index/hash mismatch")
    return {
        "record_count": record_count,
        "file_sha256": actual_sha,
        "checksum_failure_count": 0,
        "coherence_failure_count": 0,
        "schema_pass": True,
    }


def symmetric_difference(
    left: Iterable[str], right: Iterable[str]
) -> tuple[list[str], list[str]]:
    left_set = set(left)
    right_set = set(right)
    return sorted(left_set - right_set), sorted(right_set - left_set)


def collision_boundary() -> str:
    return (
        "SHA-256 identities are treated as diagnostic identifiers; "
        "a theoretical hash collision remains possible."
    )
