#!/usr/bin/env python3
"""Create detector-free evidence for freezing MUN-FRL pilot intervals.

Only raw PointCloud2 geometry and the position-only NavSatFix trajectory are
read.  This script never imports or evaluates ODI, AIS, Schur information, or
weak-direction detector code.
"""

from __future__ import annotations

import argparse
import csv
import math
import struct
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.navsat_reference import NavSatSample, navsat_to_enu  # noqa: E402
from fastlio2_adapter.mun_frl_contract import (  # noqa: E402
    message_header_time_seconds,
    validate_point_layout,
)


DEFAULT_OUTPUT = (
    ROOT
    / "data/measurement_real_validation/mun_frl_lighthouse_pilot/interval_selection_evidence"
)


def _raw_xyz(message: object, stride: int = 12) -> np.ndarray:
    validate_point_layout(
        message.fields,
        point_step=int(message.point_step),
        is_bigendian=bool(message.is_bigendian),
    )
    data = bytes(message.data)
    points = []
    for offset in range(0, len(data), int(message.point_step) * stride):
        point = struct.unpack_from("<fff", data, offset)
        if all(math.isfinite(value) for value in point):
            points.append(point)
    array = np.asarray(points, dtype=np.float64)
    ranges = np.linalg.norm(array[:, :2], axis=1)
    return array[(ranges >= 1.0) & (ranges <= 60.0) & (np.abs(array[:, 2]) <= 8.0)]


def _descriptor(timestamp: float, points: np.ndarray) -> dict[str, float]:
    centered_xy = points[:, :2] - np.mean(points[:, :2], axis=0)
    eigenvalues = np.linalg.eigvalsh(centered_xy.T @ centered_xy / points.shape[0])
    anisotropy = float(eigenvalues[1] / max(eigenvalues[0], 1.0e-12))
    angles = np.arctan2(points[:, 1], points[:, 0])
    occupied = np.unique(np.floor((angles + np.pi) / (2 * np.pi) * 36).astype(int))
    ranges = np.linalg.norm(points[:, :2], axis=1)
    return {
        "timestamp": timestamp,
        "point_sample_count": int(points.shape[0]),
        "raw_xy_anisotropy": anisotropy,
        "azimuth_sector_coverage": float(len(occupied) / 36.0),
        "range_median_m": float(np.median(ranges)),
        "range_q95_m": float(np.quantile(ranges, 0.95)),
    }


def inspect(bag_path: Path, output_dir: Path) -> None:
    try:
        import rosbag
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("ROS Noetic rosbag is required") from error

    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, float]] = []
    snapshots: list[tuple[float, np.ndarray]] = []
    fixes: list[NavSatSample] = []
    lidar_index = 0
    with rosbag.Bag(str(bag_path), "r") as bag:
        for topic, message, record_time in bag.read_messages(
            topics=["/velodyne_points", "/fix"]
        ):
            if topic == "/fix":
                fixes.append(
                    NavSatSample(
                        timestamp=message_header_time_seconds(
                            message, bag_record_time=record_time
                        ),
                        latitude_deg=float(message.latitude),
                        longitude_deg=float(message.longitude),
                        altitude_m=float(message.altitude),
                        status=int(message.status.status),
                        covariance_x_m2=float(message.position_covariance[0]),
                        covariance_y_m2=float(message.position_covariance[4]),
                        covariance_z_m2=float(message.position_covariance[8]),
                    )
                )
                continue
            # Roughly 1 Hz descriptors and 0.1 Hz scene snapshots.
            if lidar_index % 10 == 0:
                timestamp = message_header_time_seconds(
                    message, bag_record_time=record_time
                )
                points = _raw_xyz(message)
                if points.shape[0] >= 20:
                    rows.append(_descriptor(timestamp, points))
                    if lidar_index % 100 == 0:
                        snapshots.append((timestamp, points.copy()))
            lidar_index += 1

    if not rows or not fixes:
        raise ValueError("raw inspection found no usable LiDAR or NavSatFix data")
    reference = navsat_to_enu(fixes)
    csv_path = output_dir / "raw_scene_descriptors.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    start = rows[0]["timestamp"]
    figure, axes = plt.subplots(3, 1, figsize=(13, 12), constrained_layout=True)
    axes[0].plot(
        reference.positions_enu_m[:, 0],
        reference.positions_enu_m[:, 1],
        color="black",
        linewidth=1.5,
    )
    axes[0].scatter(
        reference.positions_enu_m[0, 0],
        reference.positions_enu_m[0, 1],
        color="green",
        label="first valid RTK",
    )
    axes[0].set(title="Position-only RTK trajectory (detector-free)", xlabel="East [m]", ylabel="North [m]")
    axes[0].axis("equal")
    axes[0].legend()

    relative = [row["timestamp"] - start for row in rows]
    axes[1].plot(relative, [row["raw_xy_anisotropy"] for row in rows], label="raw scan XY anisotropy")
    axes[1].set_yscale("log")
    axes[1].set(xlabel="LiDAR header time from first sampled scan [s]", ylabel="XY covariance eigenvalue ratio")
    axes[1].grid(alpha=0.25)
    axes[1].legend()
    axes[2].plot(relative, [row["azimuth_sector_coverage"] for row in rows], label="occupied azimuth sectors")
    axes[2].plot(relative, [row["range_q95_m"] / 60.0 for row in rows], label="range q95 / 60 m")
    axes[2].set(xlabel="LiDAR header time from first sampled scan [s]", ylabel="detector-free raw scene descriptor")
    axes[2].grid(alpha=0.25)
    axes[2].legend()
    figure.savefig(output_dir / "raw_trajectory_and_geometry.png", dpi=160)
    plt.close(figure)

    columns = 4
    scene_figure, scene_axes = plt.subplots(
        math.ceil(len(snapshots) / columns),
        columns,
        figsize=(16, 4 * math.ceil(len(snapshots) / columns)),
        constrained_layout=True,
        squeeze=False,
    )
    for axis, (timestamp, points) in zip(scene_axes.ravel(), snapshots):
        axis.scatter(points[:, 0], points[:, 1], s=1, alpha=0.45)
        axis.set_title(f"t={timestamp - start:.1f}s")
        axis.set_xlim(-40, 40)
        axis.set_ylim(-40, 40)
        axis.set_aspect("equal")
    for axis in scene_axes.ravel()[len(snapshots) :]:
        axis.axis("off")
    scene_figure.savefig(output_dir / "raw_scan_scene_montage.png", dpi=140)
    plt.close(scene_figure)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bag", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    inspect(args.bag.resolve(), args.output_dir.resolve())
    print(args.output_dir.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
