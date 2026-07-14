"""Deterministic coherent correspondence stress for directional gain studies."""

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
    variances = np.asarray(output["R_diag_list"], dtype=float)
    axial = np.asarray(output["is_axial_support"], dtype=bool)
    patches = np.asarray(patch_ids).astype(str)
    if patches.shape != axial.shape:
        raise ValueError("patch_ids must match is_axial_support")
    if stress_name not in stress_config["stress_regimes"]:
        raise ValueError(f"unknown stress regime: {stress_name}")

    mask = np.zeros_like(axial, dtype=bool)
    offsets = np.zeros_like(variances, dtype=float)
    selected: list[str] = []
    burst_start = -1
    burst_sign = 0
    slip_sigma = 0.0
    nominal_sigma = float(np.median(np.sqrt(variances[axial]))) if np.any(axial) else 0.0
    injected_distance = 0.0
    regime = stress_config["stress_regimes"][stress_name]
    if bool(regime["enabled"]) and np.any(axial):
        slip_sigma = float(regime["slip_sigma"])
        injected_distance = slip_sigma * nominal_sigma
        fraction = float(regime["corrupted_axial_patch_fraction"])
        burst_length = int(regime["burst_length_frames"])
        unique = sorted(set(patches[axial].tolist()))
        count = min(len(unique), int(np.ceil(fraction * len(unique))))
        ranked = sorted(
            unique,
            key=lambda patch: _digest(
                experiment_family, geometry_seed, sensor_seed, stress_name, "patch", patch
            ),
        )
        selected = ranked[:count]
        maximum_start = max(points.shape[0] - burst_length, 0)
        burst_start = _digest(
            experiment_family, geometry_seed, sensor_seed, stress_name, "burst_start"
        ) % (maximum_start + 1)
        burst_sign = -1 if _digest(
            experiment_family, geometry_seed, sensor_seed, stress_name, "burst_sign"
        ) % 2 else 1
        frame_mask = np.zeros(points.shape[0], dtype=bool)
        frame_mask[burst_start : burst_start + burst_length] = True
        selected_mask = np.isin(patches, selected) & axial
        mask = selected_mask & frame_mask[:, None]
        offsets[mask] = float(burst_sign) * injected_distance
        points[mask] = points[mask] + offsets[mask, None] * normals[mask]

    output["plane_points_world"] = points
    output["contamination_mask"] = mask
    output["contamination_offset_m"] = offsets
    output["selected_axial_patch_ids"] = np.asarray(selected, dtype="U64")
    output["stress_name"] = np.asarray(stress_name)
    output["shared_burst_start_frame"] = np.asarray(burst_start, dtype=np.int32)
    output["shared_burst_sign"] = np.asarray(burst_sign, dtype=np.int8)
    output["nominal_measurement_sigma_m"] = np.asarray(nominal_sigma, dtype=float)
    output["injected_slip_distance_m"] = np.asarray(injected_distance, dtype=float)
    output["injected_slip_sigma"] = np.asarray(slip_sigma, dtype=float)
    output["contaminated_measurement_ratio"] = np.asarray(float(np.mean(mask)), dtype=float)
    output["stress_checksum"] = np.asarray(stress_checksum(
        mask, offsets, selected, stress_name, burst_start, burst_sign,
        nominal_sigma, injected_distance, slip_sigma,
    ))
    return output


def stress_checksum(
    mask: np.ndarray,
    offsets: np.ndarray,
    selected: list[str],
    stress_name: str,
    burst_start: int,
    burst_sign: int,
    nominal_sigma: float,
    injected_distance: float,
    slip_sigma: float,
) -> str:
    digest = hashlib.sha256()
    digest.update(np.ascontiguousarray(mask).tobytes())
    digest.update(np.ascontiguousarray(offsets).tobytes())
    digest.update("\0".join(selected).encode("utf-8"))
    digest.update(str(stress_name).encode("utf-8"))
    digest.update(np.asarray([burst_start, burst_sign], dtype=np.int64).tobytes())
    digest.update(np.asarray([nominal_sigma, injected_distance, slip_sigma], dtype=float).tobytes())
    return digest.hexdigest()


def _digest(
    experiment_family: str,
    geometry_seed: int,
    sensor_seed: int,
    stress_name: str,
    purpose: str,
    patch_id: str = "",
) -> int:
    payload = (
        f"{experiment_family}|{int(geometry_seed)}|{int(sensor_seed)}|"
        f"{stress_name}|{purpose}|{patch_id}"
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
