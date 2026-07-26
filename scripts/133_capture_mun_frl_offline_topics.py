#!/usr/bin/env python3
"""Capture FAST-LIO2 odometry and NavSatFix for later offline evaluation."""

from __future__ import annotations

import argparse
import csv
import json
import threading
from pathlib import Path

import rospy
from nav_msgs.msg import Odometry
from sensor_msgs.msg import NavSatFix


class Capture:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.odom_count = 0
        self.fix_count = 0
        self.odom_handle = (output_dir / "fastlio_odometry.csv").open(
            "w", newline="", encoding="utf-8"
        )
        self.fix_handle = (output_dir / "navsat_fix.csv").open(
            "w", newline="", encoding="utf-8"
        )
        self.odom_writer = csv.writer(self.odom_handle)
        self.fix_writer = csv.writer(self.fix_handle)
        self.odom_writer.writerow(
            [
                "timestamp",
                "position_x",
                "position_y",
                "position_z",
                "orientation_x",
                "orientation_y",
                "orientation_z",
                "orientation_w",
            ]
        )
        self.fix_writer.writerow(
            [
                "timestamp",
                "latitude_deg",
                "longitude_deg",
                "altitude_m",
                "status",
                "service",
                "covariance_x_m2",
                "covariance_y_m2",
                "covariance_z_m2",
                "covariance_type",
            ]
        )

    def odometry(self, message: Odometry) -> None:
        with self.lock:
            position = message.pose.pose.position
            orientation = message.pose.pose.orientation
            self.odom_writer.writerow(
                [
                    message.header.stamp.to_sec(),
                    position.x,
                    position.y,
                    position.z,
                    orientation.x,
                    orientation.y,
                    orientation.z,
                    orientation.w,
                ]
            )
            self.odom_handle.flush()
            self.odom_count += 1

    def fix(self, message: NavSatFix) -> None:
        with self.lock:
            covariance = message.position_covariance
            self.fix_writer.writerow(
                [
                    message.header.stamp.to_sec(),
                    message.latitude,
                    message.longitude,
                    message.altitude,
                    message.status.status,
                    message.status.service,
                    covariance[0],
                    covariance[4],
                    covariance[8],
                    message.position_covariance_type,
                ]
            )
            self.fix_handle.flush()
            self.fix_count += 1

    def close(self) -> None:
        with self.lock:
            self.odom_handle.close()
            self.fix_handle.close()
            summary = {
                "timestamp_source": "message_header",
                "bag_record_epoch_used": False,
                "fastlio_odometry_count": self.odom_count,
                "navsat_fix_count": self.fix_count,
                "reference_is_position_only": True,
                "reference_orientation_available": False,
                "reference_access_role": "offline_evaluation_only",
            }
            (self.output_dir / "topic_capture_summary.json").write_text(
                json.dumps(summary, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args, unknown = parser.parse_known_args()
    del unknown
    rospy.init_node("mun_frl_offline_topic_capture", anonymous=False)
    capture = Capture(args.output_dir.resolve())
    rospy.Subscriber("/Odometry", Odometry, capture.odometry, queue_size=10000)
    rospy.Subscriber("/fix", NavSatFix, capture.fix, queue_size=10000)
    rospy.on_shutdown(capture.close)
    rospy.spin()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
