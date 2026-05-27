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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import numpy as np
import yaml


@dataclass
class ObservationPlane:
    plane_id: str
    normal: np.ndarray
    point: np.ndarray
    semantic: str


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
    config_path = metadata.get("config_path")
    if not config_path:
        return {}
    path = Path(config_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    return config if isinstance(config, dict) else {}


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
            planes.append(
                ObservationPlane(
                    plane_id=row["plane_id"],
                    normal=normalize_vector([float(row["nx"]), float(row["ny"]), float(row["nz"])]),
                    point=np.array([float(row["qx"]), float(row["qy"]), float(row["qz"])], dtype=float),
                    semantic=row["semantic"],
                )
            )
    return planes


def simulate_lidar_points(sequence: SequenceData, config: Dict[str, Any]) -> Dict[str, np.ndarray]:
    """Generate framewise synthetic LiDAR points and associated plane normals."""

    rng = np.random.default_rng(int(sequence.metadata["random_seed"]))
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

    points_world, normals_world = sample_points_on_planes(
        pose_t=t,
        planes=planes,
        points_per_frame=points_per_frame,
        rng=rng,
    )
    points_lidar = (R.T @ (points_world - t).T).T

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
        "J": J,
        "residuals": residuals,
        "R_diag": R_diag,
    }


def simulate_sequence_observations(
    sequence_dir: Union[str, Path],
    detector_config_path: Union[str, Path],
) -> Dict[str, np.ndarray]:
    sequence = load_sequence(sequence_dir)
    detector_config = load_detector_config(detector_config_path)
    rng = np.random.default_rng(int(detector_config.get("random_seed", sequence.metadata["random_seed"])))

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
            {"point_noise_std_m": float(point_noise_std)},
        )
        packed_J[frame_idx] = frame["J"]
        r_list[frame_idx] = frame["residuals"]
        R_diag_list[frame_idx] = frame["R_diag"]
        normal_list[frame_idx] = frame["normals_world"]
        point_list[frame_idx] = frame["points_lidar"]

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
    }


def save_observations(observations: Dict[str, np.ndarray], output_path: Union[str, Path]) -> None:
    np.savez_compressed(output_path, **observations)


def frame_planes(sequence: SequenceData, frame_idx: int) -> List[ObservationPlane]:
    if sequence.metadata["scene_family"] == "CT":
        return curved_tunnel_local_planes(sequence, frame_idx)
    return sequence.static_planes


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
    counts = distribute_counts(points_per_frame, len(planes))
    points = []
    normals = []
    for plane, count in zip(planes, counts):
        u, v = plane_basis(plane.normal)
        center = project_point_to_plane(pose_t, plane)
        for _ in range(count):
            # Offsets are symmetric in-plane only. The sampled world point stays
            # on the matched plane; residual noise is added separately.
            offset_u = rng.uniform(-3.0, 3.0)
            offset_v = rng.uniform(-1.5, 1.5)
            points.append(center + offset_u * u + offset_v * v)
            normals.append(plane.normal)
    return np.asarray(points, dtype=float), np.asarray(normals, dtype=float)


def distribute_counts(total: int, bins: int) -> List[int]:
    base = total // bins
    counts = [base] * bins
    for idx in range(total - base * bins):
        counts[idx] += 1
    return counts


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
