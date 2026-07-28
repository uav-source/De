"""Independent-seed synthetic helpers for Phase A v1.2 unit tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from zero_perturbation.backend_phase_a_protocol import (
    canonical_json_sha256,
    file_sha256,
)
from zero_perturbation.backend_phase_a_v1_2 import (
    CanonicalSnapshot,
    PROTOCOL_LOCK_SCHEMA,
    V1_2_PROTOCOL_SHA256,
    canonical_target,
    quantization_closure,
    raw_array_sha256,
    source_from_parent_indices,
)


ROOT = Path(__file__).resolve().parents[1]
PLANNED_SNAPSHOTS = (
    ROOT
    / "artifacts/current/zero_perturbation_backend_phase_a_v1_1_lock/planned_snapshots.csv"
)


def transform() -> np.ndarray:
    angles = np.deg2rad([7.3, -11.1, 19.7])
    cx, sx = np.cos(angles[0]), np.sin(angles[0])
    cy, sy = np.cos(angles[1]), np.sin(angles[1])
    cz, sz = np.cos(angles[2]), np.sin(angles[2])
    rx = np.array(((1, 0, 0), (0, cx, -sx), (0, sx, cx)))
    ry = np.array(((cy, 0, sy), (0, 1, 0), (-sy, 0, cy)))
    rz = np.array(((cz, -sz, 0), (sz, cz, 0), (0, 0, 1)))
    value = np.eye(4, dtype="<f8")
    value[:3, :3] = rz @ ry @ rx
    value[:3, 3] = [0.137, -0.283, 1.519]
    return np.ascontiguousarray(value)


def target_points(count: int = 64) -> np.ndarray:
    index = np.arange(count, dtype=np.float64)
    points = np.column_stack(
        (
            0.413 + index * 0.071,
            -1.271 + np.sin(index * 0.37) * 1.713,
            0.229 + np.cos(index * 0.23) * 0.917,
        )
    )
    return canonical_target(points)


def synthetic_snapshot(snapshot_id: str = "fixture/stage0/0") -> CanonicalSnapshot:
    target = target_points()
    reference = transform()
    indices = np.ascontiguousarray(np.arange(len(target)), dtype="<i8")
    source, source_f64, parents = source_from_parent_indices(
        target, indices, reference
    )
    closure = quantization_closure(
        source_points=source,
        source_float64=source_f64,
        parent_points_map_float64=parents,
        reference_pose=reference,
    )
    checksums = {
        "source_raw_checksum": raw_array_sha256(source),
        "target_raw_checksum": raw_array_sha256(target),
        "reference_pose_raw_checksum": raw_array_sha256(reference),
        "parent_index_raw_checksum": raw_array_sha256(indices),
        "parent_point_checksum": raw_array_sha256(
            np.ascontiguousarray(parents, dtype="<f8")
        ),
    }
    metadata = {
        "schema_version": "backend_phase_a_v1_2_stage0_snapshot_v1",
        "snapshot_id": snapshot_id,
        **checksums,
        "snapshot_checksum": canonical_json_sha256(
            {"snapshot_id": snapshot_id, **checksums}
        ),
        **closure,
    }
    return CanonicalSnapshot(source, target, reference, indices, source_f64, metadata)


def write_minimal_protocol_lock(path: Path) -> dict:
    payload = {
        "schema_version": PROTOCOL_LOCK_SCHEMA,
        "protocol_sha256": V1_2_PROTOCOL_SHA256,
        "PHASE_A_V1_2_PROTOCOL_LOCK_PASS": True,
        "stage0_snapshot_build_authorized": True,
        "implementation_sha256": "test-only",
        "planned_snapshots_path": PLANNED_SNAPSHOTS.relative_to(ROOT).as_posix(),
        "planned_snapshots_sha256": file_sha256(PLANNED_SNAPSHOTS),
    }
    value = {**payload, "lock_payload_sha256": canonical_json_sha256(payload)}
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return value
