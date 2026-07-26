#!/usr/bin/env python3
"""Validate and convert Day 5 remediation compact runtime binaries."""

from __future__ import annotations

import argparse
import csv
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RUNTIME_MAGIC = b"HBRTAUD2"
OBSERVATION_MAGIC = b"HBROBSV3"
TRAILER_MAGIC = b"HBRENDV1"
RUNTIME_VERSION = 2
OBSERVATION_VERSION = 3
ENDIAN_MARKER = 1
HEADER_SIZE = 16
TRAILER_SIZE = 24
FNV_OFFSET = 14695981039346656037
FNV_PRIME = 1099511628211
SKIP_REASONS = (
    "NONE",
    "FIRST_SCAN_INITIALIZATION",
    "EMPTY_UNDISTORTED_SCAN",
    "LOCAL_MAP_INITIALIZATION",
    "DOWNSAMPLED_POINTS_TOO_FEW",
    "FILTER_UPDATE_NOT_INVOKED",
    "NO_VALID_LINEARIZATION",
    "EXTRINSIC_ESTIMATION_ENABLED",
    "NONFINITE_OBSERVATION",
    "BUFFER_FULL",
    "INTERNAL_LIFECYCLE_ERROR",
)


class BinaryFormatError(ValueError):
    """A compact binary failed its fail-closed integrity contract."""


@dataclass(frozen=True)
class FramedRecord:
    payload: bytes
    checksum: int


