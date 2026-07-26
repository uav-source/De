"""Deterministic endpoint contracts for the frozen Day 5 replay clips."""

from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "fastlio2_replay_endpoint_contract_v1"
ENDPOINT_POLICY = "ALL_EXPECTED_CALLBACKS_RECEIVED_AND_NO_PROCESSABLE_MEASURE_GROUP_V1"
MEASURE_GROUP_COUNT_POLICY = "MUST_BE_IDENTICAL_ACROSS_REPEATS_AFTER_DRAIN"
CONTRACT_SOURCE = "FROZEN_CLIP_DIRECT_READ"
LIDAR_TOPIC = "/livox/lidar"
IMU_TOPIC = "/livox/imu"
EXPECTED_CLIPS: dict[str, dict[str, Any]] = {
    "avia_quick_shack": {
        "clip_alias": "avia_quick_shack.replay.bag",
        "clip_sha256": "272325265978787c838e010b1f0da963a15fb4b08ff8730fc3dd9901e32a0e20",
        "expected_lidar_message_count": 491,
        "expected_imu_message_count": 9953,
    },
    "avia_outdoor_run_100hz": {
        "clip_alias": "avia_outdoor_run_100hz.replay.bag",
        "clip_sha256": "087c552c9c62be37b42d218323383459df8791ce6514fa7b3425f7bab5021284",
        "expected_lidar_message_count": 6386,
        "expected_imu_message_count": 12914,
    },
}


