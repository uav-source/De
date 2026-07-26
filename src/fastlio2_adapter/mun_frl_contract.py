"""Frozen MUN-FRL Lighthouse input contract.

This module is intentionally independent of ROS so the byte layout, timestamp,
unit, and extrinsic rules can be tested in the locked Python environment.
"""

from __future__ import annotations

import math
import struct
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np


LIDAR_TOPIC = "/velodyne_points"
LIDAR_MESSAGE_TYPE = "sensor_msgs/PointCloud2"
LIDAR_FRAME = "velodyne"
LIDAR_RATE_HZ = 10.0
IMU_TOPIC = "/imu/data"
IMU_MESSAGE_TYPE = "sensor_msgs/Imu"
IMU_FRAME = "imu_link"
IMU_RATE_HZ = 400.0
REFERENCE_TOPIC = "/fix"
REFERENCE_MESSAGE_TYPE = "sensor_msgs/NavSatFix"

# sensor_msgs/PointField constants are duplicated to avoid importing ROS.
UINT16 = 4
FLOAT32 = 7
EXPECTED_POINT_FIELDS = (
    ("x", 0, FLOAT32, 1),
    ("y", 4, FLOAT32, 1),
    ("z", 8, FLOAT32, 1),
    ("intensity", 12, FLOAT32, 1),
    ("ring", 16, UINT16, 1),
    ("time", 18, FLOAT32, 1),
)
POINT_STEP = 22
RING_MIN = 0
RING_MAX = 15
POINT_TIME_UNIT = "scan-relative seconds"

T_IMU_LIDAR = np.asarray([-0.0593, 0.0468, -0.1249], dtype=np.float64)
R_IMU_LIDAR = np.asarray(
    [
        [0.0018, 0.0019, 1.0],
        [0.0011, -1.0, 0.0019],
        [1.0, 0.0011, -0.0018],
    ],
    dtype=np.float64,
)
TIME_SYNC_EN = False
TIME_OFFSET_LIDAR_TO_IMU = 0.0034


def _value(item: Any, name: str) -> Any:
    if isinstance(item, Mapping):
        return item[name]
    return getattr(item, name)


def validate_point_layout(
    fields: Sequence[Any], *, point_step: int, is_bigendian: bool
) -> None:
    """Reject any deviation from the released 22-byte Lighthouse layout."""

    if bool(is_bigendian):
        raise ValueError("MUN-FRL point records must be little-endian")
    if int(point_step) != POINT_STEP:
        raise ValueError(f"point_step must be {POINT_STEP}, got {point_step}")
    actual = {
        str(_value(field, "name")): (
            int(_value(field, "offset")),
            int(_value(field, "datatype")),
            int(_value(field, "count")),
        )
        for field in fields
    }
    expected = {
        name: (offset, datatype, count)
        for name, offset, datatype, count in EXPECTED_POINT_FIELDS
    }
    if actual != expected:
        raise ValueError(f"point field layout mismatch: {actual!r}")


def decode_point_record(record: bytes) -> tuple[float, float, float, float, int, float]:
    """Decode one packed point; the final float remains in relative seconds."""

    if len(record) != POINT_STEP:
        raise ValueError(f"point record must contain {POINT_STEP} bytes")
    x, y, z, intensity = struct.unpack_from("<ffff", record, 0)
    ring = struct.unpack_from("<H", record, 16)[0]
    point_time_seconds = struct.unpack_from("<f", record, 18)[0]
    return x, y, z, intensity, ring, point_time_seconds


def point_time_seconds(value: Any) -> float:
    """Return ``point.time`` directly; no millisecond/nanosecond multiplier."""

    seconds = float(value)
    if not math.isfinite(seconds) or seconds < 0.0:
        raise ValueError("point time must be a finite nonnegative relative second")
    return seconds


def validate_point_times(values: Iterable[Any], *, scan_rate_hz: float = 10.0) -> dict[str, float]:
    times = np.asarray([point_time_seconds(value) for value in values], dtype=np.float64)
    if times.size == 0:
        raise ValueError("point cloud contains no point-time samples")
    scan_period = 1.0 / float(scan_rate_hz)
    # Packet timing and float rounding can extend slightly past the nominal scan.
    if float(np.max(times)) > scan_period * 1.25:
        raise ValueError("point times are incompatible with scan-relative seconds")
    return {
        "minimum_seconds": float(np.min(times)),
        "maximum_seconds": float(np.max(times)),
        "span_seconds": float(np.ptp(times)),
    }


