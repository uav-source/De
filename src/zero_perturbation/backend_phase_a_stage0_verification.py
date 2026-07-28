"""Independent on-disk verifier for Phase A v1.2 Stage 0.

The implementation intentionally does not import or call the Stage-0 builder.
It reconstructs every invariant from the protocol plan and cached files.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .backend_phase_a_protocol import (
    canonical_json_sha256,
    file_sha256,
    load_backend_phase_a_protocol,
)


PROTOCOL_SHA256 = "d412c9bb74fd4e3828c830d17144e1fb4440a27936941ce000e9daa87afabf81"
PROTOCOL_LOCK_SCHEMA = "backend_phase_a_v1_2_protocol_lock_v1"
METADATA_SCHEMA = "backend_phase_a_v1_2_stage0_snapshot_v1"
ARRAY_FILENAMES = (
    "source_points.npy",
    "target_points.npy",
    "reference_pose.npy",
    "source_parent_target_indices.npy",
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _raw_sha(array: np.ndarray) -> str:
    if not array.flags.c_contiguous:
        raise ValueError("array is not C-contiguous")
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def _snapshot_path(cache_root: Path, snapshot_id: str) -> Path:
    parts = Path(snapshot_id).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("unsafe snapshot ID")
    return cache_root.joinpath(*parts)


def _load_lock(root: Path, path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    lock = _json(path)
    if lock.get("schema_version") != PROTOCOL_LOCK_SCHEMA:
        raise ValueError("invalid v1.2 protocol lock schema")
    payload = {key: value for key, value in lock.items() if key != "lock_payload_sha256"}
    if canonical_json_sha256(payload) != lock.get("lock_payload_sha256"):
        raise ValueError("v1.2 protocol lock payload SHA mismatch")
    if (
        lock.get("protocol_sha256") != PROTOCOL_SHA256
        or lock.get("PHASE_A_V1_2_PROTOCOL_LOCK_PASS") is not True
        or lock.get("stage0_snapshot_build_authorized") is not True
    ):
        raise ValueError("v1.2 protocol lock does not authorize Stage 0")
    plan_path = root / str(lock["planned_snapshots_path"])
    if file_sha256(plan_path) != lock.get("planned_snapshots_sha256"):
        raise ValueError("planned snapshot CSV SHA mismatch")
    plan = _csv(plan_path)
    base = load_backend_phase_a_protocol(root)
    expected = [
        {key: str(value) for key, value in row.row().items()}
        for row in base.planned_snapshots()
    ]
    if plan != expected or len(plan) != 210:
        raise ValueError("planned snapshot CSV differs from frozen enumeration")
    return lock, plan


def _record_failure(
    failures: list[dict[str, str]], snapshot_id: str, classification: str, detail: str
) -> None:
    failures.append(
        {
            "snapshot_id": snapshot_id,
            "classification": classification,
            "detail": detail,
        }
    )


def _verify_one(
    *,
    directory: Path,
    plan: Mapping[str, str],
    failures: list[dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, Any]], np.ndarray, np.ndarray, np.ndarray]:
    snapshot_id = str(plan["snapshot_id"])
    expected_files = {*ARRAY_FILENAMES, "metadata.json"}
    actual_files = {child.name for child in directory.iterdir() if child.is_file()}
    child_directories = [child for child in directory.iterdir() if child.is_dir()]
    if actual_files != expected_files or child_directories:
        raise ValueError("snapshot file set is incomplete or contains extras")
    metadata = _json(directory / "metadata.json")
    if metadata.get("schema_version") != METADATA_SCHEMA:
        raise ValueError("metadata schema changed")
    metadata_payload = {
        key: value for key, value in metadata.items() if key != "metadata_payload_sha256"
    }
    metadata_checksum_pass = (
        canonical_json_sha256(metadata_payload)
        == metadata.get("metadata_payload_sha256")
    )
    if not metadata_checksum_pass:
        raise ValueError("metadata payload checksum mismatch")
    identity_expected = {
        "snapshot_id": snapshot_id,
        "scene_variant": str(plan["scene_variant"]),
        "geometry_seed": int(plan["geometry_seed_value"]),
        "geometry_seed_index": int(plan["geometry_seed_index"]),
        "measurement_seed": int(plan["measurement_seed_value"]),
        "measurement_seed_index": int(plan["measurement_seed_index"]),
        "repeat_index": int(plan["repeat_index"]),
        "condition": str(plan["condition"]),
    }
    if any(metadata.get(key) != value for key, value in identity_expected.items()):
        raise ValueError("metadata identity differs from plan")

    arrays = {
        "source": np.load(directory / "source_points.npy", allow_pickle=False),
        "target": np.load(directory / "target_points.npy", allow_pickle=False),
        "reference": np.load(directory / "reference_pose.npy", allow_pickle=False),
        "indices": np.load(
            directory / "source_parent_target_indices.npy", allow_pickle=False
        ),
    }
    specifications = {
        "source": (np.dtype("<f4"), 2, (3,)),
        "target": (np.dtype("<f4"), 2, (3,)),
        "reference": (np.dtype("<f8"), 2, (4,)),
        "indices": (np.dtype("<i8"), 1, ()),
    }
    for name, (dtype, dimensions, tail) in specifications.items():
        array = arrays[name]
        if (
            array.dtype != dtype
            or array.ndim != dimensions
            or array.shape[1:] != tail
            or not array.flags.c_contiguous
        ):
            raise ValueError(f"noncanonical array: {name}")
    source = arrays["source"]
    target = arrays["target"]
    reference = arrays["reference"]
    indices = arrays["indices"]
    if reference.shape != (4, 4) or len(source) != len(indices):
        raise ValueError("array row count or reference pose shape changed")
    finite_pass = bool(
        np.isfinite(source).all()
        and np.isfinite(target).all()
        and np.isfinite(reference).all()
    )
    if not finite_pass:
        raise ValueError("cached input contains nonfinite values")

    raw = {
        "source_raw_checksum": _raw_sha(source),
        "target_raw_checksum": _raw_sha(target),
        "reference_pose_raw_checksum": _raw_sha(reference),
        "parent_index_raw_checksum": _raw_sha(indices),
    }
    raw_checksum_pass = all(metadata.get(key) == value for key, value in raw.items())
    file_rows: list[dict[str, Any]] = []
    file_checksum_pass = True
    for filename in ARRAY_FILENAMES:
        actual_sha = file_sha256(directory / filename)
        expected_sha = metadata.get("array_file_sha256", {}).get(filename)
        matches = actual_sha == expected_sha
        file_checksum_pass = file_checksum_pass and matches
        file_rows.append(
            {
                "snapshot_id": snapshot_id,
                "filename": filename,
                "file_sha256": actual_sha,
                "metadata_file_sha256": expected_sha,
                "file_checksum_pass": matches,
            }
        )
    if not raw_checksum_pass or not file_checksum_pass:
        raise ValueError("raw or file checksum mismatch")

    out_of_range = int(np.count_nonzero((indices < 0) | (indices >= len(target))))
    duplicate = int(len(indices) - len(np.unique(indices)))
    if out_of_range:
        parents = np.empty((0, 3), dtype=np.float64)
    else:
        parents = target[indices].astype(np.float64)
    parent_checksum = _raw_sha(np.ascontiguousarray(parents, dtype="<f8"))
    lineage_violations = int(
        out_of_range
        + duplicate
        + (parent_checksum != metadata.get("parent_point_checksum"))
        + (parent_checksum != metadata.get("source_parent_target_points_map_f64_checksum"))
    )

    rotation = reference[:3, :3]
    translation = reference[:3, 3]
    source_float64 = (rotation.T @ (parents - translation).T).T
    source_requantized = np.ascontiguousarray(source_float64, dtype="<f4")
    source_inverse_transform_pass = bool(np.array_equal(source_requantized, source))
    lineage_violations += int(not source_inverse_transform_pass)

    source_q = source.astype(np.float64)
    reconstructed = (rotation @ source_q.T).T + translation
    actual = reconstructed - parents
    source_quantization = source_q - source_float64
    predicted = (rotation @ source_quantization.T).T
    residual = actual - predicted
    actual_norm = np.linalg.norm(actual, axis=1)
    predicted_norm = np.linalg.norm(predicted, axis=1)
    residual_norm = np.linalg.norm(residual, axis=1)
    scale = np.maximum.reduce(
        (
            np.ones(len(parents), dtype=np.float64),
            np.linalg.norm(parents, axis=1),
            np.linalg.norm(source_float64, axis=1),
            np.full(len(parents), np.linalg.norm(translation), dtype=np.float64),
        )
    )
    guard = 256.0 * np.finfo(np.float64).eps * scale
    normalized = residual_norm / guard
    residual_violations = int(np.count_nonzero(residual_norm > guard))
    actual_bound_violations = int(
        np.count_nonzero(actual_norm > predicted_norm + guard)
    )
    rotation_determinant = float(np.linalg.det(rotation))
    rotation_defect = float(np.linalg.norm(rotation.T @ rotation - np.eye(3), ord="fro"))
    rotation_quality_pass = bool(
        np.isfinite(rotation).all()
        and rotation_determinant > 0.0
        and abs(rotation_determinant - 1.0) <= 1.0e-12
        and rotation_defect <= 1.0e-12
    )
    closure_pass = residual_violations == 0 and actual_bound_violations == 0
    snapshot_checksum = canonical_json_sha256(
        {
            "snapshot_id": snapshot_id,
            **raw,
            "parent_point_checksum": parent_checksum,
        }
    )
    snapshot_checksum_pass = snapshot_checksum == metadata.get("snapshot_checksum")
    metadata_stat_match = all(
        np.isclose(float(metadata.get(key, np.nan)), value, rtol=0.0, atol=0.0)
        for key, value in {
            "reconstruction_error_median_m": float(np.median(actual_norm)),
            "reconstruction_error_q95_m": float(
                np.quantile(actual_norm, 0.95, method="linear")
            ),
            "reconstruction_error_max_m": float(np.max(actual_norm)),
            "predicted_quantization_median_m": float(np.median(predicted_norm)),
            "predicted_quantization_q95_m": float(
                np.quantile(predicted_norm, 0.95, method="linear")
            ),
            "predicted_quantization_max_m": float(np.max(predicted_norm)),
            "closure_residual_max_m": float(np.max(residual_norm)),
            "float64_guard_max_m": float(np.max(guard)),
            "max_normalized_closure_ratio": float(np.max(normalized)),
        }.items()
    )
    row = {
        "snapshot_id": snapshot_id,
        "scene_variant": str(plan["scene_variant"]),
        "geometry_seed": int(plan["geometry_seed_value"]),
        "measurement_seed": int(plan["measurement_seed_value"]),
        "repeat_index": int(plan["repeat_index"]),
        "condition": str(plan["condition"]),
        "source_point_count": int(len(source)),
        "target_point_count": int(len(target)),
        "source_raw_checksum": raw["source_raw_checksum"],
        "target_raw_checksum": raw["target_raw_checksum"],
        "reference_pose_raw_checksum": raw["reference_pose_raw_checksum"],
        "parent_index_raw_checksum": raw["parent_index_raw_checksum"],
        "snapshot_checksum": snapshot_checksum,
        "parent_index_unique_count": int(len(np.unique(indices))),
        "parent_index_out_of_range_count": out_of_range,
        "parent_index_duplicate_count": duplicate,
        "lineage_violation_count": lineage_violations,
        "source_inverse_transform_pass": source_inverse_transform_pass,
        "source_all_finite": bool(np.isfinite(source).all()),
        "target_all_finite": bool(np.isfinite(target).all()),
        "reference_pose_all_finite": bool(np.isfinite(reference).all()),
        "reference_rotation_determinant": rotation_determinant,
        "reference_rotation_orthogonality_defect_fro": rotation_defect,
        "reference_rotation_quality_pass": rotation_quality_pass,
        "reconstruction_error_median_m": float(np.median(actual_norm)),
        "reconstruction_error_q95_m": float(
            np.quantile(actual_norm, 0.95, method="linear")
        ),
        "reconstruction_error_max_m": float(np.max(actual_norm)),
        "predicted_quantization_median_m": float(np.median(predicted_norm)),
        "predicted_quantization_q95_m": float(
            np.quantile(predicted_norm, 0.95, method="linear")
        ),
        "predicted_quantization_max_m": float(np.max(predicted_norm)),
        "closure_residual_max_m": float(np.max(residual_norm)),
        "float64_guard_max_m": float(np.max(guard)),
        "max_normalized_closure_ratio": float(np.max(normalized)),
        "closure_residual_violation_count": residual_violations,
        "actual_error_bound_violation_count": actual_bound_violations,
        "quantization_closure_pass": closure_pass,
        "raw_checksum_pass": raw_checksum_pass,
        "file_checksum_pass": file_checksum_pass,
        "metadata_checksum_pass": metadata_checksum_pass,
        "snapshot_checksum_pass": snapshot_checksum_pass,
        "metadata_statistics_match": metadata_stat_match,
    }
    if not (
        lineage_violations == 0
        and closure_pass
        and raw_checksum_pass
        and file_checksum_pass
        and snapshot_checksum_pass
        and metadata_stat_match
        and rotation_quality_pass
    ):
        _record_failure(failures, snapshot_id, "SNAPSHOT_GATE_FAILURE", json.dumps(row, sort_keys=True))
    return row, file_rows, actual_norm, predicted_norm, normalized


def verify_stage0_cache(
    *, root: str | Path, protocol_lock: str | Path, cache_root: str | Path
) -> dict[str, Any]:
    repository = Path(root).resolve()
    cache = Path(cache_root).resolve()
    failures: list[dict[str, str]] = []
    try:
        lock, plans = _load_lock(repository, Path(protocol_lock).resolve())
    except Exception as error:
        return {
            "schema_version": "backend_phase_a_v1_2_independent_verification_v1",
            "verification_pass": False,
            "fatal_error": f"{type(error).__name__}: {error}",
            "snapshot_rows": [],
            "snapshot_file_rows": [],
            "failure_rows": [
                {
                    "snapshot_id": "",
                    "classification": "PROTOCOL_LOCK_FAILURE",
                    "detail": str(error),
                }
            ],
        }
    expected_ids = [str(row["snapshot_id"]) for row in plans]
    expected_set = set(expected_ids)
    metadata_paths = list(cache.rglob("metadata.json")) if cache.is_dir() else []
    discovered_ids: list[str] = []
    for path in metadata_paths:
        try:
            relative = path.parent.relative_to(cache).as_posix()
            discovered_ids.append(relative)
        except ValueError:
            continue
    counts = Counter(discovered_ids)
    actual_set = set(discovered_ids)
    missing = sorted(expected_set - actual_set)
    extra = sorted(actual_set - expected_set)
    duplicate_count = sum(count - 1 for count in counts.values() if count > 1)
    snapshot_rows: list[dict[str, Any]] = []
    file_rows: list[dict[str, Any]] = []
    actual_vectors: list[np.ndarray] = []
    predicted_vectors: list[np.ndarray] = []
    ratio_vectors: list[np.ndarray] = []
    corrupt_count = 0
    for item in missing:
        _record_failure(failures, item, "MISSING_SNAPSHOT", "planned cache directory is absent")
    for item in extra:
        _record_failure(failures, item, "EXTRA_SNAPSHOT", "cache ID is not planned")
    plan_by_id = {str(row["snapshot_id"]): row for row in plans}
    for snapshot_id in expected_ids:
        directory = _snapshot_path(cache, snapshot_id)
        if not directory.is_dir():
            continue
        try:
            row, files, actual, predicted, ratios = _verify_one(
                directory=directory, plan=plan_by_id[snapshot_id], failures=failures
            )
        except Exception as error:
            corrupt_count += 1
            _record_failure(
                failures,
                snapshot_id,
                "CORRUPT_SNAPSHOT",
                f"{type(error).__name__}: {error}",
            )
            continue
        snapshot_rows.append(row)
        file_rows.extend(files)
        actual_vectors.append(actual)
        predicted_vectors.append(predicted)
        ratio_vectors.append(ratios)

    source_by_scene: dict[str, set[str]] = defaultdict(set)
    target_by_scene: dict[str, set[str]] = defaultdict(set)
    count_by_scene: Counter[str] = Counter()
    for row in snapshot_rows:
        scene = str(row["scene_variant"])
        count_by_scene[scene] += 1
        source_by_scene[scene].add(str(row["source_raw_checksum"]))
        target_by_scene[scene].add(str(row["target_raw_checksum"]))
    diversity_rows = []
    for scene in load_backend_phase_a_protocol(repository).scenes:
        count = count_by_scene[scene]
        source_unique = len(source_by_scene[scene])
        target_unique = len(target_by_scene[scene])
        diversity_rows.append(
            {
                "scene_variant": scene,
                "snapshot_count": count,
                "unique_source_checksum_count": source_unique,
                "unique_target_checksum_count": target_unique,
                "duplicate_source_checksum_count": count - source_unique,
                "duplicate_target_checksum_count": count - target_unique,
                "scene_diversity_pass": count == 30 and source_unique >= 10,
            }
        )
    all_actual = np.concatenate(actual_vectors) if actual_vectors else np.asarray([])
    all_predicted = (
        np.concatenate(predicted_vectors) if predicted_vectors else np.asarray([])
    )
    all_ratios = np.concatenate(ratio_vectors) if ratio_vectors else np.asarray([])
    q = lambda values, value: float(np.quantile(values, value, method="linear"))
    aggregate = {
        "reconstruction_error_median_m": float(np.median(all_actual)) if len(all_actual) else None,
        "reconstruction_error_q95_m": q(all_actual, 0.95) if len(all_actual) else None,
        "reconstruction_error_max_m": float(np.max(all_actual)) if len(all_actual) else None,
        "predicted_quantization_median_m": float(np.median(all_predicted)) if len(all_predicted) else None,
        "predicted_quantization_q95_m": q(all_predicted, 0.95) if len(all_predicted) else None,
        "predicted_quantization_max_m": float(np.max(all_predicted)) if len(all_predicted) else None,
        "closure_residual_max_m": max(
            (float(row["closure_residual_max_m"]) for row in snapshot_rows),
            default=None,
        ),
        "float64_guard_max_m": max(
            (float(row["float64_guard_max_m"]) for row in snapshot_rows),
            default=None,
        ),
        "max_normalized_closure_ratio": float(np.max(all_ratios)) if len(all_ratios) else None,
    }
    lineage_violations = sum(int(row["lineage_violation_count"]) for row in snapshot_rows)
    out_of_range = sum(int(row["parent_index_out_of_range_count"]) for row in snapshot_rows)
    duplicates = sum(int(row["parent_index_duplicate_count"]) for row in snapshot_rows)
    checksum_violations = sum(
        int(not row[gate])
        for row in snapshot_rows
        for gate in (
            "raw_checksum_pass",
            "file_checksum_pass",
            "metadata_checksum_pass",
            "snapshot_checksum_pass",
        )
    )
    closure_violations = sum(
        int(row["closure_residual_violation_count"])
        + int(row["actual_error_bound_violation_count"])
        for row in snapshot_rows
    )
    all_complete = bool(
        len(snapshot_rows) == 210
        and not missing
        and not extra
        and duplicate_count == 0
        and corrupt_count == 0
    )
    lineage_pass = lineage_violations == 0 and out_of_range == 0 and duplicates == 0
    closure_pass = closure_violations == 0 and len(snapshot_rows) == 210
    cache_pass = checksum_violations == 0 and len(snapshot_rows) == 210
    diversity_pass = all(row["scene_diversity_pass"] for row in diversity_rows)
    verification_pass = bool(
        all_complete and lineage_pass and closure_pass and cache_pass and diversity_pass
    )
    return {
        "schema_version": "backend_phase_a_v1_2_independent_verification_v1",
        "protocol_sha256": PROTOCOL_SHA256,
        "implementation_sha256": lock.get("implementation_sha256"),
        "planned_snapshot_count": len(plans),
        "actual_complete_snapshot_count": len(snapshot_rows),
        "missing_snapshot_count": len(missing),
        "extra_snapshot_count": len(extra),
        "duplicate_snapshot_count": duplicate_count,
        "corrupt_snapshot_count": corrupt_count,
        "parent_index_out_of_range_count": out_of_range,
        "parent_index_duplicate_count": duplicates,
        "lineage_violation_count": lineage_violations,
        "cache_checksum_violation_count": checksum_violations,
        "closure_violation_count": closure_violations,
        "ALL_210_STAGE0_SNAPSHOTS_COMPLETE": all_complete,
        "SNAPSHOT_PROVENANCE_LINEAGE_PASS": lineage_pass,
        "FLOAT32_RECONSTRUCTION_CLOSURE_PASS": closure_pass,
        "CANONICAL_INPUT_CACHE_PASS": cache_pass,
        "IDEAL_MATCHED_SNAPSHOT_DIVERSITY_PASS": diversity_pass,
        "FORMAL_BACKEND_EXECUTION_COUNT": 0,
        "FORMAL_TRIAL_RESULT_COUNT": 0,
        "STAGE0_BACKEND_IMPORT_COUNT": 0,
        "STAGE0_BACKEND_EXECUTION_COUNT": 0,
        "NATIVE_EXECUTION_COUNT": 0,
        "aggregate_reconstruction": aggregate,
        "snapshot_rows": snapshot_rows,
        "snapshot_file_rows": file_rows,
        "diversity_rows": diversity_rows,
        "failure_rows": failures,
        "verification_pass": verification_pass,
    }


__all__ = ["verify_stage0_cache"]
