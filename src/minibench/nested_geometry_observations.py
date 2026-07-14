"""Strictly nested, additive observations for geometry detector sweeps."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import numpy as np

from .observation_simulator import (
    compute_point_to_plane_jacobian,
    load_detector_config,
    load_sequence,
    quat_to_rot,
    sensor_visibility_mask,
)


def stable_measurement_seed(
    geometry_seed: int,
    sensor_seed: int,
    frame_index: int,
    patch_id: str,
    local_candidate_index: int,
) -> int:
    payload = (
        f"geometry|{int(geometry_seed)}|{int(sensor_seed)}|{int(frame_index)}|"
        f"{patch_id}|{int(local_candidate_index)}"
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def stable_measurement_id(
    geometry_seed: int,
    sensor_seed: int,
    frame_index: int,
    patch_id: str,
    local_candidate_index: int,
) -> int:
    return stable_measurement_seed(
        geometry_seed,
        sensor_seed,
        frame_index,
        patch_id,
        local_candidate_index,
    ) & ((1 << 63) - 1)


def points_for_patch(area: float, density: float, minimum: int) -> int:
    if density <= 0.0 or minimum < 1:
        raise ValueError("geometry density and minimum points must be positive")
    return max(int(minimum), int(round(float(density) * float(area))))


def simulate_nested_geometry_observations(
    sequence_dir: Path,
    detector_config_path: Path,
    geometry_seed: int,
    sensor_seed: int,
    points_per_square_meter: float,
    min_points_per_patch: int,
) -> Dict[str, np.ndarray]:
    """Generate level-independent candidates for every active finite patch."""

    sequence = load_sequence(sequence_dir)
    detector = load_detector_config(detector_config_path)
    sensor = dict(detector.get("sensor", {}))
    point_noise_std = float(detector.get("point_noise_std_m", 0.02))
    dropout_probability = float(sensor.get("dropout_probability", 0.0))
    if not 0.0 <= dropout_probability < 1.0:
        raise ValueError("dropout_probability must be in [0, 1)")

    frame_records = []
    for frame_index, pose in enumerate(sequence.gt_poses):
        rotation = quat_to_rot(pose[4:8])
        translation = pose[1:4]
        records = []
        for plane in sequence.static_planes:
            if not plane.frame_start <= frame_index <= plane.frame_end:
                continue
            count = points_for_patch(
                4.0 * float(plane.half_u) * float(plane.half_v),
                float(points_per_square_meter),
                int(min_points_per_patch),
            )
            for local_index in range(count):
                seed = stable_measurement_seed(
                    geometry_seed,
                    sensor_seed,
                    frame_index,
                    plane.plane_id,
                    local_index,
                )
                rng = np.random.default_rng(seed)
                point_world = (
                    plane.point
                    + rng.uniform(-plane.half_u, plane.half_u) * plane.u_axis
                    + rng.uniform(-plane.half_v, plane.half_v) * plane.v_axis
                )
                point_lidar = rotation.T @ (point_world - translation)
                visible = bool(sensor_visibility_mask(point_lidar.reshape(1, 3), sensor)[0])
                retained = visible and bool(rng.random() >= dropout_probability)
                measurement_noise = float(rng.normal(0.0, point_noise_std))
                if not retained:
                    continue
                measurement_id = stable_measurement_id(
                    geometry_seed,
                    sensor_seed,
                    frame_index,
                    plane.plane_id,
                    local_index,
                )
                records.append(
                    (
                        measurement_id,
                        plane.plane_id,
                        point_lidar,
                        plane.normal.copy(),
                        point_world,
                        measurement_noise,
                        bool(plane.is_axial_support),
                        compute_point_to_plane_jacobian(rotation, point_lidar, plane.normal),
                    )
                )
        records.sort(key=lambda item: item[0])
        if not records:
            raise RuntimeError(f"no nested geometry measurements survived frame {frame_index}")
        frame_records.append(records)

    counts = {len(records) for records in frame_records}
    if len(counts) != 1:
        raise RuntimeError(
            "nested geometry frame counts differ; use a full-FOV, zero-dropout detector configuration"
        )
    frames = len(frame_records)
    count = counts.pop()
    measurement_ids = np.zeros((frames, count), dtype=np.int64)
    patch_ids = np.empty((frames, count), dtype="U64")
    points_lidar = np.zeros((frames, count, 3), dtype=float)
    normals = np.zeros((frames, count, 3), dtype=float)
    points_world = np.zeros((frames, count, 3), dtype=float)
    residuals = np.zeros((frames, count), dtype=float)
    axial = np.zeros((frames, count), dtype=bool)
    packed_j = np.zeros((frames, count, 6), dtype=float)
    for frame_index, records in enumerate(frame_records):
        for index, record in enumerate(records):
            measurement_ids[frame_index, index] = record[0]
            patch_ids[frame_index, index] = record[1]
            points_lidar[frame_index, index] = record[2]
            normals[frame_index, index] = record[3]
            points_world[frame_index, index] = record[4]
            residuals[frame_index, index] = record[5]
            axial[frame_index, index] = record[6]
            packed_j[frame_index, index] = record[7]
    variance = max(point_noise_std**2, 1.0e-6)
    r_diag = np.full((frames, count), variance, dtype=float)
    raw_information = np.asarray(
        [packed_j[index].T @ (packed_j[index] / r_diag[index, :, None]) for index in range(frames)]
    )
    shell_ids = measurement_ids[~axial]
    axial_ids = measurement_ids[axial]
    return {
        "timestamps": sequence.gt_poses[:, 0],
        "packed_J": packed_j,
        "r_list": residuals,
        "R_diag_list": r_diag,
        "num_points_per_frame": np.full(frames, count, dtype=np.int32),
        "axis_per_frame": sequence.axis,
        "pose_gt": sequence.gt_poses,
        "normals_world": normals,
        "points_lidar": points_lidar,
        "plane_points_world": points_world,
        "is_axial_support": axial,
        "measurement_ids": measurement_ids,
        "measurement_patch_ids": patch_ids,
        "measurement_noise": residuals.copy(),
        "shell_measurement_ids": shell_ids,
        "axial_measurement_ids": axial_ids,
        "measurement_set_checksum": np.asarray(array_checksum(measurement_ids)),
        "shell_measurement_checksum": np.asarray(array_checksum(shell_ids)),
        "axial_measurement_checksum": np.asarray(array_checksum(axial_ids)),
        "raw_information_matrices": raw_information,
        "sensor_seed": np.asarray(int(sensor_seed), dtype=np.int64),
        "geometry_seed": np.asarray(int(geometry_seed), dtype=np.int64),
    }


def audit_nested_geometry_levels(
    level_observations: Mapping[str, Mapping[str, np.ndarray]],
    levels: Sequence[str] = ("L1", "L2", "L3", "L4"),
    tolerance: float = 1.0e-8,
) -> Dict[str, Any]:
    """Audit strict ID subsets, shared measurements, and additive PSD increments."""

    if any(level not in level_observations for level in levels):
        raise ValueError("all geometry levels are required for nested audit")
    subset_valid = True
    shared_values_valid = True
    delta_minima = []
    pair_rows = []
    for stronger, weaker in zip(levels[:-1], levels[1:]):
        high = level_observations[stronger]
        low = level_observations[weaker]
        for frame_index in range(high["measurement_ids"].shape[0]):
            high_ids = np.asarray(high["measurement_ids"][frame_index], dtype=np.int64)
            low_ids = np.asarray(low["measurement_ids"][frame_index], dtype=np.int64)
            strict_subset = set(low_ids.tolist()) < set(high_ids.tolist())
            subset_valid &= strict_subset
            high_index = {int(value): index for index, value in enumerate(high_ids)}
            for low_index, measurement_id in enumerate(low_ids):
                index = high_index.get(int(measurement_id))
                if index is None:
                    shared_values_valid = False
                    continue
                for field in ["points_lidar", "normals_world", "measurement_noise"]:
                    shared_values_valid &= bool(
                        np.array_equal(
                            np.asarray(high[field][frame_index, index]),
                            np.asarray(low[field][frame_index, low_index]),
                        )
                    )
            delta = np.asarray(high["raw_information_matrices"][frame_index]) - np.asarray(
                low["raw_information_matrices"][frame_index]
            )
            minimum = float(np.min(np.linalg.eigvalsh(0.5 * (delta + delta.T))))
            delta_minima.append(minimum)
            pair_rows.append(
                {
                    "parent_level": stronger,
                    "child_level": weaker,
                    "frame_index": frame_index,
                    "parent_measurement_subset_valid": strict_subset,
                    "delta_H_min_eigenvalue": minimum,
                    "psd_increment_valid": bool(minimum >= -float(tolerance)),
                }
            )
    return {
        "measurement_sets_strictly_nested": bool(subset_valid),
        "shared_measurements_identical": bool(shared_values_valid),
        "delta_H_min_eigenvalue": min(delta_minima) if delta_minima else float("nan"),
        "psd_increment_valid": bool(delta_minima and min(delta_minima) >= -float(tolerance)),
        "pair_rows": pair_rows,
    }


def array_checksum(values: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(values))
    digest = hashlib.sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(str(array.shape).encode("ascii"))
    digest.update(array.tobytes())
    return digest.hexdigest()