def validate_ring_values(values: Iterable[Any]) -> dict[str, int]:
    rings = np.asarray([int(value) for value in values], dtype=np.int64)
    if rings.size == 0:
        raise ValueError("point cloud contains no ring samples")
    minimum = int(np.min(rings))
    maximum = int(np.max(rings))
    if minimum < RING_MIN or maximum > RING_MAX:
        raise ValueError(f"ring values must remain in {RING_MIN}--{RING_MAX}")
    return {"minimum": minimum, "maximum": maximum}


def convert_imu_units(
    angular_velocity: Sequence[Any], linear_acceleration: Sequence[Any]
) -> tuple[np.ndarray, np.ndarray]:
    """Apply the frozen identity conversions (rad/s and m/s^2)."""

    angular = np.asarray(angular_velocity, dtype=np.float64) * 1.0
    acceleration = np.asarray(linear_acceleration, dtype=np.float64) * 1.0
    if angular.shape != (3,) or acceleration.shape != (3,):
        raise ValueError("IMU vectors must each have three components")
    if not np.all(np.isfinite(angular)) or not np.all(np.isfinite(acceleration)):
        raise ValueError("IMU values must be finite")
    return angular, acceleration


def stamp_to_seconds(stamp: Any) -> float:
    if hasattr(stamp, "to_sec"):
        seconds = float(stamp.to_sec())
    elif isinstance(stamp, Mapping):
        seconds = float(stamp["secs"]) + float(stamp.get("nsecs", 0)) * 1.0e-9
    elif hasattr(stamp, "secs"):
        seconds = float(stamp.secs) + float(getattr(stamp, "nsecs", 0)) * 1.0e-9
    else:
        seconds = float(stamp)
    if not math.isfinite(seconds):
        raise ValueError("message header timestamp must be finite")
    return seconds


def message_header_time_seconds(message: Any, *, bag_record_time: Any | None = None) -> float:
    """Select the message header clock and deliberately ignore bag record time."""

    del bag_record_time
    header = _value(message, "header")
    return stamp_to_seconds(_value(header, "stamp"))


def transform_lidar_points_to_imu(points_lidar: Any) -> np.ndarray:
    """Apply p_imu = R_imu_lidar p_lidar + t_imu_lidar (never its inverse)."""

    points = np.asarray(points_lidar, dtype=np.float64)
    if points.shape[-1:] != (3,):
        raise ValueError("LiDAR points must have a final dimension of three")
    return points @ R_IMU_LIDAR.T + T_IMU_LIDAR


def validate_mun_frl_config(config: Mapping[str, Any]) -> None:
    """Validate the ROS parameter bundle consumed by FAST-LIO2."""

    common = config["common"]
    preprocess = config["preprocess"]
    mapping = config["mapping"]
    expected_scalars = (
        (common["lid_topic"], LIDAR_TOPIC, "common.lid_topic"),
        (common["imu_topic"], IMU_TOPIC, "common.imu_topic"),
        (bool(common["time_sync_en"]), TIME_SYNC_EN, "common.time_sync_en"),
        (
            float(common["time_offset_lidar_to_imu"]),
            TIME_OFFSET_LIDAR_TO_IMU,
            "common.time_offset_lidar_to_imu",
        ),
        (int(preprocess["lidar_type"]), 2, "preprocess.lidar_type"),
        (int(preprocess["scan_line"]), 16, "preprocess.scan_line"),
        (int(preprocess["scan_rate"]), 10, "preprocess.scan_rate"),
        (int(preprocess["timestamp_unit"]), 0, "preprocess.timestamp_unit"),
    )
    for actual, expected, name in expected_scalars:
        if actual != expected:
            raise ValueError(f"{name} must be {expected!r}, got {actual!r}")
    rotation = np.asarray(mapping["extrinsic_R"], dtype=np.float64).reshape(3, 3)
    translation = np.asarray(mapping["extrinsic_T"], dtype=np.float64)
    if not np.array_equal(rotation, R_IMU_LIDAR):
        raise ValueError("mapping.extrinsic_R must be the frozen imu<-lidar rotation")
    if not np.array_equal(translation, T_IMU_LIDAR):
        raise ValueError("mapping.extrinsic_T must be the frozen imu<-lidar translation")

