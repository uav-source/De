from __future__ import annotations

from pathlib import Path

import numpy as np

from capture_range.anchor_validity_audit import AnchorAuditSnapshotBundle
from capture_range.types import RegistrationSnapshot


ROOT = Path(__file__).resolve().parents[1]


def sentinel_bundle() -> AnchorAuditSnapshotBundle:
    axis = np.linspace(-0.5, 0.5, 11)
    first, second = np.meshgrid(axis, axis, indexing="ij")
    points = np.column_stack((first.ravel(), second.ravel(), np.zeros(first.size)))
    reference = np.eye(4, dtype=np.float64)
    snapshot = RegistrationSnapshot(
        snapshot_id="anchor_audit_sentinel",
        scan_points=points,
        local_map_points=points,
        reference_pose=reference,
        registration_config={
            "registration": {
                "k_neighbors": 5,
                "max_neighbor_distance_m": 0.3,
                "plane_fit_tolerance_m": 1.0e-6,
                "huber_delta_m": 0.05,
                "damping": 1.0e-6,
                "rotation_step_tolerance_rad": 1.0e-5,
                "translation_step_tolerance_m": 1.0e-5,
                "min_correspondences": 30,
                "max_iterations": 5,
            },
            "success": {
                "translation_error_threshold_m": 0.02,
                "rotation_geodesic_error_threshold_deg": 0.5,
                "rotation_geodesic_error_threshold_rad": np.deg2rad(0.5),
                "require_solver_converged": True,
                "require_finite_result": True,
                "require_iteration_limit_not_failed": True,
            },
        },
        metadata={"fixture": "anchor_audit_non_day2_sentinel"},
    )
    return AnchorAuditSnapshotBundle(
        snapshot=snapshot,
        scene_id="sentinel_scene",
        scene_variant="SENTINEL",
        geometry_seed=1,
        measurement_seed=2,
        repeat_index=0,
        block_id="sentinel_block",
        base_snapshot_id="sentinel_snapshot",
        condition_id="LOCKED_FULL_NOISE",
        base_snapshot_checksum="base",
        scan_checksum="scan",
        map_checksum="map",
        dropout_checksum="dropout",
    )
