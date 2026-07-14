"""Deterministic, method-independent correspondence stress for Stage 2B."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Mapping

import numpy as np


def apply_correspondence_stress(
    observations: Mapping[str, np.ndarray],
    stress_name: str,
    stress_config: Mapping[str, Any],
    experiment_family: str,
    geometry_seed: int,
    sensor_seed: int,
    patch_ids: np.ndarray,
) -> Dict[str, np.ndarray]:
    output = {key: np.asarray(value).copy() for key, value in observations.items()}
    points = np.asarray(output["plane_points_world"], dtype=float)
    normals = np.asarray(output["normals_world"], dtype=float)
    axial = np.asarray(output["is_axial_support"], dtype=bool)
    patches = np.asarray(patch_ids).astype(str)
    if patches.shape != axial.shape:
        raise ValueError("patch_ids must match is_axial_support")
    mask = np.zeros_like(axial, dtype=bool)
    offsets = np.zeros_like(axial, dtype=float)
    selected: list[str] = []
    burst_starts: list[int] = []
    burst_signs: list[int] = []
    if stress_name != "clean":
        config = stress_config["stress_regimes"][stress_name]
        if not bool(config["enabled"]):
            raise ValueError("requested stress regime is disabled")
        fraction = float(config["corrupted_axial_patch_fraction"])
        burst = int(config["burst_length_frames"])
        distance = float(config["slip_distance_m"])
        unique = sorted(set(patches[axial].tolist()))
        count = int(np.ceil(fraction * len(unique))) if unique else 0
        ranked = sorted(unique, key=lambda patch: _digest(experiment_family, geometry_seed, sensor_seed, patch, "rank"))
        selected = ranked[:count]
        for patch in selected:
            maximum_start = max(points.shape[0] - burst, 0)
            start = _digest(experiment_family, geometry_seed, sensor_seed, patch, "start") % (maximum_start + 1)
            sign = -1.0 if _digest(experiment_family, geometry_seed, sensor_seed, patch, "sign") % 2 else 1.0
            burst_starts.append(int(start))
            burst_signs.append(int(sign))
            patch_mask = (patches == patch) & axial
            frame_mask = np.zeros(points.shape[0], dtype=bool)
            frame_mask[start : start + burst] = True
            active = patch_mask & frame_mask[:, None]
            mask |= active
            offsets[active] = sign * distance
            points[active] = points[active] + sign * distance * normals[active]
    output["plane_points_world"] = points
    output["contamination_mask"] = mask
    output["contamination_offset_m"] = offsets
    output["contaminated_patch_ids"] = np.asarray(selected, dtype="U64")
    output["contaminated_patch_burst_start_frames"] = np.asarray(burst_starts, dtype=np.int32)
    output["contaminated_patch_burst_signs"] = np.asarray(burst_signs, dtype=np.int8)
    output["stress_name"] = np.asarray(stress_name)
    output["stress_checksum"] = np.asarray(
        stress_checksum(mask, offsets, selected, burst_starts, burst_signs)
    )
    return output


def stress_checksum(
    mask: np.ndarray,
    offsets: np.ndarray,
    selected: list[str],
    burst_starts: list[int],
    burst_signs: list[int],
) -> str:
    digest = hashlib.sha256()
    digest.update(np.ascontiguousarray(mask).tobytes())
    digest.update(np.ascontiguousarray(offsets).tobytes())
    digest.update("\0".join(selected).encode("utf-8"))
    digest.update(np.asarray(burst_starts, dtype=np.int32).tobytes())
    digest.update(np.asarray(burst_signs, dtype=np.int8).tobytes())
    return digest.hexdigest()


def _digest(experiment_family: str, geometry_seed: int, sensor_seed: int, patch_id: str, purpose: str) -> int:
    payload = f"{experiment_family}|{int(geometry_seed)}|{int(sensor_seed)}|{patch_id}|{purpose}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
