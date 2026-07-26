from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from capture_range.registration_core import (
    RegistrationCounters,
    RegistrationOptions,
    _build_point_to_plane_jacobian,
    _evaluate_full_reassociation,
    _fit_local_plane,
    _query_neighbors,
    pose_rotation_translation,
)


def test_vectorized_full_evaluation_matches_scalar_plane_algebra():
    rng = np.random.default_rng(42)
    local_map = rng.normal(size=(120, 3))
    scan = local_map[:35] + rng.normal(scale=0.002, size=(35, 3))
    pose = np.eye(4)
    options = RegistrationOptions(5, 3.0, 2.0, 0.05, 1e-6, 1e-5, 1e-5, 1, 3)
    tree = cKDTree(local_map, balanced_tree=True, compact_nodes=True)
    fast = _evaluate_full_reassociation(scan, local_map, pose, tree, options, RegistrationCounters())

    rotation, translation = pose_rotation_translation(pose)
    transformed = (rotation @ scan.T).T + translation
    distances, neighbors = _query_neighbors(tree, transformed, options.k_neighbors)
    accepted, scalar_neighbors, normals, centroids, jacobians, residuals = [], [], [], [], [], []
    for index in range(scan.shape[0]):
        if distances[index, -1] > options.max_neighbor_distance_m:
            continue
        plane = _fit_local_plane(local_map[neighbors[index]], options.plane_fit_tolerance_m)
        if plane is None:
            continue
        normal, centroid = plane
        accepted.append(index)
        scalar_neighbors.append(neighbors[index])
        normals.append(normal)
        centroids.append(centroid)
        jacobians.append(_build_point_to_plane_jacobian(rotation, scan[index], normal))
        residuals.append(float(normal @ (transformed[index] - centroid)))

    assert np.array_equal(fast.accepted_scan_indices, np.asarray(accepted, dtype=np.int64))
    assert np.array_equal(fast.neighbor_indices, np.asarray(scalar_neighbors, dtype=np.int64))
    assert np.allclose(fast.plane_normals, np.asarray(normals), atol=1e-12)
    assert np.allclose(fast.plane_centroids, np.asarray(centroids), atol=1e-12)
    assert np.allclose(fast.jacobian, np.asarray(jacobians), atol=1e-12)
    assert np.allclose(fast.residual, np.asarray(residuals), atol=1e-12)
