"""ROS-message-facing validation helpers for MUN-FRL Lighthouse."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from .mun_frl_contract import (
    IMU_FRAME,
    LIDAR_FRAME,
    POINT_STEP,
    convert_imu_units,
    decode_point_record,
    message_header_time_seconds,
    validate_point_layout,
    validate_point_times,
    validate_ring_values,
)


def _xyz(vector: Any) -> tuple[float, float, float]:
    return float(vector.x), float(vector.y), float(vector.z)


def iter_packed_points(message: Any) -> Iterator[tuple[float, float, float, float, int, float]]:
    """Iterate the packed 22-byte records without changing time units."""

    data = bytes(message.data)
    if len(data) % int(message.point_step) != 0:
        raise ValueError("PointCloud2 data length is not divisible by point_step")
    for offset in range(0, len(data), POINT_STEP):
        yield decode_point_record(data[offset : offset + POINT_STEP])


def validate_pointcloud_message(message: Any, *, bag_record_time: Any | None = None) -> dict[str, Any]:
    validate_point_layout(
        message.fields,
        point_step=int(message.point_step),
        is_bigendian=bool(message.is_bigendian),
    )
    if str(message.header.frame_id) != LIDAR_FRAME:
        raise ValueError(f"LiDAR frame must be {LIDAR_FRAME}")
    decoded = list(iter_packed_points(message))
    rings = validate_ring_values(point[4] for point in decoded)
    times = validate_point_times(point[5] for point in decoded)
    return {
        "header_timestamp": message_header_time_seconds(
            message, bag_record_time=bag_record_time
        ),
        "point_count": len(decoded),
        "ring": rings,
        "point_time": times,
    }


def validate_imu_message(message: Any, *, bag_record_time: Any | None = None) -> dict[str, Any]:
    if str(message.header.frame_id) != IMU_FRAME:
        raise ValueError(f"IMU frame must be {IMU_FRAME}")
    angular, acceleration = convert_imu_units(
        _xyz(message.angular_velocity), _xyz(message.linear_acceleration)
    )
    return {
        "header_timestamp": message_header_time_seconds(
            message, bag_record_time=bag_record_time
        ),
        "angular_velocity_rad_s": angular.tolist(),
        "linear_acceleration_m_s2": acceleration.tolist(),
        "angular_velocity_conversion_factor": 1.0,
        "linear_acceleration_conversion_factor": 1.0,
    }
