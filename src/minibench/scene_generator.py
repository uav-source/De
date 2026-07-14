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
class PlanePatch:
    plane_id: str
    frame_start: int
    frame_end: int
    normal: np.ndarray
    point: np.ndarray
    semantic: str
    u_axis: Optional[np.ndarray] = None
    v_axis: Optional[np.ndarray] = None
    half_u: float = 1000.0
    half_v: float = 1000.0
    sampling_weight: float = 1.0
    is_axial_support: bool = False
    axial_normal_component: Optional[float] = None
    projected_axial_area: Optional[float] = None
    support_strength: Optional[float] = None

    def __post_init__(self) -> None:
        self.normal = normalize_vector(self.normal)
        if self.u_axis is None or self.v_axis is None:
            self.u_axis, self.v_axis = plane_basis(self.normal)
        else:
            self.u_axis = normalize_vector(self.u_axis)
            self.u_axis = normalize_vector(self.u_axis - self.normal * float(self.normal @ self.u_axis))
            self.v_axis = normalize_vector(np.cross(self.normal, self.u_axis))
            if float(self.v_axis @ np.asarray(self.v_axis, dtype=float)) <= 0.0:
                raise ValueError("Invalid plane-patch basis")
        if abs(float(self.normal @ self.u_axis)) > 1.0e-8:
            raise ValueError("PlanePatch normal and u_axis must be orthogonal")
        if abs(float(self.normal @ self.v_axis)) > 1.0e-8 or abs(float(self.u_axis @ self.v_axis)) > 1.0e-8:
            raise ValueError("PlanePatch basis must be orthogonal")
        self.point = np.asarray(self.point, dtype=float)
        self.half_u = float(self.half_u)
        self.half_v = float(self.half_v)
        self.sampling_weight = float(self.sampling_weight)
        if self.half_u <= 0.0 or self.half_v <= 0.0:
            raise ValueError("PlanePatch half extents must be positive")
        if self.sampling_weight < 0.0:
            raise ValueError("PlanePatch sampling_weight must be non-negative")

    @property
    def patch_id(self) -> str:
        return self.plane_id

    @property
    def center(self) -> np.ndarray:
        return self.point

    @property
    def visible_frame_start(self) -> int:
        return self.frame_start

    @property
    def visible_frame_end(self) -> int:
        return self.frame_end

    @property
    def area(self) -> float:
        return 4.0 * self.half_u * self.half_v


