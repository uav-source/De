#!/usr/bin/env python3
"""Validate the MUN-FRL Lighthouse bag before a Measurement pilot run."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastlio2_adapter.mun_frl_adapter import (  # noqa: E402
    validate_imu_message,
    validate_pointcloud_message,
)
from fastlio2_adapter.mun_frl_contract import (  # noqa: E402
    IMU_MESSAGE_TYPE,
    IMU_RATE_HZ,
    IMU_TOPIC,
    LIDAR_MESSAGE_TYPE,
    LIDAR_RATE_HZ,
    LIDAR_TOPIC,
    REFERENCE_MESSAGE_TYPE,
    REFERENCE_TOPIC,
    R_IMU_LIDAR,
    T_IMU_LIDAR,
    message_header_time_seconds,
    validate_mun_frl_config,
)


DEFAULT_CONFIG = ROOT / "configs/real_data/mun_frl_lighthouse.yaml"
DEFAULT_OUTPUT = (
    ROOT
    / "data/measurement_real_validation/mun_frl_lighthouse_pilot/bag_validation.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sample_indices(count: int) -> set[int]:
    return {0, max(0, count // 2), max(0, count - 1)}


def _merge_extrema(target: dict[str, float], source: dict[str, float]) -> None:
    for name, value in source.items():
        if name.startswith("minimum"):
            target[name] = min(target.get(name, value), value)
        elif name.startswith("maximum"):
            target[name] = max(target.get(name, value), value)
        elif name.startswith("span"):
            target[name] = max(target.get(name, value), value)


def validate_bag(bag_path: Path, config_path: Path) -> dict[str, Any]:
    try:
        import rosbag
    except ImportError as error:  # pragma: no cover - exercised in ROS host
        raise RuntimeError("ROS Noetic rosbag is required for bag validation") from error

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    validate_mun_frl_config(config)
    expected_types = {
        LIDAR_TOPIC: LIDAR_MESSAGE_TYPE,
        IMU_TOPIC: IMU_MESSAGE_TYPE,
        REFERENCE_TOPIC: REFERENCE_MESSAGE_TYPE,
    }

    with rosbag.Bag(str(bag_path), "r") as bag:
        topic_info = bag.get_type_and_topic_info().topics
        for topic, expected_type in expected_types.items():
            if topic not in topic_info:
                raise ValueError(f"required topic is missing: {topic}")
            actual_type = topic_info[topic].msg_type
            if actual_type != expected_type:
                raise ValueError(
                    f"{topic} type must be {expected_type}, got {actual_type}"
                )
        counts = {topic: int(topic_info[topic].message_count) for topic in expected_types}
        sample_indices = {
            topic: _sample_indices(count) for topic, count in counts.items()
        }
        observed = {topic: 0 for topic in expected_types}
        first_header: dict[str, float] = {}
        last_header: dict[str, float] = {}
        max_header_record_delta = {topic: 0.0 for topic in expected_types}
        lidar_time: dict[str, float] = {}
        ring_min, ring_max = 16, -1
        lidar_point_counts: list[int] = []
        imu_samples: list[dict[str, Any]] = []
        valid_fix_count = 0
        invalid_fix_count = 0

        for topic, message, bag_record_time in bag.read_messages(
            topics=list(expected_types)
        ):
            index = observed[topic]
            observed[topic] += 1
            header_time = message_header_time_seconds(
                message, bag_record_time=bag_record_time
            )
            first_header.setdefault(topic, header_time)
            last_header[topic] = header_time
            delta = abs(header_time - float(bag_record_time.to_sec()))
            max_header_record_delta[topic] = max(
                max_header_record_delta[topic], delta
            )

            if topic == REFERENCE_TOPIC:
                finite = all(
                    math.isfinite(float(value))
                    for value in (message.latitude, message.longitude, message.altitude)
                )
                if int(message.status.status) >= 0 and finite:
                    valid_fix_count += 1
                else:
                    invalid_fix_count += 1

            if index not in sample_indices[topic]:
                continue
            if topic == LIDAR_TOPIC:
                sample = validate_pointcloud_message(
                    message, bag_record_time=bag_record_time
                )
                lidar_point_counts.append(int(sample["point_count"]))
                ring_min = min(ring_min, int(sample["ring"]["minimum"]))
                ring_max = max(ring_max, int(sample["ring"]["maximum"]))
                _merge_extrema(lidar_time, sample["point_time"])
            elif topic == IMU_TOPIC:
                imu_samples.append(
                    validate_imu_message(message, bag_record_time=bag_record_time)
                )

    if observed != counts:
        raise ValueError(f"message counts changed while reading bag: {observed}")
    rates = {
        topic: (counts[topic] - 1) / (last_header[topic] - first_header[topic])
        for topic in expected_types
    }
    if not 0.8 * LIDAR_RATE_HZ <= rates[LIDAR_TOPIC] <= 1.2 * LIDAR_RATE_HZ:
        raise ValueError(f"LiDAR rate is not about 10 Hz: {rates[LIDAR_TOPIC]}")
    if not 0.8 * IMU_RATE_HZ <= rates[IMU_TOPIC] <= 1.2 * IMU_RATE_HZ:
        raise ValueError(f"IMU rate is not about 400 Hz: {rates[IMU_TOPIC]}")
    if valid_fix_count == 0:
        raise ValueError("bag has no valid position reference fixes")

    return {
        "schema_version": "measurement_mun_frl_bag_validation_v1",
        "status": "PASS",
        "bag": {
            "path": str(bag_path.resolve()),
            "size_bytes": bag_path.stat().st_size,
            "sha256": sha256_file(bag_path),
        },
        "config": {
            "path": str(config_path.resolve()),
            "sha256": sha256_file(config_path),
            "validation": "PASS",
        },
        "topics": {
            topic: {
                "type": expected_types[topic],
                "message_count": counts[topic],
                "header_rate_hz": rates[topic],
                "first_header_timestamp": first_header[topic],
                "last_header_timestamp": last_header[topic],
                "maximum_header_vs_bag_record_delta_seconds": max_header_record_delta[
                    topic
                ],
            }
            for topic in expected_types
        },
        "point_layout": {
            "validation": "PASS",
            "point_step": 22,
            "little_endian": True,
            "sample_point_counts": lidar_point_counts,
        },
        "point_time": {"validation": "PASS", "unit": "seconds", **lidar_time},
        "ring": {
            "validation": "PASS",
            "sample_minimum": ring_min,
            "sample_maximum": ring_max,
            "allowed_minimum": 0,
            "allowed_maximum": 15,
        },
        "imu_units": {
            "validation": "PASS",
            "angular_velocity": "rad/s",
            "linear_acceleration": "m/s^2",
            "conversion_factor": 1.0,
            "sample_count": len(imu_samples),
        },
        "timestamp_source": "message_header",
        "bag_record_epoch_used": False,
        "extrinsic": {
            "validation": "PASS",
            "direction": "p_imu = R_imu_lidar * p_lidar + t_imu_lidar",
            "inverted": False,
            "translation": T_IMU_LIDAR.tolist(),
            "rotation_row_major": R_IMU_LIDAR.reshape(-1).tolist(),
        },
        "reference": {
            "topic": REFERENCE_TOPIC,
            "role": "offline_position_only_evaluation",
            "reference_is_position_only": True,
            "reference_orientation_available": False,
            "valid_fix_count": valid_fix_count,
            "invalid_fix_count": invalid_fix_count,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bag", type=Path, default=os.environ.get("MUN_FRL_BAG"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.bag is None:
        raise SystemExit("provide --bag or set MUN_FRL_BAG")
    bag_path = args.bag.expanduser().resolve()
    if not bag_path.is_file():
        raise SystemExit(f"bag does not exist: {bag_path}")
    report = validate_bag(bag_path, args.config.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