class EndpointContractError(RuntimeError):
    """The frozen input does not satisfy the endpoint contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def message_serialized_bytes(message: Any) -> bytes:
    stream = io.BytesIO()
    message.serialize(stream)
    return stream.getvalue()


def header_stamp_ns(message: Any) -> int:
    stamp = message.header.stamp
    if hasattr(stamp, "to_nsec"):
        return int(stamp.to_nsec())
    return int(stamp.secs) * 1_000_000_000 + int(stamp.nsecs)


def bag_time_ns(value: Any) -> int:
    if hasattr(value, "to_nsec"):
        return int(value.to_nsec())
    return int(value.secs) * 1_000_000_000 + int(value.nsecs)


def _topic_endpoint(rows: Iterable[tuple[Any, Any]]) -> dict[str, Any]:
    count = 0
    first_header = last_header = first_bag = last_bag = None
    first_sha = last_sha = None
    for message, bag_stamp in rows:
        serialized_sha = hashlib.sha256(message_serialized_bytes(message)).hexdigest()
        message_header = header_stamp_ns(message)
        message_bag_time = bag_time_ns(bag_stamp)
        if count == 0:
            first_header = message_header
            first_bag = message_bag_time
            first_sha = serialized_sha
        count += 1
        last_header = message_header
        last_bag = message_bag_time
        last_sha = serialized_sha
    if count == 0:
        raise EndpointContractError("required replay topic is empty")
    return {
        "count": count,
        "first_header_stamp_ns": first_header,
        "last_header_stamp_ns": last_header,
        "first_bag_time_ns": first_bag,
        "last_bag_time_ns": last_bag,
        "first_message_sha256": first_sha,
        "last_message_sha256": last_sha,
    }


def build_sequence_contract(
    sequence_id: str,
    clip_path: Path,
    *,
    bag_factory: Any | None = None,
) -> dict[str, Any]:
    if sequence_id not in EXPECTED_CLIPS:
        raise EndpointContractError(f"unsupported sequence_id: {sequence_id}")
    definition = EXPECTED_CLIPS[sequence_id]
    clip_path = clip_path.expanduser().resolve()
    if not clip_path.is_file():
        raise EndpointContractError(f"clip missing: {clip_path}")
    actual_sha = sha256_file(clip_path)
    if actual_sha != definition["clip_sha256"]:
        raise EndpointContractError(
            f"{sequence_id} clip SHA mismatch: {actual_sha}"
        )
    if bag_factory is None:
        try:
            import rosbag  # type: ignore
        except ImportError as error:
            raise EndpointContractError("ROS rosbag Python module unavailable") from error
        bag_factory = rosbag.Bag
    with bag_factory(str(clip_path), "r") as bag:
        lidar = _topic_endpoint(
            (message, stamp)
            for _topic, message, stamp in bag.read_messages(topics=[LIDAR_TOPIC])
        )
        imu = _topic_endpoint(
            (message, stamp)
            for _topic, message, stamp in bag.read_messages(topics=[IMU_TOPIC])
        )
    if lidar["count"] != definition["expected_lidar_message_count"]:
        raise EndpointContractError(
            f"{sequence_id} LiDAR count mismatch: {lidar['count']}"
        )
    if imu["count"] != definition["expected_imu_message_count"]:
        raise EndpointContractError(
            f"{sequence_id} IMU count mismatch: {imu['count']}"
        )
    return {
        "sequence_id": sequence_id,
        "clip_alias": definition["clip_alias"],
        "clip_sha256": actual_sha,
        "lidar_topic": LIDAR_TOPIC,
        "imu_topic": IMU_TOPIC,
        "expected_lidar_message_count": lidar["count"],
        "expected_imu_message_count": imu["count"],
        "first_lidar_header_stamp_ns": lidar["first_header_stamp_ns"],
        "last_lidar_header_stamp_ns": lidar["last_header_stamp_ns"],
        "first_imu_header_stamp_ns": imu["first_header_stamp_ns"],
        "last_imu_header_stamp_ns": imu["last_header_stamp_ns"],
        "first_lidar_bag_time_ns": lidar["first_bag_time_ns"],
        "last_lidar_bag_time_ns": lidar["last_bag_time_ns"],
        "first_imu_bag_time_ns": imu["first_bag_time_ns"],
        "last_imu_bag_time_ns": imu["last_bag_time_ns"],
        "first_lidar_message_sha256": lidar["first_message_sha256"],
        "last_lidar_message_sha256": lidar["last_message_sha256"],
        "first_imu_message_sha256": imu["first_message_sha256"],
        "last_imu_message_sha256": imu["last_message_sha256"],
        "endpoint_policy": ENDPOINT_POLICY,
        "expected_measure_group_count": "NOT_PRECOMPUTED",
        "measure_group_count_policy": MEASURE_GROUP_COUNT_POLICY,
        "contract_source": CONTRACT_SOURCE,
    }


def build_contract(clip_paths: Mapping[str, Path], *, bag_factory: Any | None = None) -> dict[str, Any]:
    if set(clip_paths) != set(EXPECTED_CLIPS):
        raise EndpointContractError("both and only the fixed Day 5 sequences are required")
    sequences = [
        build_sequence_contract(sequence, clip_paths[sequence], bag_factory=bag_factory)
        for sequence in sorted(EXPECTED_CLIPS)
    ]
    content_time_ns = max(
        max(row["last_lidar_bag_time_ns"], row["last_imu_bag_time_ns"])
        for row in sequences
    )
    created_at = datetime.fromtimestamp(
        content_time_ns / 1_000_000_000, tz=timezone.utc
    ).isoformat(timespec="microseconds").replace("+00:00", "Z")
    contract: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": created_at,
        "contract_source": CONTRACT_SOURCE,
        "endpoint_policy": ENDPOINT_POLICY,
        "sequences": sequences,
    }
    contract["contract_checksum_sha256"] = hashlib.sha256(
        canonical_json_bytes(contract)
    ).hexdigest()
    return contract


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("schema_version") != SCHEMA_VERSION:
        raise EndpointContractError("endpoint contract schema mismatch")
    sequences = contract.get("sequences")
    if not isinstance(sequences, list) or len(sequences) != 2:
        raise EndpointContractError("endpoint contract must contain two sequences")
    by_id = {row.get("sequence_id"): row for row in sequences if isinstance(row, dict)}
    if set(by_id) != set(EXPECTED_CLIPS):
        raise EndpointContractError("endpoint contract sequence set mismatch")
    for sequence_id, expected in EXPECTED_CLIPS.items():
        row = by_id[sequence_id]
        for field in (
            "clip_sha256",
            "expected_lidar_message_count",
            "expected_imu_message_count",
        ):
            if row.get(field) != expected[field]:
                raise EndpointContractError(f"{sequence_id} {field} mismatch")
    without_checksum = dict(contract)
    declared = without_checksum.pop("contract_checksum_sha256", None)
    actual = hashlib.sha256(canonical_json_bytes(without_checksum)).hexdigest()
    if declared != actual:
        raise EndpointContractError("endpoint contract checksum mismatch")


def sequence_contract(contract: Mapping[str, Any], sequence_id: str) -> Mapping[str, Any]:
    validate_contract(contract)
    for row in contract["sequences"]:
        if row["sequence_id"] == sequence_id:
            return row
    raise EndpointContractError(f"sequence missing: {sequence_id}")