# Backward-compatible public name used by the Day 1-14 pipeline.
Plane = PlanePatch


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
    rng = np.random.default_rng(int(config.get("geometry_seed", config["random_seed"])))
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
    rng = np.random.default_rng(int(config.get("geometry_seed", config["random_seed"])))
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
    if "master_axial_patch_pool_size" in config:
        planes = build_rectangular_tunnel_patches(frames, length_m, width_m, height_m, prefix="nested")
        master_pool = generate_master_axial_patch_pool(
            int(config.get("geometry_seed", config["random_seed"])),
            length_m,
            width_m,
            height_m,
            int(config["master_axial_patch_pool_size"]),
        )
        active_count = int(config.get("active_axial_patch_count", len(master_pool)))
        if not 0 < active_count <= len(master_pool):
            raise ValueError("active_axial_patch_count must select a non-empty master-pool prefix")
        planes.extend(master_pool[:active_count])
        for plane in planes:
            plane.sampling_weight = 1.0
    elif "axial_support_fraction" in config:
        planes = build_rectangular_tunnel_patches(frames, length_m, width_m, height_m, prefix="st")
        planes.extend(
            build_axial_support_patches(
                length_m,
                width_m,
                height_m,
                int(config.get("axial_patch_count", 8)),
                float(config["axial_support_fraction"]),
                rng,
                frames=frames,
                prefix="st",
            )
        )
        set_sampling_fraction(planes, float(config["axial_support_fraction"]))
    else:
        planes = rectangular_tunnel_planes(frames, width_m, height_m, length_m=length_m)
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
    planes = rectangular_tunnel_planes(frames, width_m, height_m, prefix="ct", length_m=arc_length)
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
    planes = rectangular_tunnel_planes(frames, width_m, height_m, prefix="rt", length_m=length_m)
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
        "geometry_seed": int(config.get("geometry_seed", config["random_seed"])),
        "axial_support_fraction": float(config.get("axial_support_fraction", 0.0)),
        "axial_patch_count": int(config.get("axial_patch_count", 0)),
        "geometry_schema": "finite_plane_patch_v1" if "geometry_seed" in config else "legacy_plane_compatible_v1",
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
    if "master_axial_patch_pool_size" in config:
        axis_unit = normalize_vector(config["axis"])
        axial = [plane for plane in planes if plane.is_axial_support]
        shell = [plane for plane in planes if not plane.is_axial_support]
        support = [plane.area * float(plane.normal @ axis_unit) ** 2 for plane in axial]
        abs_components = [abs(float(plane.normal @ axis_unit)) for plane in axial]
        metadata.update(
            {
                "master_pool_checksum": master_axial_patch_pool_checksum(
                    generate_master_axial_patch_pool(
                        int(config.get("geometry_seed", config["random_seed"])),
                        float(config["tunnel_length_m"]),
                        float(config["width_m"]),
                        float(config["height_m"]),
                        int(config["master_axial_patch_pool_size"]),
                    )
                ),
                "active_patch_ids": [plane.plane_id for plane in axial],
                "active_axial_patch_count": len(axial),
                "total_axial_patch_area": float(sum(plane.area for plane in axial)),
                "total_projected_axial_area": float(sum(support)),
                "mean_abs_axis_normal_component": float(np.mean(abs_components)),
                "median_abs_axis_normal_component": float(np.median(abs_components)),
                "geometry_axial_support_score": float(sum(support)),
                "non_axial_shell_checksum": plane_patch_checksum(shell),
                # This checksum deliberately describes the frozen policy, not
                # the number of active planes. Every nested patch has weight 1.
                "sampling_weight_checksum": hashlib.sha256(b"nested:all_sampling_weights=1.0").hexdigest(),
                "sampling_weight_values": sorted({float(plane.sampling_weight) for plane in planes}),
                "geometry_metadata_schema": "nested_real_geometry_v2",
            }
        )
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


def plane_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = normalize_vector(normal)
    candidate = np.array([0.0, 0.0, 1.0])
    if abs(float(n @ candidate)) > 0.9:
        candidate = np.array([1.0, 0.0, 0.0])
    u = normalize_vector(np.cross(n, candidate))
    v = normalize_vector(np.cross(n, u))
    return u, v


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
    length_m: float = 200.0,
) -> List[Plane]:
    return build_rectangular_tunnel_patches(frames, length_m, width_m, height_m, prefix)


def build_rectangular_tunnel_patches(
    frames: int,
    length_m: float,
    width_m: float,
    height_m: float,
    prefix: str = "st",
) -> List[PlanePatch]:
    center_x = 0.5 * float(length_m)
    return [
        Plane(
            f"{prefix}_left_wall",
            0,
            frames - 1,
            np.array([0.0, -1.0, 0.0]),
            np.array([center_x, 0.5 * width_m, 0.5 * height_m]),
            "left_wall",
            np.array([1.0, 0.0, 0.0]),
            np.array([0.0, 0.0, 1.0]),
            0.5 * length_m,
            0.5 * height_m,
        ),
        Plane(
            f"{prefix}_right_wall",
            0,
            frames - 1,
            np.array([0.0, 1.0, 0.0]),
            np.array([center_x, -0.5 * width_m, 0.5 * height_m]),
            "right_wall",
            np.array([1.0, 0.0, 0.0]),
            np.array([0.0, 0.0, -1.0]),
            0.5 * length_m,
            0.5 * height_m,
        ),
        Plane(
            f"{prefix}_floor",
            0,
            frames - 1,
            np.array([0.0, 0.0, 1.0]),
            np.array([center_x, 0.0, 0.0]),
            "floor",
            np.array([1.0, 0.0, 0.0]),
            np.array([0.0, 1.0, 0.0]),
            0.5 * length_m,
            0.5 * width_m,
        ),
        Plane(
            f"{prefix}_ceiling",
            0,
            frames - 1,
            np.array([0.0, 0.0, -1.0]),
            np.array([center_x, 0.0, height_m]),
            "ceiling",
            np.array([1.0, 0.0, 0.0]),
            np.array([0.0, -1.0, 0.0]),
            0.5 * length_m,
            0.5 * width_m,
        ),
    ]


