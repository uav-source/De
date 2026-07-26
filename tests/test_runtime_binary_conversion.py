import importlib.util
import json
import struct
import sys
from pathlib import Path

import pytest

from test_runtime_observation_v3 import v3_record


ROOT = Path(__file__).resolve().parents[1]


def load_converter():
    spec = importlib.util.spec_from_file_location(
        "day5_runtime_binary_converter",
        ROOT / "scripts/46_convert_fastlio2_runtime_binary.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def u8(value):
    return struct.pack("<B", value)


def u32(value):
    return struct.pack("<I", value)


def u64(value):
    return struct.pack("<Q", value)


def f64(value):
    return struct.pack("<d", value)


def text(value):
    encoded = value.encode()
    return u32(len(encoded)) + encoded


def f64_vector(values):
    return u32(len(values)) + b"".join(f64(value) for value in values)


def runtime_payload():
    parts = [
        text("unit"),
        text("avia_quick_shack"),
        u64(1),
        f64(1.0),
        f64(1.1),
        u8(1),
        u8(1),
        u32(0),
        u32(2),
        u32(2),
        u32(100),
        u32(6),
        b"".join(f64(value) for value in (1, 2, 3)),
        b"".join(f64(value) for value in (0, 0, 0, 1)),
        b"".join(f64(value) for value in (1, 2, 3)),
        b"".join(f64(value) for value in (0, 0, 0, 1)),
        f64_vector([1.0, 2.0]),
        f64_vector([1.0, 0.0, 0.0, 1.0]),
        u64(10),
        u64(11),
        u64(100),
        u64(20),
        f64(0.9),
        f64(1.09),
        f64(1.0),
        f64(1.1),
        b"".join(u64(value) for value in range(1, 21)),
        u64(21),
        u64(22),
        u64(10),
        u64(10),
        u8(1),
        u8(1),
        u64(0),
        u8(0),
        u64(23),
        u64(23),
        u8(0),
        u64(1_000_000),
        u64(1000),
        u64(2000),
        u64(3000),
    ]
    return b"".join(parts)


def observation_payload():
    record = v3_record()
    parts = [
        text(record["run_id"]),
        text(record["sequence_id"]),
        text(record["fastlio2_commit"]),
        text(record["fastlio2_binary_sha256"]),
        text(record["bag_sha256"]),
        text(record["config_bundle_sha256"]),
        u64(record["scan_index"]),
        f64(record["timestamp_begin"]),
        f64(record["timestamp_end"]),
        u32(record["measurement_call_index"]),
        b"".join(f64(value) for value in record["prior_position_world"]),
        b"".join(
            f64(value)
            for value in record["prior_orientation_world_from_imu_xyzw"]
        ),
        b"".join(
            f64(value)
            for row in record["prior_covariance_detector_order_raw"]
            for value in row
        ),
        u32(len(record["detector_pose_jacobian_rows"])),
        b"".join(
            f64(value)
            for row in record["detector_pose_jacobian_rows"]
            for value in row
        ),
        f64_vector(record["formal_filter_innovation_h"]),
        f64(record["measurement_variance_scalar_m2"]),
        u8(1),
        u32(record["valid_correspondence_count"]),
        u32(12),
        u32(6),
        u64(record["formal_native_jacobian_checksum"]),
        u64(record["detector_jacobian_checksum"]),
        u64(record["formal_innovation_checksum"]),
        u64(record["geometric_residual_checksum"]),
        u64(record["accepted_index_checksum"]),
        u64(record["formal_correspondence_checksum"]),
        u64(record["prior_covariance_raw_checksum"]),
    ]
    return b"".join(parts)


def framed(magic, version, payload):
    converter = load_converter()
    header = magic + struct.pack("<HBBI", version, 1, 0, 16)
    frame = u32(len(payload)) + payload + u64(converter.fnv1a64(payload))
    prefix = header + frame
    return prefix + b"HBRENDV1" + u64(1) + u64(converter.fnv1a64(prefix))


def test_binary_converter_round_trip(tmp_path):
    converter = load_converter()
    runtime = tmp_path / "runtime.bin"
    observation = tmp_path / "observation.bin"
    runtime.write_bytes(framed(b"HBRTAUD2", 2, runtime_payload()))
    observation.write_bytes(framed(b"HBROBSV3", 3, observation_payload()))
    summary = converter.convert_files(runtime, tmp_path / "converted", observation)
    assert summary["binary_file_integrity_pass"] is True
    assert summary["runtime_record_count"] == 1
    assert summary["observation_record_count"] == 1
    records = [
        json.loads(line)
        for line in (tmp_path / "converted/observation_records_v3.jsonl")
        .read_text()
        .splitlines()
    ]
    assert records[0]["schema_version"] == "readonly_observation_v3"
    assert records[0]["prior_covariance_max_asymmetry"] > 1e-12


@pytest.mark.parametrize("mutation", ["truncate", "record_checksum", "trailer"])
def test_binary_converter_rejects_corruption_before_output(tmp_path, mutation):
    converter = load_converter()
    data = bytearray(framed(b"HBRTAUD2", 2, runtime_payload()))
    if mutation == "truncate":
        del data[-5:]
    elif mutation == "record_checksum":
        data[24] ^= 1
    else:
        data[-1] ^= 1
    path = tmp_path / "bad.bin"
    path.write_bytes(data)
    with pytest.raises(converter.BinaryFormatError):
        converter.convert_files(path, tmp_path / "must_not_exist")
    assert not (tmp_path / "must_not_exist").exists()
