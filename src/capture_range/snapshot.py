"""Deterministic, tiny scan/map snapshots for the Day 1 smoke pipeline.

The builders in this module create geometry only.  No reference weak axis or
ground-truth label is attached to a snapshot, and registration receives only
the fixed scan, map, initial pose, and frozen registration configuration.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import numpy as np

from .types import RegistrationSnapshot


SMOKE_SCENES = ("geometry_rich_box", "parallel_walls", "long_corridor")


def array_checksum(values: np.ndarray) -> str:
    """Return a stable checksum that includes dtype and shape."""

    array = np.ascontiguousarray(np.asarray(values))
    digest = hashlib.sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(json.dumps(array.shape).encode("ascii"))
    digest.update(array.tobytes())
    return digest.hexdigest()


def config_checksum(config: Mapping[str, Any]) -> str:
    payload = json.dumps(_jsonable(config), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def snapshot_checksums(snapshot: RegistrationSnapshot) -> dict[str, str]:
    return {
        "scan_checksum": array_checksum(snapshot.scan_points),
        "map_checksum": array_checksum(snapshot.local_map_points),
        "reference_pose_checksum": array_checksum(snapshot.reference_pose),
        "config_checksum": config_checksum(snapshot.registration_config),
    }


def build_smoke_snapshots(protocol: Mapping[str, Any]) -> tuple[RegistrationSnapshot, ...]:
    """Build the three protocol-frozen Day 1 geometry snapshots."""

    registration_config = {
        "registration": _jsonable(protocol["registration"]),
        "success": _jsonable(protocol["success"]),
        "randomness": _jsonable(protocol["randomness"]),
    }
    # Repository-native TUM row: timestamp, translation, xyzw quaternion.
    reference_pose = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], dtype=float)
    builders = {
        "geometry_rich_box": _geometry_rich_box,
        "parallel_walls": _parallel_walls,
        "long_corridor": _long_corridor,
    }
    snapshots = []
    for scene_name in SMOKE_SCENES:
        scan, local_map = builders[scene_name]()
        snapshots.append(
            RegistrationSnapshot(
                snapshot_id=f"day1_{scene_name}",
                scan_points=scan,
                local_map_points=local_map,
                reference_pose=reference_pose,
                registration_config=registration_config,
                metadata={
                    "scene_name": scene_name,
                    "purpose": "directional_capture_range_engineering_smoke_only",
                    "algorithm_conditioned": True,
                },
            )
        )
    return tuple(snapshots)


def _geometry_rich_box() -> tuple[np.ndarray, np.ndarray]:
    # Dense map faces and inset scan samples avoid edge-driven plane ambiguity.
    map_points = np.vstack(
        [
            _plane_points(0, side * 2.0, _grid(-2.0, 2.0, 0.4), _grid(-1.6, 1.6, 0.4))
            for side in (-1.0, 1.0)
        ]
        + [
            _plane_points(1, side * 2.0, _grid(-2.0, 2.0, 0.4), _grid(-1.6, 1.6, 0.4))
            for side in (-1.0, 1.0)
        ]
        + [
            _plane_points(2, side * 1.6, _grid(-2.0, 2.0, 0.4), _grid(-2.0, 2.0, 0.4))
            for side in (-1.0, 1.0)
        ]
    )
    scan_points = np.vstack(
        [
            _plane_points(0, side * 2.0, _grid(-1.0, 1.0, 0.5), _grid(-0.75, 0.75, 0.5))
            for side in (-1.0, 1.0)
        ]
        + [
            _plane_points(1, side * 2.0, _grid(-1.0, 1.0, 0.5), _grid(-0.75, 0.75, 0.5))
            for side in (-1.0, 1.0)
        ]
        + [
            _plane_points(2, side * 1.6, _grid(-1.0, 1.0, 0.5), _grid(-1.0, 1.0, 0.5))
            for side in (-1.0, 1.0)
        ]
    )
    return scan_points, _unique_rows(map_points)


def _parallel_walls() -> tuple[np.ndarray, np.ndarray]:
    map_points = np.vstack(
        [
            _plane_points(1, side * 2.0, _grid(-6.0, 6.0, 0.4), _grid(-1.6, 1.6, 0.4))
            for side in (-1.0, 1.0)
        ]
    )
    scan_points = np.vstack(
        [
            _plane_points(1, side * 2.0, _grid(-1.5, 1.5, 0.5), _grid(-0.75, 0.75, 0.5))
            for side in (-1.0, 1.0)
        ]
    )
    return scan_points, _unique_rows(map_points)


def _long_corridor() -> tuple[np.ndarray, np.ndarray]:
    wall_map = [
        _plane_points(1, side * 2.0, _grid(-6.0, 6.0, 0.4), _grid(-1.6, 1.6, 0.4))
        for side in (-1.0, 1.0)
    ]
    floor_map = [
        _plane_points(2, side * 1.6, _grid(-6.0, 6.0, 0.4), _grid(-2.0, 2.0, 0.4))
        for side in (-1.0, 1.0)
    ]
    wall_scan = [
        _plane_points(1, side * 2.0, _grid(-1.5, 1.5, 0.5), _grid(-0.75, 0.75, 0.5))
        for side in (-1.0, 1.0)
    ]
    floor_scan = [
        _plane_points(2, side * 1.6, _grid(-1.5, 1.5, 0.5), _grid(-1.0, 1.0, 0.5))
        for side in (-1.0, 1.0)
    ]
    return np.vstack(wall_scan + floor_scan), _unique_rows(np.vstack(wall_map + floor_map))


def _plane_points(axis: int, value: float, first: np.ndarray, second: np.ndarray) -> np.ndarray:
    a, b = np.meshgrid(first, second, indexing="ij")
    points = np.empty((a.size, 3), dtype=float)
    other_axes = [index for index in range(3) if index != axis]
    points[:, axis] = value
    points[:, other_axes[0]] = a.ravel()
    points[:, other_axes[1]] = b.ravel()
    return points


def _grid(start: float, stop: float, step: float) -> np.ndarray:
    count = int(round((stop - start) / step))
    return np.linspace(start, stop, count + 1, dtype=float)


def _unique_rows(values: np.ndarray) -> np.ndarray:
    return np.unique(np.asarray(values, dtype=float), axis=0)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value