def build_axial_support_patches(
    length_m: float,
    width_m: float,
    height_m: float,
    count: int,
    axial_support_fraction: float,
    rng: np.random.Generator,
    frames: int = 100,
    prefix: str = "st",
) -> List[PlanePatch]:
    """Build local, finite structures whose normals contain axial support."""

    fraction = float(axial_support_fraction)
    if not 0.0 < fraction < 1.0:
        raise ValueError("axial_support_fraction must be in (0, 1)")
    if count <= 0:
        raise ValueError("axial_patch_count must be positive")
    xs = np.linspace(0.08 * length_m, 0.92 * length_m, count)
    xs += rng.uniform(-0.025 * length_m, 0.025 * length_m, size=count)
    patches: List[PlanePatch] = []
    for index, x in enumerate(np.clip(xs, 0.04 * length_m, 0.96 * length_m)):
        side = -1.0 if index % 2 == 0 else 1.0
        # Keep support non-zero but locally oblique: the prescribed support
        # fraction, rather than a near-end-cap normal, controls the level.
        axial = rng.uniform(0.18, 0.32)
        transverse = math.sqrt(max(1.0 - axial * axial, 1.0e-6))
        orientation = index % 4
        if orientation < 2:
            normal = normalize_vector([axial, -transverse if orientation == 0 else transverse, 0.0])
        else:
            normal = normalize_vector([axial, 0.0, -transverse if orientation == 2 else transverse])
        u_axis, v_axis = plane_basis(normal)
        y = side * (0.5 * width_m - rng.uniform(0.05, 0.20))
        z = rng.uniform(0.25 * height_m, 0.75 * height_m)
        frame_center = int(round((x / max(length_m, 1.0e-9)) * (frames - 1)))
        radius = max(2, int(math.ceil(frames * 0.10)))
        patches.append(
            PlanePatch(
                plane_id=f"{prefix}_axial_patch_{index:02d}",
                frame_start=max(0, frame_center - radius),
                frame_end=min(frames - 1, frame_center + radius),
                normal=normal,
                point=np.array([x, y, z]),
                semantic="local_axial_support",
                u_axis=u_axis,
                v_axis=v_axis,
                half_u=rng.uniform(0.25, 0.55),
                half_v=rng.uniform(0.25, 0.70),
                sampling_weight=fraction / count,
                is_axial_support=True,
            )
        )
    return patches


def generate_master_axial_patch_pool(
    geometry_seed: int,
    tunnel_length_m: float,
    width_m: float,
    height_m: float,
    pool_size: int,
) -> List[PlanePatch]:
    """Generate one deterministic, strength-ranked Stage 1b patch pool.

    Geometry levels select nested prefixes of this pool. Sampling weights are
    frozen at one, so level changes are physical additions/removals of finite
    surfaces rather than observation-probability changes.
    """

    if pool_size < 1:
        raise ValueError("pool_size must be positive")
    rng = np.random.default_rng(int(geometry_seed))
    xs = np.linspace(0.06 * tunnel_length_m, 0.94 * tunnel_length_m, pool_size)
    xs += rng.uniform(-0.018 * tunnel_length_m, 0.018 * tunnel_length_m, size=pool_size)
    axis = np.array([1.0, 0.0, 0.0])
    patches: List[PlanePatch] = []
    for index, x in enumerate(np.clip(xs, 0.03 * tunnel_length_m, 0.97 * tunnel_length_m)):
        axial_component = rng.uniform(0.25, 0.92)
        transverse = math.sqrt(max(1.0 - axial_component**2, 1.0e-12))
        orientation = index % 4
        if orientation == 0:
            normal = normalize_vector([axial_component, transverse, 0.0])
        elif orientation == 1:
            normal = normalize_vector([axial_component, -transverse, 0.0])
        elif orientation == 2:
            normal = normalize_vector([axial_component, 0.0, transverse])
        else:
            normal = normalize_vector([axial_component, 0.0, -transverse])
        u_axis, v_axis = plane_basis(normal)
        half_u = float(rng.uniform(0.28, 0.85))
        half_v = float(rng.uniform(0.28, 0.90))
        area = 4.0 * half_u * half_v
        strength = area * float(normal @ axis) ** 2
        y = float(rng.uniform(-0.42 * width_m, 0.42 * width_m))
        z = float(rng.uniform(0.18 * height_m, 0.82 * height_m))
        patches.append(
            PlanePatch(
                plane_id=f"axial_patch_{index:02d}",
                frame_start=0,
                frame_end=2**31 - 1,
                normal=normal,
                point=np.array([x, y, z]),
                semantic="real_axial_structure",
                u_axis=u_axis,
                v_axis=v_axis,
                half_u=half_u,
                half_v=half_v,
                sampling_weight=1.0,
                is_axial_support=True,
                axial_normal_component=abs(float(normal @ axis)),
                projected_axial_area=strength,
                support_strength=strength,
            )
        )
    return sorted(patches, key=lambda patch: (-float(patch.support_strength or 0.0), patch.plane_id))


