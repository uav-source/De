"""Standalone point-to-plane registration primitives for capture-range trials.

The optimizer in this module deliberately accepts only the fixed scan, fixed
local map, initial pose, frozen registration configuration, and trial seed.  It
does not know the scoring pose or snapshot metadata.

Pose increments follow the repository's IKFoM product-manifold convention::

    R_next = R @ Exp(delta_theta_body)
    p_next = p + delta_position_world

The implementation supports both the repository-native TUM row
``[timestamp, tx, ty, tz, qx, qy, qz, qw]`` and a homogeneous 4x4 storage
representation.  The input representation is preserved in the output.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np
from scipy.spatial import cKDTree

from minibench.motion_simulator import apply_se3_increment
from minibench.observation_simulator import quat_to_rot, skew_matrix


@dataclass(frozen=True)
class RegistrationOptions:
    k_neighbors: int
    max_neighbor_distance_m: float
    plane_fit_tolerance_m: float
    huber_delta_m: float
    damping: float
    rotation_step_tolerance_rad: float
    translation_step_tolerance_m: float
    min_correspondences: int
    max_iterations: int


@dataclass
class RegistrationCounters:
    """Pass counts, not per-point operation counts."""

    full_reassociation_count: int = 0
    transform_count: int = 0
    nearest_neighbor_search_count: int = 0
    correspondence_build_count: int = 0
    plane_fit_count: int = 0
    jacobian_recompute_count: int = 0
    correspondence_checksums: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RegistrationEvaluation:
    jacobian: np.ndarray
    residual: np.ndarray
    accepted_scan_indices: np.ndarray
    neighbor_indices: np.ndarray
    plane_normals: np.ndarray
    plane_centroids: np.ndarray
    correspondence_count: int
    correspondence_checksum: str
    cost: float


@dataclass(frozen=True)
class RegistrationOutcome:
    final_pose: np.ndarray
    initial_evaluation: RegistrationEvaluation
    final_evaluation: RegistrationEvaluation
    iteration_count: int
    solver_converged: bool
    finite_result: bool
    iteration_limit_not_failed: bool
    termination_reason: str
    failure_reason: str
    counters: RegistrationCounters


@dataclass(frozen=True)
class FrozenJacobianBaseline:
    """Reference linearization used only by the comparison path."""

    snapshot_id: str
    scan_checksum: str
    map_checksum: str
    config_checksum: str
    reference_pose: np.ndarray
    selected_scan_points: np.ndarray
    jacobian: np.ndarray
    reference_residual: np.ndarray
    plane_normals: np.ndarray
    plane_centroids: np.ndarray
    correspondence_count: int
    correspondence_checksum: str
    reference_cost: float


def run_full_reassociation_core(
    scan_points: np.ndarray,
    local_map_points: np.ndarray,
    initial_pose: np.ndarray,
    registration_config: Mapping[str, Any],
    seed: int,
) -> RegistrationOutcome:
    """Run robust point-to-plane registration with fresh association each pass.

    A fixed ``cKDTree`` index may be reused because the local map is fixed.  Its
    query results, accepted correspondences, fitted planes, residuals,
    Jacobians, and robust weights are rebuilt for every nonlinear evaluation.
    One final evaluation is always performed after the last update.
    """

    scan, local_map = _validated_clouds(scan_points, local_map_points)
    pose = _validated_pose(initial_pose).copy()
    options = registration_options(registration_config)
    _validate_seed(seed)
    if local_map.shape[0] < options.k_neighbors:
        raise ValueError("local map has fewer points than k_neighbors")

    tree = cKDTree(local_map, balanced_tree=True, compact_nodes=True)
    counters = RegistrationCounters()
    current = _evaluate_full_reassociation(
        scan, local_map, pose, tree, options, counters
    )
    initial_evaluation = current
    iteration_count = 0
    converged = False
    termination_reason = ""
    failure_reason = ""

    for iteration_index in range(options.max_iterations):
        if current.correspondence_count < options.min_correspondences:
            termination_reason = "insufficient_correspondences"
            failure_reason = termination_reason
            break
        if not _evaluation_is_finite(current):
            termination_reason = "nonfinite_linearization"
            failure_reason = termination_reason
            break

        try:
            delta = _solve_robust_step(
                current.jacobian, current.residual, options
            )
        except (ValueError, np.linalg.LinAlgError):
            termination_reason = "linear_solver_failure"
            failure_reason = termination_reason
            break
        if not np.all(np.isfinite(delta)):
            termination_reason = "nonfinite_update"
            failure_reason = termination_reason
            break

        pose = boxplus_pose(pose, delta)
        iteration_count += 1
        if not np.all(np.isfinite(pose)):
            termination_reason = "nonfinite_pose"
            failure_reason = termination_reason
            break

        rotation_small = (
            float(np.linalg.norm(delta[:3]))
            <= options.rotation_step_tolerance_rad
        )
        translation_small = (
            float(np.linalg.norm(delta[3:6]))
            <= options.translation_step_tolerance_m
        )
        if rotation_small and translation_small:
            converged = True
            termination_reason = "converged_step"
            break

        # This is the nonlinear evaluation consumed by the next iteration.
        if iteration_index < options.max_iterations - 1:
            current = _evaluate_full_reassociation(
                scan, local_map, pose, tree, options, counters
            )
    else:
        termination_reason = "iteration_limit"
        failure_reason = termination_reason

    # A distinct final pass is required even when the last step was accepted,
    # failed, or the initial linearization had too few correspondences.
    final_evaluation = _evaluate_full_reassociation(
        scan, local_map, pose, tree, options, counters
    )
    if converged and final_evaluation.correspondence_count < options.min_correspondences:
        converged = False
        termination_reason = "final_insufficient_correspondences"
        failure_reason = termination_reason
    if converged and not _evaluation_is_finite(final_evaluation):
        converged = False
        termination_reason = "final_nonfinite_linearization"
        failure_reason = termination_reason

    expected_minimum = iteration_count + 1
    if counters.full_reassociation_count < expected_minimum:
        raise RuntimeError("full reassociation was not executed for every required pass")
    _assert_full_counter_identity(counters)

    finite_result = bool(
        np.all(np.isfinite(pose)) and _evaluation_is_finite(final_evaluation)
    )
    iteration_limit_not_failed = termination_reason != "iteration_limit"
    return RegistrationOutcome(
        final_pose=_readonly_copy(pose),
        initial_evaluation=initial_evaluation,
        final_evaluation=final_evaluation,
        iteration_count=iteration_count,
        solver_converged=converged,
        finite_result=finite_result,
        iteration_limit_not_failed=iteration_limit_not_failed,
        termination_reason=termination_reason,
        failure_reason=failure_reason,
        counters=counters,
    )


def prepare_frozen_linearization(
    scan_points: np.ndarray,
    local_map_points: np.ndarray,
    reference_pose: np.ndarray,
    registration_config: Mapping[str, Any],
    seed: int,
    *,
    snapshot_id: str = "",
) -> FrozenJacobianBaseline:
    """Build the one reference linearization used by frozen-baseline trials."""

    scan, local_map = _validated_clouds(scan_points, local_map_points)
    pose = _validated_pose(reference_pose)
    options = registration_options(registration_config)
    _validate_seed(seed)
    if local_map.shape[0] < options.k_neighbors:
        raise ValueError("local map has fewer points than k_neighbors")
    tree = cKDTree(local_map, balanced_tree=True, compact_nodes=True)
    preparation_counters = RegistrationCounters()
    evaluation = _evaluate_full_reassociation(
        scan, local_map, pose, tree, options, preparation_counters
    )
    if evaluation.correspondence_count < options.min_correspondences:
        raise ValueError("reference pose has insufficient correspondences")
    if not _evaluation_is_finite(evaluation):
        raise ValueError("reference linearization is non-finite")
    selected = scan[evaluation.accepted_scan_indices]
    return FrozenJacobianBaseline(
        snapshot_id=str(snapshot_id),
        scan_checksum=array_checksum(scan),
        map_checksum=array_checksum(local_map),
        config_checksum=config_checksum(registration_config),
        reference_pose=_readonly_copy(pose),
        selected_scan_points=_readonly_copy(selected),
        jacobian=_readonly_copy(evaluation.jacobian),
        reference_residual=_readonly_copy(evaluation.residual),
        plane_normals=_readonly_copy(evaluation.plane_normals),
        plane_centroids=_readonly_copy(evaluation.plane_centroids),
        correspondence_count=evaluation.correspondence_count,
        correspondence_checksum=evaluation.correspondence_checksum,
        reference_cost=evaluation.cost,
    )


def run_frozen_jacobian_core(
    baseline: FrozenJacobianBaseline,
    initial_pose: np.ndarray,
    registration_config: Mapping[str, Any],
    seed: int,
) -> RegistrationOutcome:
    """Run the isolated comparison path without trial-time association work.

    The residual and Jacobian are fixed at the reference pose and evaluated as
    a retained tangent-space linear model.  Only robust weights and pose updates
    are evaluated during a trial.  Consequently every formal geometry counter
    remains zero.
    """

    pose = _validated_pose(initial_pose).copy()
    options = registration_options(registration_config)
    _validate_seed(seed)
    if baseline.config_checksum != config_checksum(registration_config):
        raise ValueError("frozen baseline registration configuration mismatch")

    counters = RegistrationCounters()
    current = _evaluate_frozen(baseline, pose, options, counters)
    initial_evaluation = current
    iteration_count = 0
    converged = False
    termination_reason = ""
    failure_reason = ""

    for iteration_index in range(options.max_iterations):
        if current.correspondence_count < options.min_correspondences:
            termination_reason = "insufficient_correspondences"
            failure_reason = termination_reason
            break
        if not _evaluation_is_finite(current):
            termination_reason = "nonfinite_linearization"
            failure_reason = termination_reason
            break
        try:
            delta = _solve_robust_step(current.jacobian, current.residual, options)
        except (ValueError, np.linalg.LinAlgError):
            termination_reason = "linear_solver_failure"
            failure_reason = termination_reason
            break
        if not np.all(np.isfinite(delta)):
            termination_reason = "nonfinite_update"
            failure_reason = termination_reason
            break
        pose = boxplus_pose(pose, delta)
        iteration_count += 1
        if not np.all(np.isfinite(pose)):
            termination_reason = "nonfinite_pose"
            failure_reason = termination_reason
            break

        if (
            float(np.linalg.norm(delta[:3]))
            <= options.rotation_step_tolerance_rad
            and float(np.linalg.norm(delta[3:6]))
            <= options.translation_step_tolerance_m
        ):
            converged = True
            termination_reason = "converged_step"
            break
        if iteration_index < options.max_iterations - 1:
            current = _evaluate_frozen(baseline, pose, options, counters)
    else:
        termination_reason = "iteration_limit"
        failure_reason = termination_reason

    final_evaluation = _evaluate_frozen(baseline, pose, options, counters)
    if any(
        (
            counters.full_reassociation_count,
            counters.transform_count,
            counters.nearest_neighbor_search_count,
            counters.correspondence_build_count,
            counters.plane_fit_count,
            counters.jacobian_recompute_count,
        )
    ):
        raise RuntimeError("frozen-Jacobian trial performed forbidden reassociation work")

    finite_result = bool(
        np.all(np.isfinite(pose)) and _evaluation_is_finite(final_evaluation)
    )
    return RegistrationOutcome(
        final_pose=_readonly_copy(pose),
        initial_evaluation=initial_evaluation,
        final_evaluation=final_evaluation,
        iteration_count=iteration_count,
        solver_converged=converged,
        finite_result=finite_result,
        iteration_limit_not_failed=termination_reason != "iteration_limit",
        termination_reason=termination_reason,
        failure_reason=failure_reason,
        counters=counters,
    )


def registration_options(config: Mapping[str, Any]) -> RegistrationOptions:
    if not isinstance(config, Mapping):
        raise ValueError("registration_config must be a mapping")
    section: Mapping[str, Any] = config
    nested = config.get("registration")
    if isinstance(nested, Mapping):
        section = nested

    options = RegistrationOptions(
        k_neighbors=int(_value(section, ("k_neighbors", "nearest_neighbors"), 5)),
        max_neighbor_distance_m=float(
            _value(section, ("max_neighbor_distance_m", "neighbor_radius_m"), math.sqrt(5.0))
        ),
        plane_fit_tolerance_m=float(
            _value(section, ("plane_fit_tolerance_m", "plane_tolerance_m"), 0.1)
        ),
        huber_delta_m=float(
            _value(section, ("huber_delta_m", "robust_kernel_delta_m"), 0.05)
        ),
        damping=float(_value(section, ("damping", "damping_ratio"), 1.0e-6)),
        rotation_step_tolerance_rad=float(
            _value(section, ("rotation_step_tolerance_rad",), 1.0e-5)
        ),
        translation_step_tolerance_m=float(
            _value(section, ("translation_step_tolerance_m",), 1.0e-5)
        ),
        min_correspondences=int(_value(section, ("min_correspondences",), 6)),
        max_iterations=int(_value(section, ("max_iterations",), 20)),
    )
    if options.k_neighbors < 3:
        raise ValueError("k_neighbors must be at least three for plane fitting")
    if options.min_correspondences < 1 or options.max_iterations < 1:
        raise ValueError("min_correspondences and max_iterations must be positive")
    positive = (
        options.max_neighbor_distance_m,
        options.plane_fit_tolerance_m,
        options.huber_delta_m,
        options.damping,
        options.rotation_step_tolerance_rad,
        options.translation_step_tolerance_m,
    )
    if any(not math.isfinite(value) or value <= 0.0 for value in positive):
        raise ValueError("registration distances, thresholds, and damping must be positive")
    return options


def boxplus_pose(pose: np.ndarray, delta: np.ndarray) -> np.ndarray:
    """Apply body-right rotation and world-additive translation."""

    value = _validated_pose(pose)
    increment = np.asarray(delta, dtype=np.float64)
    if increment.shape != (6,) or not np.all(np.isfinite(increment)):
        raise ValueError("delta must be a finite length-6 vector")
    if value.shape == (8,):
        return apply_se3_increment(value, increment)
    updated = value.copy()
    updated[:3, :3] = value[:3, :3] @ _rotation_exp(increment[:3])
    updated[:3, 3] = value[:3, 3] + increment[3:6]
    return updated


def pose_rotation_translation(pose: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    value = _validated_pose(pose)
    if value.shape == (8,):
        return quat_to_rot(value[4:8]), value[1:4]
    return value[:3, :3], value[:3, 3]


def pose_boxminus(reference_pose: np.ndarray, pose: np.ndarray) -> np.ndarray:
    """Return ``[Log(R_ref.T R), p - p_ref]`` in native tangent order."""

    reference_rotation, reference_translation = pose_rotation_translation(
        reference_pose
    )
    rotation, translation = pose_rotation_translation(pose)
    return np.concatenate(
        [
            _rotation_log(reference_rotation.T @ rotation),
            translation - reference_translation,
        ]
    )


def array_checksum(values: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(values))
    digest = hashlib.sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(json.dumps(array.shape, separators=(",", ":")).encode("ascii"))
    digest.update(array.tobytes())
    return digest.hexdigest()


def config_checksum(config: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _jsonable(config), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _evaluate_full_reassociation(
    scan: np.ndarray,
    local_map: np.ndarray,
    pose: np.ndarray,
    tree: cKDTree,
    options: RegistrationOptions,
    counters: RegistrationCounters,
) -> RegistrationEvaluation:
    counters.full_reassociation_count += 1
    counters.transform_count += 1
    rotation, translation = pose_rotation_translation(pose)
    transformed = (rotation @ scan.T).T + translation

    counters.nearest_neighbor_search_count += 1
    distances, neighbor_indices = _query_neighbors(
        tree, transformed, options.k_neighbors
    )
    counters.correspondence_build_count += 1
    counters.plane_fit_count += 1
    counters.jacobian_recompute_count += 1

    accepted_indices: list[int] = []
    accepted_neighbors: list[np.ndarray] = []
    normals: list[np.ndarray] = []
    centroids: list[np.ndarray] = []
    jacobian_rows: list[np.ndarray] = []
    residuals: list[float] = []
    for scan_index in range(scan.shape[0]):
        if float(distances[scan_index, -1]) > options.max_neighbor_distance_m:
            continue
        indices = neighbor_indices[scan_index]
        plane = _fit_local_plane(
            local_map[indices], options.plane_fit_tolerance_m
        )
        if plane is None:
            continue
        normal, centroid = plane
        residual = float(normal @ (transformed[scan_index] - centroid))
        jacobian = _build_point_to_plane_jacobian(
            rotation, scan[scan_index], normal
        )
        accepted_indices.append(scan_index)
        accepted_neighbors.append(indices.copy())
        normals.append(normal)
        centroids.append(centroid)
        jacobian_rows.append(jacobian)
        residuals.append(residual)

    count = len(accepted_indices)
    jacobian_array = (
        np.asarray(jacobian_rows, dtype=np.float64).reshape(count, 6)
        if count
        else np.empty((0, 6), dtype=np.float64)
    )
    residual_array = np.asarray(residuals, dtype=np.float64)
    accepted_array = np.asarray(accepted_indices, dtype=np.int64)
    neighbors_array = (
        np.asarray(accepted_neighbors, dtype=np.int64).reshape(
            count, options.k_neighbors
        )
        if count
        else np.empty((0, options.k_neighbors), dtype=np.int64)
    )
    normals_array = (
        np.asarray(normals, dtype=np.float64).reshape(count, 3)
        if count
        else np.empty((0, 3), dtype=np.float64)
    )
    centroids_array = (
        np.asarray(centroids, dtype=np.float64).reshape(count, 3)
        if count
        else np.empty((0, 3), dtype=np.float64)
    )
    checksum = _correspondence_checksum(accepted_array, neighbors_array)
    counters.correspondence_checksums.append(checksum)
    return RegistrationEvaluation(
        jacobian=_readonly_copy(jacobian_array),
        residual=_readonly_copy(residual_array),
        accepted_scan_indices=_readonly_copy(accepted_array),
        neighbor_indices=_readonly_copy(neighbors_array),
        plane_normals=_readonly_copy(normals_array),
        plane_centroids=_readonly_copy(centroids_array),
        correspondence_count=count,
        correspondence_checksum=checksum,
        cost=_huber_cost(residual_array, options.huber_delta_m),
    )


def _evaluate_frozen(
    baseline: FrozenJacobianBaseline,
    pose: np.ndarray,
    options: RegistrationOptions,
    counters: RegistrationCounters,
) -> RegistrationEvaluation:
    # The comparison evaluates the retained tangent-space model directly and
    # must keep every formal geometric-rebuild counter at zero.
    tangent = pose_boxminus(baseline.reference_pose, pose)
    residual = baseline.reference_residual + baseline.jacobian @ tangent
    count = baseline.correspondence_count
    empty_neighbors = np.empty((count, 0), dtype=np.int64)
    return RegistrationEvaluation(
        jacobian=baseline.jacobian,
        residual=_readonly_copy(residual),
        accepted_scan_indices=_readonly_copy(np.arange(count, dtype=np.int64)),
        neighbor_indices=_readonly_copy(empty_neighbors),
        plane_normals=baseline.plane_normals,
        plane_centroids=baseline.plane_centroids,
        correspondence_count=count,
        correspondence_checksum=baseline.correspondence_checksum,
        cost=_huber_cost(residual, options.huber_delta_m),
    )


def _query_neighbors(
    tree: cKDTree, transformed_scan: np.ndarray, k_neighbors: int
) -> tuple[np.ndarray, np.ndarray]:
    distances, indices = tree.query(
        transformed_scan, k=int(k_neighbors), workers=1
    )
    distances = np.asarray(distances, dtype=np.float64).reshape(
        transformed_scan.shape[0], int(k_neighbors)
    )
    indices = np.asarray(indices, dtype=np.int64).reshape(
        transformed_scan.shape[0], int(k_neighbors)
    )
    # cKDTree does not promise stable candidate membership when more than k map
    # points tie at the kth distance.  Expand each kth-radius boundary, compute
    # exact candidate distances, then select by (distance, map index).  The
    # small Day 1 smoke clouds make this deterministic tie resolution cheap.
    map_points = np.asarray(tree.data, dtype=np.float64)
    for row in range(distances.shape[0]):
        kth_distance = float(distances[row, -1])
        radius = kth_distance + max(1.0e-12, abs(kth_distance) * 1.0e-12)
        candidates = np.asarray(
            tree.query_ball_point(transformed_scan[row], r=radius), dtype=np.int64
        )
        if candidates.size < int(k_neighbors):
            raise RuntimeError("nearest-neighbor boundary expansion lost a kNN candidate")
        offsets = map_points[candidates] - transformed_scan[row]
        candidate_distances = np.linalg.norm(offsets, axis=1)
        order = np.lexsort((candidates, candidate_distances))[: int(k_neighbors)]
        indices[row] = candidates[order]
        distances[row] = candidate_distances[order]
    return distances, indices


def _fit_local_plane(
    neighbors: np.ndarray, tolerance_m: float
) -> tuple[np.ndarray, np.ndarray] | None:
    points = np.asarray(neighbors, dtype=np.float64)
    if points.ndim != 2 or points.shape[0] < 3 or points.shape[1] != 3:
        return None
    centroid = np.mean(points, axis=0)
    centered = points - centroid
    covariance = centered.T @ centered / float(points.shape[0])
    if not np.all(np.isfinite(covariance)):
        return None
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    if not np.all(np.isfinite(eigenvalues)):
        return None
    normal = eigenvectors[:, 0]
    normal_norm = float(np.linalg.norm(normal))
    if normal_norm <= 1.0e-12:
        return None
    normal = normal / normal_norm
    # Eigenvector signs are arbitrary.  Canonicalization prevents platform or
    # run dependent signs from entering residual traces and checksums.
    pivot = int(np.argmax(np.abs(normal)))
    if float(normal[pivot]) < 0.0:
        normal = -normal
    deviations = np.abs(centered @ normal)
    if float(np.max(deviations)) > float(tolerance_m):
        return None
    return normal, centroid


def _build_point_to_plane_jacobian(
    rotation: np.ndarray, scan_point: np.ndarray, normal: np.ndarray
) -> np.ndarray:
    rotational = normal @ (-rotation @ skew_matrix(scan_point))
    return np.concatenate([rotational, normal]).astype(np.float64, copy=False)


def _solve_robust_step(
    jacobian: np.ndarray, residual: np.ndarray, options: RegistrationOptions
) -> np.ndarray:
    if jacobian.ndim != 2 or jacobian.shape[1] != 6:
        raise ValueError("jacobian must have shape [N,6]")
    if residual.shape != (jacobian.shape[0],):
        raise ValueError("residual must match jacobian rows")
    absolute = np.abs(residual)
    weights = np.ones_like(absolute)
    outside = absolute > options.huber_delta_m
    weights[outside] = options.huber_delta_m / absolute[outside]
    sqrt_weights = np.sqrt(weights)
    robust_jacobian = jacobian * sqrt_weights[:, None]
    robust_residual = residual * sqrt_weights
    hessian = robust_jacobian.T @ robust_jacobian
    gradient = robust_jacobian.T @ robust_residual
    hessian = 0.5 * (hessian + hessian.T)
    scale = max(float(np.max(np.diag(hessian))), 1.0)
    damped = hessian + (options.damping * scale) * np.eye(6)
    return -np.linalg.solve(damped, gradient)


def _huber_cost(residual: np.ndarray, delta: float) -> float:
    values = np.abs(np.asarray(residual, dtype=np.float64))
    inside = values <= float(delta)
    losses = np.empty_like(values)
    losses[inside] = 0.5 * values[inside] ** 2
    losses[~inside] = float(delta) * (
        values[~inside] - 0.5 * float(delta)
    )
    return float(np.sum(losses))


def _correspondence_checksum(
    accepted_scan_indices: np.ndarray, neighbor_indices: np.ndarray
) -> str:
    digest = hashlib.sha256()
    for name, values in (
        ("accepted_scan_indices", accepted_scan_indices),
        ("neighbor_indices", neighbor_indices),
    ):
        array = np.ascontiguousarray(values)
        digest.update(name.encode("ascii"))
        digest.update(array.dtype.str.encode("ascii"))
        digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
        digest.update(array.tobytes())
    return digest.hexdigest()


def _validated_clouds(
    scan_points: np.ndarray, local_map_points: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    scan = np.asarray(scan_points, dtype=np.float64)
    local_map = np.asarray(local_map_points, dtype=np.float64)
    if scan.ndim != 2 or scan.shape[1] != 3 or scan.shape[0] == 0:
        raise ValueError("scan_points must have non-empty shape [N,3]")
    if local_map.ndim != 2 or local_map.shape[1] != 3 or local_map.shape[0] == 0:
        raise ValueError("local_map_points must have non-empty shape [M,3]")
    if not np.all(np.isfinite(scan)) or not np.all(np.isfinite(local_map)):
        raise ValueError("point clouds must be finite")
    return scan, local_map


def _validated_pose(pose: np.ndarray) -> np.ndarray:
    value = np.asarray(pose, dtype=np.float64)
    if value.shape == (8,):
        if not np.all(np.isfinite(value)):
            raise ValueError("native pose must be finite")
        if float(np.linalg.norm(value[4:8])) <= 1.0e-12:
            raise ValueError("native pose quaternion cannot be zero")
        return value
    if value.shape == (4, 4):
        if not np.all(np.isfinite(value)):
            raise ValueError("homogeneous pose must be finite")
        if not np.allclose(value[3], [0.0, 0.0, 0.0, 1.0], atol=1.0e-9):
            raise ValueError("homogeneous pose has an invalid final row")
        rotation = value[:3, :3]
        if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1.0e-7):
            raise ValueError("homogeneous pose rotation must be orthonormal")
        if float(np.linalg.det(rotation)) <= 0.0:
            raise ValueError("homogeneous pose rotation must be proper")
        return value
    raise ValueError("pose must have shape [8] or [4,4]")


def _rotation_exp(rotation_vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(rotation_vector, dtype=np.float64)
    angle = float(np.linalg.norm(vector))
    hat = skew_matrix(vector)
    if angle < 1.0e-8:
        return np.eye(3) + hat + 0.5 * (hat @ hat)
    unit_hat = hat / angle
    return (
        np.eye(3)
        + math.sin(angle) * unit_hat
        + (1.0 - math.cos(angle)) * (unit_hat @ unit_hat)
    )


def _rotation_log(rotation: np.ndarray) -> np.ndarray:
    matrix = np.asarray(rotation, dtype=np.float64)
    cosine = float(np.clip((np.trace(matrix) - 1.0) * 0.5, -1.0, 1.0))
    angle = math.acos(cosine)
    vee = np.array(
        [
            matrix[2, 1] - matrix[1, 2],
            matrix[0, 2] - matrix[2, 0],
            matrix[1, 0] - matrix[0, 1],
        ],
        dtype=np.float64,
    )
    if angle < 1.0e-8:
        return 0.5 * vee
    sine = math.sin(angle)
    if abs(sine) <= 1.0e-10:
        # Day 1 perturbations are far from pi; keep a deterministic finite
        # fallback for out-of-scope callers.
        eigenvalues, eigenvectors = np.linalg.eigh(matrix)
        axis = eigenvectors[:, int(np.argmin(np.abs(eigenvalues - 1.0)))]
        pivot = int(np.argmax(np.abs(axis)))
        if axis[pivot] < 0.0:
            axis = -axis
        return angle * axis / max(float(np.linalg.norm(axis)), 1.0e-12)
    return (angle / (2.0 * sine)) * vee


def _evaluation_is_finite(evaluation: RegistrationEvaluation) -> bool:
    return bool(
        math.isfinite(evaluation.cost)
        and np.all(np.isfinite(evaluation.jacobian))
        and np.all(np.isfinite(evaluation.residual))
    )


def _assert_full_counter_identity(counters: RegistrationCounters) -> None:
    expected = counters.full_reassociation_count
    observed = (
        counters.transform_count,
        counters.nearest_neighbor_search_count,
        counters.correspondence_build_count,
        counters.plane_fit_count,
        counters.jacobian_recompute_count,
        len(counters.correspondence_checksums),
    )
    if any(value != expected for value in observed):
        raise RuntimeError(
            f"full reassociation instrumentation mismatch: expected={expected}, observed={observed}"
        )


def _readonly_copy(values: np.ndarray) -> np.ndarray:
    output = np.array(values, copy=True)
    output.setflags(write=False)
    return output


def _validate_seed(seed: int) -> None:
    if int(seed) < 0:
        raise ValueError("seed must be non-negative")


def _value(section: Mapping[str, Any], names: tuple[str, ...], default: Any) -> Any:
    for name in names:
        if name in section:
            return section[name]
    return default


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


# Compact aliases for callers and tests that prefer a verb-first name.
register_full_reassociation = run_full_reassociation_core
