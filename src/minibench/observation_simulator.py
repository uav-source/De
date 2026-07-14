"""Simulate point-to-plane Jacobians for Day 5.

This module creates framewise residual Jacobians only. It does not compute ODI,
does not run toy LIO, and does not use ground-truth error to construct the
Jacobian. Ground truth pose is used only as the synthetic sensor pose from which
LiDAR points are generated.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class ObservationPlane:
    plane_id: str
    normal: np.ndarray
    point: np.ndarray
    semantic: str
    frame_start: int = 0
    frame_end: int = 2**31 - 1
    u_axis: Optional[np.ndarray] = None
    v_axis: Optional[np.ndarray] = None
    half_u: float = 1000.0
    half_v: float = 1000.0
    sampling_weight: float = 1.0
    is_axial_support: bool = False

    def __post_init__(self) -> None:
        self.normal = normalize_vector(self.normal)
        if self.u_axis is None or self.v_axis is None:
            self.u_axis, self.v_axis = plane_basis(self.normal)
        else:
            self.u_axis = normalize_vector(self.u_axis)
            self.u_axis = normalize_vector(self.u_axis - self.normal * float(self.normal @ self.u_axis))
            self.v_axis = normalize_vector(np.cross(self.normal, self.u_axis))
        self.point = np.asarray(self.point, dtype=float)
        self.half_u = float(self.half_u)
        self.half_v = float(self.half_v)
        self.sampling_weight = float(self.sampling_weight)
        if self.half_u <= 0.0 or self.half_v <= 0.0:
            raise ValueError("ObservationPlane half extents must be positive")


@dataclass
class SequenceData:
    sequence_id: str
    sequence_dir: Path
    metadata: Dict[str, Any]
    sequence_config: Dict[str, Any]
    gt_poses: np.ndarray
    axis: np.ndarray
    static_planes: List[ObservationPlane]


def load_sequence(sequence_dir: Union[str, Path]) -> SequenceData:
    seq_dir = Path(sequence_dir)
    metadata = json.loads((seq_dir / "scene_metadata.json").read_text(encoding="utf-8"))
    sequence_config = load_sequence_config(metadata)
    gt_poses = np.loadtxt(seq_dir / "gt.tum", dtype=float)
    if gt_poses.ndim == 1:
        gt_poses = gt_poses.reshape(1, -1)
    axis = load_axis_csv(seq_dir / "axis.csv")
    static_planes = load_planes_csv(seq_dir / "planes.csv")
    return SequenceData(
        sequence_id=metadata["sequence_id"],
        sequence_dir=seq_dir,
        metadata=metadata,
        sequence_config=sequence_config,
        gt_poses=gt_poses,
        axis=axis,
        static_planes=static_planes,
    )


def load_detector_config(path: Union[str, Path]) -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Detector config must be a mapping: {path}")
    return config


def load_sequence_config(metadata: Dict[str, Any]) -> Dict[str, Any]:
    sequence_id = metadata.get("sequence_id")
    candidates = []

    config_path = metadata.get("config_path")
    if config_path:
        path = Path(config_path)
        candidates.append(path if path.is_absolute() else Path.cwd() / path)

    if sequence_id:
        candidates.append(REPO_ROOT / "configs" / "minibench" / f"{sequence_id}.yaml")

    for path in candidates:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                config = yaml.safe_load(handle)
            if not isinstance(config, dict):
                raise ValueError(f"Sequence config must be a mapping: {path}")
            return config

    searched = ", ".join(str(path) for path in candidates) if candidates else "<no candidates>"
    raise FileNotFoundError(
        f"Could not locate sequence config for sequence_id={sequence_id!r}; searched: {searched}"
    )


def load_axis_csv(path: Path) -> np.ndarray:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append([float(row["axis_x"]), float(row["axis_y"]), float(row["axis_z"])])
    return normalize_rows(np.asarray(rows, dtype=float))


def load_planes_csv(path: Path) -> List[ObservationPlane]:
    planes: List[ObservationPlane] = []
    with path.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            has_patch_fields = all(row.get(key, "") != "" for key in ["ux", "uy", "uz", "vx", "vy", "vz"])
            normal = normalize_vector([float(row["nx"]), float(row["ny"]), float(row["nz"])])
            u_axis, v_axis = plane_basis(normal)
            if has_patch_fields:
                u_axis = normalize_vector([float(row["ux"]), float(row["uy"]), float(row["uz"])])
                v_axis = normalize_vector([float(row["vx"]), float(row["vy"]), float(row["vz"])])
            planes.append(
                ObservationPlane(
                    plane_id=row["plane_id"],
                    normal=normal,
                    point=np.array([float(row["qx"]), float(row["qy"]), float(row["qz"])], dtype=float),
                    semantic=row["semantic"],
                    frame_start=int(row.get("frame_start", 0)),
                    frame_end=int(row.get("frame_end", 2**31 - 1)),
                    u_axis=u_axis,
                    v_axis=v_axis,
                    half_u=float(row.get("half_u") or 1000.0),
                    half_v=float(row.get("half_v") or 1000.0),
                    sampling_weight=float(row.get("sampling_weight") or 1.0),
                    is_axial_support=str(row.get("is_axial_support", "0")).lower() in {"1", "true", "yes"},
                )
            )
    return planes


def simulate_lidar_points(sequence: SequenceData, config: Dict[str, Any], sensor_seed: Optional[int] = None) -> Dict[str, np.ndarray]:
    """Generate framewise synthetic LiDAR points and associated plane normals."""

    resolved_seed = resolve_sensor_seed(sequence, config, sensor_seed)
    rng = np.random.default_rng(resolved_seed)
    points_per_frame = int(config.get("points_per_frame", default_points_per_frame(sequence.sequence_id)))
    all_points = []
    all_normals = []
    for frame_idx, pose in enumerate(sequence.gt_poses):
        scene = {
            "sequence": sequence,
            "frame_idx": frame_idx,
            "rng": rng,
            "points_per_frame": points_per_frame,
        }
        frame = simulate_frame_observations(pose, scene, {"point_noise_std_m": 0.0})
        all_points.append(frame["points_lidar"])
        all_normals.append(frame["normals_world"])
    return {
        "points_lidar": np.asarray(all_points),
        "normals_world": np.asarray(all_normals),
    }


def associate_points_to_planes(points: np.ndarray, planes: List[ObservationPlane]) -> np.ndarray:
    """Associate world points to nearest planes by absolute point-plane distance."""

    if not planes:
        raise ValueError("No planes available for association")
    distances = []
    for plane in planes:
        distances.append(np.abs((points - plane.point) @ plane.normal))
    return np.argmin(np.column_stack(distances), axis=1)


def compute_point_to_plane_jacobian(R: np.ndarray, p_lidar: np.ndarray, normal: np.ndarray) -> np.ndarray:
    """Compute J_i = [n^T (-R [p_i]_x), n^T] for the 6DoF pose block."""

    skew = skew_matrix(p_lidar)
    rotational = normal @ (-R @ skew)
    translational = normal
    return np.concatenate([rotational, translational])


def simulate_frame_observations(
    frame_pose: np.ndarray,
    scene: Dict[str, Any],
    sensor_config: Dict[str, Any],
) -> Dict[str, np.ndarray]:
    """Simulate one frame of point-to-plane residuals and Jacobians."""

    sequence: SequenceData = scene["sequence"]
    frame_idx = int(scene["frame_idx"])
    rng: np.random.Generator = scene["rng"]
    points_per_frame = int(scene["points_per_frame"])

    R = quat_to_rot(frame_pose[4:8])
    t = frame_pose[1:4]
    planes = frame_planes(sequence, frame_idx)
    points_world, normals_world, plane_points_world, plane_indices, points_lidar = sample_visible_points(
        R=R,
        t=t,
        planes=planes,
        points_per_frame=points_per_frame,
        rng=rng,
        sensor_config=sensor_config,
    )

    J = np.zeros((points_per_frame, 6), dtype=float)
    for idx, (point_lidar, normal) in enumerate(zip(points_lidar, normals_world)):
        J[idx] = compute_point_to_plane_jacobian(R, point_lidar, normal)

    point_noise_std = float(sensor_config.get("point_noise_std_m", 0.02))
    residuals = rng.normal(0.0, point_noise_std, size=points_per_frame)
    R_diag = np.full(points_per_frame, max(point_noise_std**2, 1.0e-6), dtype=float)

    return {
        "points_lidar": points_lidar,
        "points_world": points_world,
        "normals_world": normals_world,
        "plane_points_world": plane_points_world,
        "plane_indices": plane_indices,
        "J": J,
        "residuals": residuals,
        "R_diag": R_diag,
    }


def simulate_sequence_observations(
    sequence_dir: Union[str, Path],
    detector_config_path: Union[str, Path],
    sensor_seed: Optional[int] = None,
) -> Dict[str, np.ndarray]:
    sequence = load_sequence(sequence_dir)
    detector_config = load_detector_config(detector_config_path)
    resolved_seed = resolve_sensor_seed(sequence, detector_config, sensor_seed)
    rng = np.random.default_rng(resolved_seed)

    points_per_frame = int(detector_config.get("points_per_frame", default_points_per_frame(sequence.sequence_id)))
    point_noise_std = detector_config.get(
        "point_noise_std_m",
        sequence.sequence_config.get("sensor_stub", {}).get("point_noise_std_m", 0.02),
    )

    frames = sequence.gt_poses.shape[0]
    packed_J = np.zeros((frames, points_per_frame, 6), dtype=float)
    r_list = np.zeros((frames, points_per_frame), dtype=float)
    R_diag_list = np.zeros((frames, points_per_frame), dtype=float)
    normal_list = np.zeros((frames, points_per_frame, 3), dtype=float)
    point_list = np.zeros((frames, points_per_frame, 3), dtype=float)
    plane_point_list = np.zeros((frames, points_per_frame, 3), dtype=float)
    plane_index_list = np.zeros((frames, points_per_frame), dtype=np.int32)
    sensor_options = dict(detector_config.get("sensor", {}))
    sensor_options["point_noise_std_m"] = float(point_noise_std)

    for frame_idx, pose in enumerate(sequence.gt_poses):
        scene = {
            "sequence": sequence,
            "frame_idx": frame_idx,
            "rng": rng,
            "points_per_frame": points_per_frame,
        }
        frame = simulate_frame_observations(
            pose,
            scene,
            sensor_options,
        )
        packed_J[frame_idx] = frame["J"]
        r_list[frame_idx] = frame["residuals"]
        R_diag_list[frame_idx] = frame["R_diag"]
        normal_list[frame_idx] = frame["normals_world"]
        point_list[frame_idx] = frame["points_lidar"]
        plane_point_list[frame_idx] = frame["plane_points_world"]
        plane_index_list[frame_idx] = frame["plane_indices"]

    return {
        "timestamps": sequence.gt_poses[:, 0],
        "packed_J": packed_J,
        "r_list": r_list,
        "R_diag_list": R_diag_list,
        "num_points_per_frame": np.full(frames, points_per_frame, dtype=np.int32),
        "axis_per_frame": sequence.axis,
        "pose_gt": sequence.gt_poses,
        "normals_world": normal_list,
        "points_lidar": point_list,
        "plane_points_world": plane_point_list,
        "plane_indices": plane_index_list,
        "sensor_seed": np.asarray(resolved_seed, dtype=np.int64),
    }


def save_observations(observations: Dict[str, np.ndarray], output_path: Union[str, Path]) -> None:
    np.savez_compressed(output_path, **observations)


def frame_planes(sequence: SequenceData, frame_idx: int) -> List[ObservationPlane]:
    if sequence.metadata["scene_family"] == "CT":
        return curved_tunnel_local_planes(sequence, frame_idx)
    active = [plane for plane in sequence.static_planes if plane.frame_start <= frame_idx <= plane.frame_end]
    if not active:
        raise ValueError(f"No active plane patches for frame {frame_idx} in {sequence.sequence_id}")
    fraction = float(sequence.metadata.get("axial_support_fraction", 0.0))
    axial = [plane for plane in active if plane.is_axial_support]
    base = [plane for plane in active if not plane.is_axial_support]
    if fraction > 0.0 and axial and base:
        active = [replace(plane, sampling_weight=(1.0 - fraction) / len(base)) for plane in base]
        active.extend(replace(plane, sampling_weight=fraction / len(axial)) for plane in axial)
    return active


def curved_tunnel_local_planes(sequence: SequenceData, frame_idx: int) -> List[ObservationPlane]:
    """Construct CT local walls from axis.csv instead of fixed planes.csv normals."""

    tangent = normalize_vector(sequence.axis[frame_idx])
    side = np.array([-tangent[1], tangent[0], 0.0], dtype=float)
    side = normalize_vector(side)
    pose_t = sequence.gt_poses[frame_idx, 1:4]
    config = sequence.sequence_config
    width = float(config.get("scene", {}).get("width_m", 4.0))
    height = float(config.get("scene", {}).get("height_m", 3.0))
    center = pose_t.copy()
    floor_point = center.copy()
    floor_point[2] = 0.0
    ceiling_point = center.copy()
    ceiling_point[2] = height
    return [
        ObservationPlane("ct_local_left_wall", side, center + 0.5 * width * side, "left_wall"),
        ObservationPlane("ct_local_right_wall", -side, center - 0.5 * width * side, "right_wall"),
        ObservationPlane("ct_local_floor", np.array([0.0, 0.0, 1.0]), floor_point, "floor"),
        ObservationPlane("ct_local_ceiling", np.array([0.0, 0.0, -1.0]), ceiling_point, "ceiling"),
    ]


def sample_points_on_planes(
    pose_t: np.ndarray,
    planes: List[ObservationPlane],
    points_per_frame: int,
    rng: np.random.Generator,
) -> Tuple[np.ndarray, np.ndarray]:
    points, normals, _, _ = sample_points_on_plane_patches(pose_t, planes, points_per_frame, rng)
    return points, normals


def sample_points_on_plane_patches(
    pose_t: np.ndarray,
    planes: List[ObservationPlane],
    points_per_frame: int,
    rng: np.random.Generator,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    counts = deterministic_weighted_counts(points_per_frame, [plane.sampling_weight for plane in planes])
    points = []
    normals = []
    anchors = []
    indices = []
    for plane_index, (plane, count) in enumerate(zip(planes, counts)):
        u, v = plane.u_axis, plane.v_axis
        center = project_point_to_plane(pose_t, plane)
        center_u = float((center - plane.point) @ u)
        center_v = float((center - plane.point) @ v)
        low_u = max(-plane.half_u, center_u - min(3.0, plane.half_u))
        high_u = min(plane.half_u, center_u + min(3.0, plane.half_u))
        low_v = max(-plane.half_v, center_v - min(1.5, plane.half_v))
        high_v = min(plane.half_v, center_v + min(1.5, plane.half_v))
        if low_u >= high_u:
            low_u, high_u = -plane.half_u, plane.half_u
        if low_v >= high_v:
            low_v, high_v = -plane.half_v, plane.half_v
        for _ in range(count):
            offset_u = rng.uniform(low_u, high_u)
            offset_v = rng.uniform(low_v, high_v)
            point = plane.point + offset_u * u + offset_v * v
            points.append(point)
            normals.append(plane.normal)
            anchors.append(point.copy())
            indices.append(plane_index)
    return (
        np.asarray(points, dtype=float),
        np.asarray(normals, dtype=float),
        np.asarray(anchors, dtype=float),
        np.asarray(indices, dtype=np.int32),
    )


def sample_visible_points(
    R: np.ndarray,
    t: np.ndarray,
    planes: List[ObservationPlane],
    points_per_frame: int,
    rng: np.random.Generator,
    sensor_config: Dict[str, Any],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    accepted = []
    max_attempts = int(sensor_config.get("max_resample_attempts", 12))
    batch_size = max(points_per_frame, int(math.ceil(points_per_frame * 1.5)))
    for _ in range(max_attempts):
        world, normals, anchors, indices = sample_points_on_plane_patches(t, planes, batch_size, rng)
        lidar = (R.T @ (world - t).T).T
        mask = sensor_visibility_mask(lidar, sensor_config)
        dropout = float(sensor_config.get("dropout_probability", 0.0))
        if not 0.0 <= dropout < 1.0:
            raise ValueError("dropout_probability must be in [0, 1)")
        if dropout > 0.0:
            mask &= rng.random(mask.shape[0]) >= dropout
        visible_indices = np.flatnonzero(mask)
        if visible_indices.size:
            visible_indices = rng.permutation(visible_indices)
        for candidate_index in visible_indices:
            item = (
                world[candidate_index],
                normals[candidate_index],
                anchors[candidate_index],
                indices[candidate_index],
                lidar[candidate_index],
            )
            accepted.append(item)
            if len(accepted) == points_per_frame:
                arrays = [np.asarray(values) for values in zip(*accepted)]
                arrays[3] = arrays[3].astype(np.int32)
                return tuple(arrays)  # type: ignore[return-value]
    raise RuntimeError(
        f"Could not collect {points_per_frame} visible points after {max_attempts} attempts; collected {len(accepted)}"
    )


def sensor_visibility_mask(points_lidar: np.ndarray, config: Dict[str, Any]) -> np.ndarray:
    ranges = np.linalg.norm(points_lidar, axis=1)
    horizontal = np.degrees(np.arctan2(points_lidar[:, 1], points_lidar[:, 0]))
    vertical = np.degrees(np.arctan2(points_lidar[:, 2], np.linalg.norm(points_lidar[:, :2], axis=1)))
    min_range = float(config.get("min_range_m", 0.0))
    max_range = float(config.get("max_range_m", float("inf")))
    hfov = float(config.get("horizontal_fov_deg", 360.0))
    mask = (ranges >= min_range) & (ranges <= max_range)
    if hfov < 360.0:
        mask &= np.abs(horizontal) <= 0.5 * hfov
    mask &= vertical >= float(config.get("vertical_fov_min_deg", -90.0))
    mask &= vertical <= float(config.get("vertical_fov_max_deg", 90.0))
    return mask


def deterministic_weighted_counts(total: int, weights: List[float]) -> List[int]:
    if total < 0 or not weights:
        raise ValueError("total must be non-negative and weights must be non-empty")
    values = np.asarray(weights, dtype=float)
    if np.any(values < 0.0) or float(np.sum(values)) <= 0.0:
        raise ValueError("sampling weights must be non-negative with positive sum")
    exact = total * values / float(np.sum(values))
    counts = np.floor(exact).astype(int)
    remainder = total - int(np.sum(counts))
    order = np.argsort(-(exact - counts), kind="stable")
    counts[order[:remainder]] += 1
    return counts.tolist()


def distribute_counts(total: int, bins: int) -> List[int]:
    return deterministic_weighted_counts(total, [1.0] * bins)


def resolve_sensor_seed(sequence: SequenceData, config: Dict[str, Any], explicit: Optional[int]) -> int:
    if explicit is not None:
        return int(explicit)
    if "sensor_seed" in config:
        return int(config["sensor_seed"])
    return int(config.get("random_seed", sequence.metadata["random_seed"]))


def plane_basis(normal: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    n = normalize_vector(normal)
    candidate = np.array([0.0, 0.0, 1.0])
    if abs(float(n @ candidate)) > 0.9:
        candidate = np.array([1.0, 0.0, 0.0])
    u = normalize_vector(np.cross(n, candidate))
    v = normalize_vector(np.cross(n, u))
    return u, v


def project_point_to_plane(point: np.ndarray, plane: ObservationPlane) -> np.ndarray:
    distance = (point - plane.point) @ plane.normal
    return point - distance * plane.normal


def default_points_per_frame(sequence_id: str) -> int:
    if sequence_id.startswith("OC"):
        return 360
    if sequence_id.startswith("RT"):
        return 464
    return 320


def quat_to_rot(qxyzw: np.ndarray) -> np.ndarray:
    x, y, z, w = [float(v) for v in qxyzw]
    norm = math.sqrt(x * x + y * y + z * z + w * w)
    if norm == 0:
        raise ValueError("Invalid zero quaternion")
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=float,
    )


def skew_matrix(p: np.ndarray) -> np.ndarray:
    x, y, z = [float(v) for v in p]
    return np.array(
        [
            [0.0, -z, y],
            [z, 0.0, -x],
            [-y, x, 0.0],
        ],
        dtype=float,
    )


def normalize_vector(values: Union[np.ndarray, List[float]]) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    norm = np.linalg.norm(vector)
    if norm < 1.0e-12:
        raise ValueError("Cannot normalize zero-length vector")
    return vector / norm


def normalize_rows(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.maximum(norms, 1.0e-12)


def information_matrix(J: np.ndarray, R_diag: np.ndarray) -> np.ndarray:
    weighted = J / R_diag[:, None]
    return J.T @ weighted


def translational_information_diag(J: np.ndarray, R_diag: np.ndarray) -> np.ndarray:
    H = information_matrix(J, R_diag)
    return np.diag(H[3:6, 3:6])
