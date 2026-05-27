"""Generate Day 1-14 minimum synthetic geometry scenes.

This module intentionally generates only geometry, ground-truth poses, axes,
and metadata. It does not create Day 5 observations, Day 7 toy LIO estimates,
or Day 14 figures.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Plane:
    plane_id: str
    frame_start: int
    frame_end: int
    normal: np.ndarray
    point: np.ndarray
    semantic: str


@dataclass
class Sequence:
    sequence_id: str
    gt_poses: np.ndarray
    axis: np.ndarray
    planes: List[Plane]
    feature_points: np.ndarray
    metadata: Dict[str, Any]


def load_scene_config(path: str | Path) -> Dict[str, Any]:
    """Load a minibench YAML config and attach reproducibility metadata."""

    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Scene config must be a mapping: {config_path}")

    config["_config_path"] = str(config_path)
    config["_config_sha256"] = sha256_file(config_path)
    return config


def generate_open_control(config: Dict[str, Any]) -> Sequence:
    rng = np.random.default_rng(int(config["random_seed"]))
    frames = int(config["frames"])
    timestamps = make_timestamps(frames, float(config["dt_s"]))

    length_m = float(config["length_m"])
    x = np.linspace(-0.5 * length_m, 0.5 * length_m, frames)
    phase = np.linspace(0.0, 2.0 * math.pi, frames)
    y = 5.0 * np.sin(phase)
    z = 2.0 + 0.4 * np.sin(2.0 * phase + 0.3)
    positions = np.column_stack([x, y, z])
    yaw = yaw_from_positions(positions)
    gt_poses = make_tum_poses(timestamps, positions, yaw)

    axis = np.tile(np.array(config["axis"], dtype=float), (frames, 1))
    axis = normalize_rows(axis)

    normals = isotropic_normals()
    bounds = np.array(config["scene"]["bounds_m"], dtype=float)
    planes: List[Plane] = []
    for index, normal in enumerate(normals):
        point = rng.uniform(-0.5, 0.5, size=3) * bounds
        planes.append(
            Plane(
                plane_id=f"oc_plane_{index:02d}",
                frame_start=0,
                frame_end=frames - 1,
                normal=normal,
                point=point,
                semantic="open_control_plane",
            )
        )

    feature_points = sample_open_points(rng, bounds, int(config["scene"]["box_count"]))
    return make_sequence(config, gt_poses, axis, planes, feature_points)


def generate_straight_tunnel(config: Dict[str, Any]) -> Sequence:
    frames = int(config["frames"])
    timestamps = make_timestamps(frames, float(config["dt_s"]))
    length_m = float(config["tunnel_length_m"])
    width_m = float(config["width_m"])
    height_m = float(config["height_m"])

    x = np.linspace(0.0, length_m, frames)
    y = np.zeros(frames)
    z = np.full(frames, 0.5 * height_m)
    positions = np.column_stack([x, y, z])
    yaw = np.zeros(frames)
    gt_poses = make_tum_poses(timestamps, positions, yaw)

    axis = np.tile(np.array(config["axis"], dtype=float), (frames, 1))
    axis = normalize_rows(axis)
    planes = rectangular_tunnel_planes(frames, width_m, height_m)
    feature_points = sample_tunnel_features(
        length_m=length_m,
        width_m=width_m,
        height_m=height_m,
        repeat_period_m=None,
    )
    return make_sequence(config, gt_poses, axis, planes, feature_points)


def generate_curved_tunnel(config: Dict[str, Any]) -> Sequence:
    frames = int(config["frames"])
    timestamps = make_timestamps(frames, float(config["dt_s"]))
    radius = float(config["curve_radius_m"])
    arc_length = float(config["arc_length_m"])
    width_m = float(config["scene"]["width_m"])
    height_m = float(config["scene"]["height_m"])

    angle_span = arc_length / radius
    theta = np.linspace(-0.5 * angle_span, 0.5 * angle_span, frames)
    x = radius * np.sin(theta)
    y = radius * (1.0 - np.cos(theta))
    z = np.full(frames, 0.5 * height_m)
    positions = np.column_stack([x, y, z])

    axis = np.column_stack([np.cos(theta), np.sin(theta), np.zeros(frames)])
    axis = normalize_rows(axis)
    yaw = np.arctan2(axis[:, 1], axis[:, 0])
    gt_poses = make_tum_poses(timestamps, positions, yaw)

    # Approximate representative local planes at the middle of the arc. The Day
    # 5 simulator can later use axis.csv for framewise local Jacobians.
    planes = rectangular_tunnel_planes(frames, width_m, height_m, prefix="ct")
    feature_points = sample_curved_tunnel_features(radius, arc_length, width_m, height_m)
    return make_sequence(config, gt_poses, axis, planes, feature_points)


def generate_repetitive_tunnel(config: Dict[str, Any]) -> Sequence:
    frames = int(config["frames"])
    timestamps = make_timestamps(frames, float(config["dt_s"]))
    length_m = float(config["tunnel_length_m"])
    width_m = float(config["width_m"])
    height_m = float(config["height_m"])
    repeat_period = float(config["scene"]["repeat_period_m"])

    x = np.linspace(0.0, length_m, frames)
    y = np.zeros(frames)
    z = np.full(frames, 0.5 * height_m)
    positions = np.column_stack([x, y, z])
    gt_poses = make_tum_poses(timestamps, positions, np.zeros(frames))

    axis = np.tile(np.array(config["axis"], dtype=float), (frames, 1))
    axis = normalize_rows(axis)
    planes = rectangular_tunnel_planes(frames, width_m, height_m, prefix="rt")
    planes.extend(repeated_feature_planes(frames, length_m, width_m, height_m, repeat_period))
    feature_points = sample_tunnel_features(
        length_m=length_m,
        width_m=width_m,
        height_m=height_m,
        repeat_period_m=repeat_period,
    )
    return make_sequence(config, gt_poses, axis, planes, feature_points)


def save_sequence(sequence: Sequence, output_dir: str | Path) -> None:
    """Save generated sequence files required by the Day 4 contract."""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    np.savetxt(
        out / "gt.tum",
        sequence.gt_poses,
        fmt="%.9f %.9f %.9f %.9f %.9f %.9f %.9f %.9f",
    )
    save_axis_csv(out / "axis.csv", sequence.gt_poses[:, 0], sequence.axis)
    save_planes_csv(out / "planes.csv", sequence.planes)
    save_feature_points_csv(out / "feature_points.csv", sequence.feature_points)
    (out / "scene_metadata.json").write_text(
        json.dumps(sequence.metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def make_sequence(
    config: Dict[str, Any],
    gt_poses: np.ndarray,
    axis: np.ndarray,
    planes: List[Plane],
    feature_points: np.ndarray,
) -> Sequence:
    sequence_id = str(config["sequence_id"])
    metadata = {
        "sequence_id": sequence_id,
        "scene_family": config["scene_family"],
        "difficulty": config["difficulty"],
        "seed_id": config["seed_id"],
        "motion_id": config["motion_id"],
        "random_seed": int(config["random_seed"]),
        "config_path": config.get("_config_path"),
        "config_sha256": config.get("_config_sha256"),
        "expected_degeneracy": config["expected_degeneracy"],
        "scientific_role": config["scientific_role"],
        "frames": int(config["frames"]),
        "dt_s": float(config["dt_s"]),
        "gt_pose_columns": "timestamp tx ty tz qx qy qz qw",
        "gt_pose_shape": list(gt_poses.shape),
        "axis_shape": list(axis.shape),
        "plane_count": len(planes),
        "feature_point_count": int(feature_points.shape[0]),
        "generated_by": "scripts/00_generate_minibench.py",
        "git_commit": git_commit(),
    }
    return Sequence(sequence_id, gt_poses, axis, planes, feature_points, metadata)


def make_timestamps(frames: int, dt_s: float) -> np.ndarray:
    return np.arange(frames, dtype=float) * dt_s


def make_tum_poses(timestamps: np.ndarray, positions: np.ndarray, yaw: np.ndarray) -> np.ndarray:
    q = yaw_to_quaternion(yaw)
    return np.column_stack([timestamps, positions, q])


def yaw_to_quaternion(yaw: np.ndarray) -> np.ndarray:
    half = 0.5 * yaw
    zeros = np.zeros_like(yaw)
    return np.column_stack([zeros, zeros, np.sin(half), np.cos(half)])


def yaw_from_positions(positions: np.ndarray) -> np.ndarray:
    delta = np.gradient(positions[:, :2], axis=0)
    return np.arctan2(delta[:, 1], delta[:, 0])


def normalize_rows(values: np.ndarray, eps: float = 1.0e-12) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.maximum(norms, eps)


def normalize_vector(values: Iterable[float]) -> np.ndarray:
    vector = np.asarray(list(values), dtype=float)
    norm = np.linalg.norm(vector)
    if norm == 0:
        raise ValueError("Cannot normalize zero vector")
    return vector / norm


def isotropic_normals() -> np.ndarray:
    raw = [
        [1, 0, 0],
        [-1, 0, 0],
        [0, 1, 0],
        [0, -1, 0],
        [0, 0, 1],
        [0, 0, -1],
        [1, 1, 1],
        [1, 1, -1],
        [1, -1, 1],
        [1, -1, -1],
        [-1, 1, 1],
        [-1, 1, -1],
        [-1, -1, 1],
        [-1, -1, -1],
        [1, 1, 0],
        [-1, -1, 0],
        [1, -1, 0],
        [-1, 1, 0],
    ]
    return np.array([normalize_vector(v) for v in raw])


def rectangular_tunnel_planes(
    frames: int,
    width_m: float,
    height_m: float,
    prefix: str = "st",
) -> List[Plane]:
    return [
        Plane(
            f"{prefix}_left_wall",
            0,
            frames - 1,
            np.array([0.0, -1.0, 0.0]),
            np.array([0.0, 0.5 * width_m, 0.5 * height_m]),
            "left_wall",
        ),
        Plane(
            f"{prefix}_right_wall",
            0,
            frames - 1,
            np.array([0.0, 1.0, 0.0]),
            np.array([0.0, -0.5 * width_m, 0.5 * height_m]),
            "right_wall",
        ),
        Plane(
            f"{prefix}_floor",
            0,
            frames - 1,
            np.array([0.0, 0.0, 1.0]),
            np.array([0.0, 0.0, 0.0]),
            "floor",
        ),
        Plane(
            f"{prefix}_ceiling",
            0,
            frames - 1,
            np.array([0.0, 0.0, -1.0]),
            np.array([0.0, 0.0, height_m]),
            "ceiling",
        ),
    ]


def repeated_feature_planes(
    frames: int,
    length_m: float,
    width_m: float,
    height_m: float,
    repeat_period_m: float,
) -> List[Plane]:
    planes: List[Plane] = []
    repeat_count = int(math.floor(length_m / repeat_period_m))
    for index in range(1, repeat_count):
        x = index * repeat_period_m
        planes.extend(
            [
                Plane(
                    f"rt_side_patch_left_{index:02d}",
                    0,
                    frames - 1,
                    np.array([0.0, -1.0, 0.0]),
                    np.array([x, 0.5 * width_m, 0.5 * height_m]),
                    "repeated_side_patch",
                ),
                Plane(
                    f"rt_ceiling_rib_{index:02d}",
                    0,
                    frames - 1,
                    np.array([0.0, 0.0, -1.0]),
                    np.array([x, 0.0, height_m]),
                    "repeated_ceiling_rib",
                ),
            ]
        )
    return planes


def sample_open_points(rng: np.random.Generator, bounds: np.ndarray, box_count: int) -> np.ndarray:
    points = []
    for _ in range(box_count * 20):
        points.append(rng.uniform(-0.5, 0.5, size=3) * bounds)
    return np.asarray(points, dtype=float)


def sample_tunnel_features(
    length_m: float,
    width_m: float,
    height_m: float,
    repeat_period_m: Optional[float],
) -> np.ndarray:
    xs = np.linspace(0.0, length_m, 80)
    points = []
    for x in xs:
        points.extend(
            [
                [x, -0.5 * width_m, 0.25 * height_m],
                [x, 0.5 * width_m, 0.75 * height_m],
                [x, 0.0, 0.0],
                [x, 0.0, height_m],
            ]
        )
    if repeat_period_m is not None:
        for x in np.arange(repeat_period_m, length_m, repeat_period_m):
            points.extend(
                [
                    [x, -0.5 * width_m, 0.5 * height_m],
                    [x, 0.5 * width_m, 0.5 * height_m],
                    [x, 0.0, 0.15 * height_m],
                    [x, 0.0, 0.85 * height_m],
                ]
            )
    return np.asarray(points, dtype=float)


def sample_curved_tunnel_features(
    radius: float,
    arc_length: float,
    width_m: float,
    height_m: float,
) -> np.ndarray:
    theta = np.linspace(-0.5 * arc_length / radius, 0.5 * arc_length / radius, 80)
    points = []
    for t in theta:
        center = np.array([radius * math.sin(t), radius * (1.0 - math.cos(t)), 0.0])
        normal = np.array([-math.sin(t), math.cos(t), 0.0])
        for side in [-0.5 * width_m, 0.5 * width_m]:
            p = center + side * normal
            points.append([p[0], p[1], 0.5 * height_m])
        points.append([center[0], center[1], 0.0])
        points.append([center[0], center[1], height_m])
    return np.asarray(points, dtype=float)


def save_axis_csv(path: Path, timestamps: np.ndarray, axis: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "axis_x", "axis_y", "axis_z", "reliable"])
        for timestamp, row in zip(timestamps, axis):
            writer.writerow([f"{timestamp:.9f}", f"{row[0]:.9f}", f"{row[1]:.9f}", f"{row[2]:.9f}", 1])


def save_planes_csv(path: Path, planes: List[Plane]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["plane_id", "frame_start", "frame_end", "nx", "ny", "nz", "qx", "qy", "qz", "semantic"])
        for plane in planes:
            n = plane.normal
            q = plane.point
            writer.writerow(
                [
                    plane.plane_id,
                    plane.frame_start,
                    plane.frame_end,
                    f"{n[0]:.9f}",
                    f"{n[1]:.9f}",
                    f"{n[2]:.9f}",
                    f"{q[0]:.9f}",
                    f"{q[1]:.9f}",
                    f"{q[2]:.9f}",
                    plane.semantic,
                ]
            )


def save_feature_points_csv(path: Path, points: np.ndarray) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["x", "y", "z"])
        for point in points:
            writer.writerow([f"{point[0]:.9f}", f"{point[1]:.9f}", f"{point[2]:.9f}"])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit() -> Optional[str]:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

