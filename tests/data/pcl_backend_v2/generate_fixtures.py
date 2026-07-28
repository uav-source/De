#!/usr/bin/env python3
"""Generate the deterministic, seed-free PCL backend qualification v2 fixtures."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARAMETERS = {
    "normal_estimation": {"method": "KSearch", "k": 50},
    "icp": {
        "maximum_correspondence_distance_m": 0.50,
        "maximum_iterations": 50,
        "transformation_epsilon": 1.0e-10,
        "euclidean_fitness_epsilon": 1.0e-10,
        "use_reciprocal_correspondences": False,
        "use_symmetric_objective": False,
        "enforce_same_direction_normals": True,
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def axis_values(start: float, stop: float, count: int) -> list[float]:
    return [float(value) for value in np.linspace(start, stop, count)]


def add_surface(
    samples: dict[tuple[float, float, float], list[np.ndarray]],
    points: list[tuple[float, float, float]],
    normal: tuple[float, float, float],
) -> None:
    unit = np.asarray(normal, dtype=np.float64)
    unit /= np.linalg.norm(unit)
    for point in points:
        key = tuple(round(float(value), 9) for value in point)
        samples.setdefault(key, []).append(unit)


def build_geometry() -> tuple[np.ndarray, np.ndarray]:
    samples: dict[tuple[float, float, float], list[np.ndarray]] = {}
    grid = axis_values(-1.0, 1.0, 13)

    add_surface(samples, [(0.0, y, z) for y in grid for z in grid], (1.0, 0.0, 0.0))
    add_surface(samples, [(x, 0.0, z) for x in grid for z in grid], (0.0, 1.0, 0.0))
    add_surface(samples, [(x, y, 0.0) for x in grid for y in grid], (0.0, 0.0, 1.0))

    # Five exposed faces of an off-centre cuboid protruding from z=0.
    x_min, x_max = 0.19, 0.55
    y_min, y_max = -0.44, -0.18
    z_min, z_max = 0.0, 0.36
    xs = axis_values(x_min, x_max, 9)
    ys = axis_values(y_min, y_max, 9)
    zs = axis_values(z_min, z_max, 9)
    add_surface(samples, [(x, y, z_max) for x in xs for y in ys], (0.0, 0.0, 1.0))
    add_surface(samples, [(x_min, y, z) for y in ys for z in zs], (-1.0, 0.0, 0.0))
    add_surface(samples, [(x_max, y, z) for y in ys for z in zs], (1.0, 0.0, 0.0))
    add_surface(samples, [(x, y_min, z) for x in xs for z in zs], (0.0, -1.0, 0.0))
    add_surface(samples, [(x, y_max, z) for x in xs for z in zs], (0.0, 1.0, 0.0))

    keys = sorted(samples)
    points = np.asarray(keys, dtype=np.float64)
    normals = []
    for key in keys:
        value = np.sum(samples[key], axis=0)
        normals.append(value / np.linalg.norm(value))
    return points, np.asarray(normals, dtype=np.float64)


def write_ascii_pcd(path: Path, points: np.ndarray) -> None:
    lines = [
        "# .PCD v0.7 - Point Cloud Data file format",
        "VERSION 0.7",
        "FIELDS x y z",
        "SIZE 4 4 4",
        "TYPE F F F",
        "COUNT 1 1 1",
        f"WIDTH {len(points)}",
        "HEIGHT 1",
        "VIEWPOINT 0 0 0 1 0 0 0",
        f"POINTS {len(points)}",
        "DATA ascii",
    ]
    lines.extend(" ".join(f"{float(value):.9f}" for value in point) for point in points)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def matrix_rank_and_eigenvalues(matrix: np.ndarray) -> tuple[int, list[float], float]:
    eigenvalues = np.linalg.eigvalsh(matrix)
    tolerance = float(
        max(matrix.shape) * np.finfo(np.float64).eps * max(1.0, float(eigenvalues[-1]))
    )
    return int(np.sum(eigenvalues > tolerance)), eigenvalues.tolist(), tolerance


def geometry_diagnostics(points: np.ndarray, normals: np.ndarray) -> dict[str, object]:
    centered = points - np.mean(points, axis=0)
    covariance = centered.T @ centered / len(points)
    cloud_rank, covariance_eigenvalues, cloud_tolerance = matrix_rank_and_eigenvalues(
        covariance
    )
    jacobian = np.column_stack((np.cross(points, normals), normals))
    hessian = jacobian.T @ jacobian
    hessian_rank, hessian_eigenvalues, hessian_tolerance = matrix_rank_and_eigenvalues(
        hessian
    )
    normal_gram = normals.T @ normals
    normal_rank, normal_eigenvalues, normal_tolerance = matrix_rank_and_eigenvalues(
        normal_gram
    )
    return {
        "point_count": int(len(points)),
        "finite_point_count": int(np.all(np.isfinite(points), axis=1).sum()),
        "unique_point_count": int(len(np.unique(points, axis=0))),
        "point_cloud_rank": cloud_rank,
        "point_cloud_covariance_eigenvalues": covariance_eigenvalues,
        "point_cloud_rank_tolerance": cloud_tolerance,
        "analytic_surface_normal_direction_rank": normal_rank,
        "analytic_surface_normal_gram_eigenvalues": normal_eigenvalues,
        "analytic_surface_normal_rank_tolerance": normal_tolerance,
        "analytic_point_to_plane_jacobian_rank": hessian_rank,
        "analytic_point_to_plane_hessian_eigenvalues": hessian_eigenvalues,
        "analytic_point_to_plane_rank_tolerance": hessian_tolerance,
        "rank_deficient": hessian_rank < 6,
        "surface_construction": {
            "mutually_perpendicular_planes": 3,
            "off_centre_cuboid_exposed_faces": 5,
            "random_seed_used": False,
        },
    }


def rpy_matrix_degrees(roll: float, pitch: float, yaw: float) -> np.ndarray:
    rx, ry, rz = [math.radians(value) for value in (roll, pitch, yaw)]
    rotation_x = np.array(
        [[1.0, 0.0, 0.0], [0.0, math.cos(rx), -math.sin(rx)], [0.0, math.sin(rx), math.cos(rx)]]
    )
    rotation_y = np.array(
        [[math.cos(ry), 0.0, math.sin(ry)], [0.0, 1.0, 0.0], [-math.sin(ry), 0.0, math.cos(ry)]]
    )
    rotation_z = np.array(
        [[math.cos(rz), -math.sin(rz), 0.0], [math.sin(rz), math.cos(rz), 0.0], [0.0, 0.0, 1.0]]
    )
    return rotation_z @ rotation_y @ rotation_x


def transform_matrix(rotation: np.ndarray, translation: np.ndarray) -> np.ndarray:
    value = np.eye(4, dtype=np.float64)
    value[:3, :3] = rotation
    value[:3, 3] = translation
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def config(
    *, trial_id: str, source_path: str, target_path: str, source_sha: str, target_sha: str
) -> dict[str, object]:
    return {
        "trial_id": trial_id,
        "source_path": source_path,
        "target_path": target_path,
        "initial_transformation_4x4": np.eye(4).reshape(-1).tolist(),
        "parameters": PARAMETERS,
        "source_checksum": source_sha,
        "target_checksum": target_sha,
        "reference_pose_checksum": "identity-pose-v2",
        "snapshot_checksum": f"{trial_id}-snapshot",
    }


def main() -> None:
    points, analytic_normals = build_geometry()
    identity_source = HERE / "nondegenerate_source.pcd"
    identity_target = HERE / "nondegenerate_target.pcd"
    transformed_source = HERE / "known_small_transform_source.pcd"
    write_ascii_pcd(identity_source, points)
    write_ascii_pcd(identity_target, points)

    applied_translation = np.asarray([0.01, -0.02, 0.03], dtype=np.float64)
    applied_rpy_deg = [0.2, -0.3, 0.5]
    applied_rotation = rpy_matrix_degrees(*applied_rpy_deg)
    applied_target_to_source = transform_matrix(applied_rotation, applied_translation)
    transformed = (applied_rotation @ points.T).T + applied_translation
    write_ascii_pcd(transformed_source, transformed)
    expected_source_to_target = np.linalg.inv(applied_target_to_source)

    write_json(
        HERE / "known_small_transform_truth.json",
        {
            "rpy_convention": "Rz(yaw) @ Ry(pitch) @ Rx(roll)",
            "applied_translation_m": applied_translation.tolist(),
            "applied_rotation_rpy_deg": applied_rpy_deg,
            "applied_target_to_source_transform_4x4": applied_target_to_source.tolist(),
            "expected_source_to_target_transform_4x4": expected_source_to_target.tolist(),
        },
    )
    source_sha = sha256(identity_source)
    target_sha = sha256(identity_target)
    transformed_sha = sha256(transformed_source)
    write_json(
        HERE / "nondegenerate_identity_config.json",
        config(
            trial_id="pcl-v2-nondegenerate-identity",
            source_path=identity_source.name,
            target_path=identity_target.name,
            source_sha=source_sha,
            target_sha=target_sha,
        ),
    )
    write_json(
        HERE / "known_small_transform_config.json",
        config(
            trial_id="pcl-v2-known-small-transform",
            source_path=transformed_source.name,
            target_path=identity_target.name,
            source_sha=transformed_sha,
            target_sha=target_sha,
        ),
    )
    v1_source = ROOT / "tests/data/pcl_backend/identity_source.pcd"
    v1_target = ROOT / "tests/data/pcl_backend/identity_target.pcd"
    write_json(
        HERE / "planar_degeneracy_config.json",
        config(
            trial_id="pcl-v2-planar-degeneracy-diagnostic",
            source_path="../pcl_backend/identity_source.pcd",
            target_path="../pcl_backend/identity_target.pcd",
            source_sha=sha256(v1_source),
            target_sha=sha256(v1_target),
        ),
    )

    generated = [
        identity_source,
        identity_target,
        transformed_source,
        HERE / "known_small_transform_truth.json",
        HERE / "nondegenerate_identity_config.json",
        HERE / "known_small_transform_config.json",
        HERE / "planar_degeneracy_config.json",
    ]
    fixture_diagnostics = geometry_diagnostics(points, analytic_normals)
    fixture_diagnostics.update(
        {
            "generator_path": str(Path(__file__).resolve().relative_to(ROOT)),
            "generator_sha256": sha256(Path(__file__).resolve()),
            "identity_source_equals_target_bytewise": identity_source.read_bytes()
            == identity_target.read_bytes(),
            "input_sha256": {path.name: sha256(path) for path in generated},
            "external_v1_input_sha256": {
                str(v1_source.relative_to(ROOT)): sha256(v1_source),
                str(v1_target.relative_to(ROOT)): sha256(v1_target),
            },
        }
    )
    write_json(HERE / "fixture_manifest.json", fixture_diagnostics)

    locked = [Path(__file__).resolve(), *generated, HERE / "fixture_manifest.json"]
    (HERE / "SHA256SUMS").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in sorted(locked)),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