def fnv1a64(data: bytes) -> int:
    value = FNV_OFFSET
    for byte in data:
        value ^= byte
        value = (value * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return value


def read_framed_binary(
    path: Path, *, magic: bytes, version: int
) -> tuple[list[FramedRecord], dict[str, Any]]:
    data = path.read_bytes()
    if len(data) < HEADER_SIZE + TRAILER_SIZE:
        raise BinaryFormatError("truncated binary file")
    if data[:8] != magic:
        raise BinaryFormatError("binary magic mismatch")
    actual_version, endianness, reserved, header_size = struct.unpack_from(
        "<HBBI", data, 8
    )
    if actual_version != version:
        raise BinaryFormatError("binary version mismatch")
    if endianness != ENDIAN_MARKER or reserved != 0 or header_size != HEADER_SIZE:
        raise BinaryFormatError("binary header contract mismatch")
    trailer_offset = len(data) - TRAILER_SIZE
    if data[trailer_offset : trailer_offset + 8] != TRAILER_MAGIC:
        raise BinaryFormatError("missing or truncated binary trailer")
    expected_count, expected_file_checksum = struct.unpack_from(
        "<QQ", data, trailer_offset + 8
    )
    actual_file_checksum = fnv1a64(data[:trailer_offset])
    if actual_file_checksum != expected_file_checksum:
        raise BinaryFormatError("binary file checksum mismatch")

    records: list[FramedRecord] = []
    offset = HEADER_SIZE
    while offset < trailer_offset:
        if offset + 4 > trailer_offset:
            raise BinaryFormatError("truncated record length")
        (payload_length,) = struct.unpack_from("<I", data, offset)
        offset += 4
        end = offset + payload_length
        if end + 8 > trailer_offset:
            raise BinaryFormatError("truncated record payload")
        payload = data[offset:end]
        offset = end
        (expected_record_checksum,) = struct.unpack_from("<Q", data, offset)
        offset += 8
        if fnv1a64(payload) != expected_record_checksum:
            raise BinaryFormatError("record checksum mismatch")
        records.append(FramedRecord(payload, expected_record_checksum))
    if offset != trailer_offset:
        raise BinaryFormatError("extra bytes before binary trailer")
    if len(records) != expected_count:
        raise BinaryFormatError("binary trailer record count mismatch")
    return records, {
        "path": str(path),
        "magic": magic.decode("ascii"),
        "version": version,
        "endianness": "little",
        "record_count": len(records),
        "record_checksum_failure_count": 0,
        "file_checksum": expected_file_checksum,
        "file_checksum_valid": True,
        "trailer_valid": True,
        "truncated_record_count": 0,
        "extra_byte_count": 0,
    }


class PayloadReader:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.offset = 0

    def _take(self, size: int) -> bytes:
        end = self.offset + size
        if end > len(self.payload):
            raise BinaryFormatError("record payload is truncated")
        value = self.payload[self.offset:end]
        self.offset = end
        return value

    def u8(self) -> int:
        return self._take(1)[0]

    def u32(self) -> int:
        return struct.unpack("<I", self._take(4))[0]

    def u64(self) -> int:
        return struct.unpack("<Q", self._take(8))[0]

    def f64(self) -> float:
        value = struct.unpack("<d", self._take(8))[0]
        if not math.isfinite(value):
            raise BinaryFormatError("nonfinite double in binary payload")
        return value

    def boolean(self) -> bool:
        value = self.u8()
        if value not in (0, 1):
            raise BinaryFormatError("invalid binary boolean")
        return bool(value)

    def text(self) -> str:
        size = self.u32()
        try:
            return self._take(size).decode("utf-8")
        except UnicodeDecodeError as error:
            raise BinaryFormatError("invalid UTF-8 string") from error

    def f64_vector(self) -> list[float]:
        return [self.f64() for _ in range(self.u32())]

    def finish(self) -> None:
        if self.offset != len(self.payload):
            raise BinaryFormatError("extra bytes in record payload")


def decode_runtime_record(record: FramedRecord) -> dict[str, Any]:
    reader = PayloadReader(record.payload)
    value: dict[str, Any] = {
        "run_id": reader.text(),
        "sequence_id": reader.text(),
        "scan_index": reader.u64(),
        "timestamp_begin": reader.f64(),
        "timestamp_end": reader.f64(),
        "update_invoked": reader.boolean(),
        "first_valid_linearization_found": reader.boolean(),
    }
    skip_reason = reader.u32()
    if skip_reason >= len(SKIP_REASONS):
        raise BinaryFormatError("invalid skip reason enum")
    value["skip_reason"] = SKIP_REASONS[skip_reason]
    for field in (
        "measurement_call_count",
        "valid_measurement_call_count",
        "downsampled_point_count",
        "valid_correspondence_count",
    ):
        value[field] = reader.u32()
    value["prior_position"] = [reader.f64() for _ in range(3)]
    value["prior_orientation_xyzw"] = [reader.f64() for _ in range(4)]
    value["posterior_position"] = [reader.f64() for _ in range(3)]
    value["posterior_orientation_xyzw"] = [reader.f64() for _ in range(4)]
    value["posterior_state_native"] = reader.f64_vector()
    value["posterior_covariance_native_flat"] = reader.f64_vector()
    value["map_size_after_update"] = reader.u64()
    value["measure_group_checksum"] = reader.u64()
    value["lidar_point_count"] = reader.u64()
    value["imu_message_count"] = reader.u64()
    for field in (
        "first_imu_timestamp",
        "last_imu_timestamp",
        "lidar_begin_time",
        "lidar_end_time",
    ):
        value[field] = reader.f64()
    checksum_fields = (
        "prior_state_checksum",
        "prior_covariance_checksum",
        "posterior_state_checksum",
        "posterior_covariance_checksum",
        "formal_native_jacobian_checksum",
        "detector_jacobian_checksum",
        "formal_innovation_checksum",
        "geometric_residual_checksum",
        "accepted_index_checksum",
        "formal_correspondence_checksum",
        "tap_pre_state_checksum",
        "tap_post_state_checksum",
        "tap_pre_covariance_checksum",
        "tap_post_covariance_checksum",
        "tap_pre_native_jacobian_checksum",
        "tap_post_native_jacobian_checksum",
        "tap_pre_innovation_checksum",
        "tap_post_innovation_checksum",
        "tap_pre_geometric_residual_checksum",
        "tap_post_geometric_residual_checksum",
        "tap_pre_correspondence_checksum",
        "tap_post_correspondence_checksum",
        "tap_pre_map_size",
        "tap_post_map_size",
    )
    for field in checksum_fields:
        value[field] = reader.u64()
    value["tap_enabled"] = reader.boolean()
    value["tap_record_emitted"] = reader.boolean()
    value["tap_drop_count"] = reader.u64()
    value["tap_call_mutation_detected"] = reader.boolean()
    value["export_pre_estimator_checksum"] = reader.u64()
    value["export_post_estimator_checksum"] = reader.u64()
    value["export_call_mutation_detected"] = reader.boolean()
    for field in (
        "scan_total_runtime_ns",
        "runtime_audit_ns",
        "tap_capture_ns",
        "binary_writer_ns",
    ):
        value[field] = reader.u64()
    value["checksum_algorithm"] = "FNV1A64_EXACT_BYTES_V1"
    reader.finish()
    return value


def decode_observation_record(record: FramedRecord) -> dict[str, Any]:
    reader = PayloadReader(record.payload)
    run_id = reader.text()
    sequence_id = reader.text()
    fastlio2_commit = reader.text()
    fastlio2_binary_sha256 = reader.text()
    bag_sha256 = reader.text()
    config_bundle_sha256 = reader.text()
    scan_index = reader.u64()
    timestamp_begin = reader.f64()
    timestamp_end = reader.f64()
    measurement_call_index = reader.u32()
    prior_position = [reader.f64() for _ in range(3)]
    prior_orientation = [reader.f64() for _ in range(4)]
    raw_flat = [reader.f64() for _ in range(36)]
    raw = [raw_flat[index : index + 6] for index in range(0, 36, 6)]
    jacobian_count = reader.u32()
    jacobian = [
        [reader.f64() for _ in range(6)] for _ in range(jacobian_count)
    ]
    innovation = reader.f64_vector()
    variance = reader.f64()
    variance_all_rows = reader.boolean()
    valid_correspondence_count = reader.u32()
    native_columns = reader.u32()
    detector_columns = reader.u32()
    checksums = {
        name: reader.u64()
        for name in (
            "formal_native_jacobian_checksum",
            "detector_jacobian_checksum",
            "formal_innovation_checksum",
            "geometric_residual_checksum",
            "accepted_index_checksum",
            "formal_correspondence_checksum",
            "prior_covariance_raw_checksum",
        )
    }
    reader.finish()
    symmetric = [
        [0.5 * (raw[row][column] + raw[column][row]) for column in range(6)]
        for row in range(6)
    ]
    max_asymmetry = max(
        abs(raw[row][column] - raw[column][row])
        for row in range(6)
        for column in range(6)
    )
    return {
        "schema_version": "readonly_observation_v3",
        "record_version": "readonly_observation_v3",
        "record_source": "FASTLIO2_RUNTIME_COMPACT_BINARY",
        "synthetic_only": False,
        "run_id": run_id,
        "sequence_id": sequence_id,
        "fastlio2_commit": fastlio2_commit,
        "fastlio2_binary_sha256": fastlio2_binary_sha256,
        "bag_sha256": bag_sha256,
        "config_bundle_sha256": config_bundle_sha256,
        "adapter_contract_version": "fastlio2-readonly-observation-v3",
        "scan_index": scan_index,
        "timestamp_begin": timestamp_begin,
        "timestamp_end": timestamp_end,
        "timestamp_unit": "seconds",
        "measurement_call_index": measurement_call_index,
        "prior_position_world": prior_position,
        "prior_orientation_world_from_imu_xyzw": prior_orientation,
        "prior_covariance_detector_order_raw": raw,
        "prior_covariance_detector_order_symmetric": symmetric,
        "prior_covariance_max_asymmetry": max_asymmetry,
        "prior_covariance_raw_checksum": checksums.pop(
            "prior_covariance_raw_checksum"
        ),
        "detector_pose_jacobian_rows": jacobian,
        "formal_filter_innovation_h": innovation,
        "signed_geometric_residual_pd2_derived": True,
        "measurement_variance_scalar_m2": variance,
        "measurement_weight_representation": "CONSTANT_SCALAR_VARIANCE",
        "measurement_variance_applies_to_all_rows": variance_all_rows,
        "valid_correspondence_count": valid_correspondence_count,
        "native_jacobian_column_count": native_columns,
        "detector_jacobian_column_count": detector_columns,
        "checksum_algorithm": "FNV1A64_EXACT_BYTES_V1",
        **checksums,
        "binary_record_checksum": record.checksum,
    }


def convert_files(
    runtime_path: Path,
    output_dir: Path,
    observation_path: Path | None = None,
) -> dict[str, Any]:
    runtime_records, runtime_integrity = read_framed_binary(
        runtime_path, magic=RUNTIME_MAGIC, version=RUNTIME_VERSION
    )
    runtime_rows = [decode_runtime_record(record) for record in runtime_records]
    observation_rows: list[dict[str, Any]] = []
    observation_integrity: dict[str, Any] | None = None
    if observation_path is not None:
        observations, observation_integrity = read_framed_binary(
            observation_path,
            magic=OBSERVATION_MAGIC,
            version=OBSERVATION_VERSION,
        )
        observation_rows = [
            decode_observation_record(record) for record in observations
        ]

    output_dir.mkdir(parents=True, exist_ok=False)
    runtime_csv = output_dir / "runtime_frames.csv"
    _write_runtime_csv(runtime_csv, runtime_rows)
    observation_jsonl = output_dir / "observation_records_v3.jsonl"
    if observation_path is not None:
        with observation_jsonl.open("w", encoding="utf-8") as handle:
            for row in observation_rows:
                handle.write(
                    json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
                )
    summary = {
        "runtime_audit": runtime_integrity,
        "observations": observation_integrity,
        "runtime_record_count": len(runtime_rows),
        "observation_record_count": len(observation_rows),
        "binary_converter_rejected_count": 0,
        "binary_checksum_failure_count": 0,
        "truncated_record_count": 0,
        "binary_file_integrity_pass": True,
        "input_bag_read": False,
        "ground_truth_read": False,
    }
    (output_dir / "binary_conversion_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def _write_runtime_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise BinaryFormatError("runtime audit binary contains no records")
    fieldnames = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            encoded = dict(row)
            for field in (
                "prior_position",
                "prior_orientation_xyzw",
                "posterior_position",
                "posterior_orientation_xyzw",
                "posterior_state_native",
                "posterior_covariance_native_flat",
            ):
                encoded[field] = ";".join(repr(value) for value in row[field])
            for field in (
                "update_invoked",
                "first_valid_linearization_found",
                "tap_enabled",
                "tap_record_emitted",
                "tap_call_mutation_detected",
                "export_call_mutation_detected",
            ):
                encoded[field] = "true" if row[field] else "false"
            writer.writerow(encoded)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert validated FAST-LIO2 remediation binaries"
    )
    parser.add_argument("--runtime-audit", required=True, type=Path)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = convert_files(
        args.runtime_audit, args.output_dir, args.observations
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