def plane_patch_checksum(planes: List[PlanePatch]) -> str:
    payload = []
    for plane in planes:
        payload.append(
            {
                "plane_id": plane.plane_id,
                "frame_start": plane.frame_start,
                "frame_end": plane.frame_end,
                "normal": np.round(plane.normal, 12).tolist(),
                "point": np.round(plane.point, 12).tolist(),
                "u_axis": np.round(plane.u_axis, 12).tolist(),
                "v_axis": np.round(plane.v_axis, 12).tolist(),
                "half_u": round(plane.half_u, 12),
                "half_v": round(plane.half_v, 12),
                "sampling_weight": round(plane.sampling_weight, 12),
                "is_axial_support": plane.is_axial_support,
            }
        )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def master_axial_patch_pool_checksum(planes: List[PlanePatch]) -> str:
    return plane_patch_checksum(planes)


def set_sampling_fraction(planes: List[PlanePatch], axial_support_fraction: float) -> None:
    base = [plane for plane in planes if not plane.is_axial_support]
    axial = [plane for plane in planes if plane.is_axial_support]
    if not base or not axial:
        raise ValueError("Both base and axial-support patches are required")
    for plane in base:
        plane.sampling_weight = (1.0 - axial_support_fraction) / len(base)
    for plane in axial:
        plane.sampling_weight = axial_support_fraction / len(axial)


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
        frame_center = int(round((x / max(length_m, 1.0e-9)) * (frames - 1)))
        frame_radius = max(2, int(math.ceil(frames * 0.06)))
        planes.extend(
            [
                Plane(
                    f"rt_side_patch_left_{index:02d}",
                    max(0, frame_center - frame_radius),
                    min(frames - 1, frame_center + frame_radius),
                    np.array([0.0, -1.0, 0.0]),
                    np.array([x, 0.5 * width_m, 0.5 * height_m]),
                    "repeated_side_patch",
                    half_u=0.35 * repeat_period_m,
                    half_v=0.35 * height_m,
                    sampling_weight=0.05,
                ),
                Plane(
                    f"rt_ceiling_rib_{index:02d}",
                    max(0, frame_center - frame_radius),
                    min(frames - 1, frame_center + frame_radius),
                    np.array([0.0, 0.0, -1.0]),
                    np.array([x, 0.0, height_m]),
                    "repeated_ceiling_rib",
                    half_u=0.35 * repeat_period_m,
                    half_v=0.35 * width_m,
                    sampling_weight=0.05,
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
        writer.writerow([
            "plane_id", "frame_start", "frame_end", "nx", "ny", "nz", "qx", "qy", "qz", "semantic",
            "ux", "uy", "uz", "vx", "vy", "vz", "half_u", "half_v", "sampling_weight", "is_axial_support",
            "axial_normal_component", "projected_axial_area", "support_strength",
        ])
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
                    f"{plane.u_axis[0]:.9f}",
                    f"{plane.u_axis[1]:.9f}",
                    f"{plane.u_axis[2]:.9f}",
                    f"{plane.v_axis[0]:.9f}",
                    f"{plane.v_axis[1]:.9f}",
                    f"{plane.v_axis[2]:.9f}",
                    f"{plane.half_u:.9f}",
                    f"{plane.half_v:.9f}",
                    f"{plane.sampling_weight:.9f}",
                    int(plane.is_axial_support),
                    "" if plane.axial_normal_component is None else f"{plane.axial_normal_component:.9f}",
                    "" if plane.projected_axial_area is None else f"{plane.projected_axial_area:.9f}",
                    "" if plane.support_strength is None else f"{plane.support_strength:.9f}",
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
