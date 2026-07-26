from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from fastlio2_adapter.replay_endpoint_contract import (
    EndpointContractError,
    EXPECTED_CLIPS,
    build_contract,
    build_sequence_contract,
    canonical_json_bytes,
    validate_contract,
)


class Stamp:
    def __init__(self, value: int) -> None:
        self.value = value

    def to_nsec(self) -> int:
        return self.value


class Message:
    def __init__(self, stamp: int, payload: bytes) -> None:
        self.header = type("Header", (), {"stamp": Stamp(stamp)})()
        self.payload = payload

    def serialize(self, stream: object) -> None:
        stream.write(self.payload)  # type: ignore[attr-defined]


class FakeBag:
    rows: dict[str, list[tuple[str, Message, Stamp]]] = {}

    def __init__(self, _path: str, _mode: str) -> None:
        pass

    def __enter__(self) -> "FakeBag":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read_messages(self, topics: list[str]):
        yield from self.rows[topics[0]]


def _fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for index, (sequence, definition) in enumerate(sorted(EXPECTED_CLIPS.items())):
        path = tmp_path / definition["clip_alias"]
        payload = f"clip-{index}".encode()
        path.write_bytes(payload)
        monkeypatch.setitem(
            definition, "clip_sha256", hashlib.sha256(payload).hexdigest()
        )
        monkeypatch.setitem(definition, "expected_lidar_message_count", 2)
        monkeypatch.setitem(definition, "expected_imu_message_count", 3)
        paths[sequence] = path
    FakeBag.rows = {
        "/livox/lidar": [
            ("/livox/lidar", Message(10, b"lidar-a"), Stamp(11)),
            ("/livox/lidar", Message(20, b"lidar-b"), Stamp(21)),
        ],
        "/livox/imu": [
            ("/livox/imu", Message(1, b"imu-a"), Stamp(2)),
            ("/livox/imu", Message(3, b"imu-b"), Stamp(4)),
            ("/livox/imu", Message(5, b"imu-c"), Stamp(6)),
        ],
    }
    return paths


def test_contract_is_byte_deterministic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    paths = _fixture(monkeypatch, tmp_path)
    first = build_contract(paths, bag_factory=FakeBag)
    second = build_contract(paths, bag_factory=FakeBag)
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    validate_contract(first)
    assert first["sequences"][0]["last_lidar_header_stamp_ns"] == 20
    assert first["sequences"][0]["last_imu_message_sha256"] == hashlib.sha256(b"imu-c").hexdigest()


def test_clip_sha_mismatch_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    paths = _fixture(monkeypatch, tmp_path)
    definition = EXPECTED_CLIPS["avia_quick_shack"]
    monkeypatch.setitem(definition, "clip_sha256", "0" * 64)
    with pytest.raises(EndpointContractError, match="SHA mismatch"):
        build_sequence_contract("avia_quick_shack", paths["avia_quick_shack"], bag_factory=FakeBag)


def test_topic_count_mismatch_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    paths = _fixture(monkeypatch, tmp_path)
    EXPECTED_CLIPS["avia_quick_shack"]["expected_lidar_message_count"] = 3
    with pytest.raises(EndpointContractError, match="LiDAR count mismatch"):
        build_sequence_contract("avia_quick_shack", paths["avia_quick_shack"], bag_factory=FakeBag)


def test_contract_checksum_rejects_change(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    contract = build_contract(_fixture(monkeypatch, tmp_path), bag_factory=FakeBag)
    changed = json.loads(json.dumps(contract))
    changed["sequences"][0]["last_imu_header_stamp_ns"] += 1
    with pytest.raises(EndpointContractError, match="checksum"):
        validate_contract(changed)
