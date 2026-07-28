"""Resumable Development execution over 1260 shared snapshots."""

from __future__ import annotations

import csv
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from .metrics import pose_matrix, zero_initialization_error
from .native_backend import run_native_pair
from .open3d_backend import validate_open3d_version, run_open3d_full
from .protocol import DevelopmentSeedFirewall, load_protocol
from .snapshot_builder import build_snapshot
from .types import BackendResult, SnapshotKey


METHODS = ("native_full", "native_frozen", "open3d_full")


def enumerate_snapshot_keys(protocol: Any, *, smoke: bool = False) -> list[SnapshotKey]:
    geometry = list(protocol.development_seeds["geometry"].values())
    measurement = list(protocol.development_seeds["measurement"].values())
    repeats = list(protocol.section("seed_firewall")["repeat_indices"])
    if smoke:
        geometry = geometry[:1]
        measurement = measurement[:1]
        repeats = repeats[:1]
    return [
        SnapshotKey(scene, int(g), int(m), int(repeat), condition)
        for scene in protocol.scenes
        for g in geometry
        for m in measurement
        for repeat in repeats
        for condition in protocol.conditions
    ]


def _json_pose(pose: np.ndarray) -> str:
    return json.dumps(pose_matrix(pose).reshape(-1).tolist(), separators=(",", ":"))


def _trial_row(
    inventory: Mapping[str, Any], result: BackendResult, reference_pose: np.ndarray
) -> dict[str, Any]:
    error = zero_initialization_error(reference_pose, result.final_pose)
    return {
        "snapshot_id": inventory["snapshot_id"],
        "scene_variant": inventory["scene_variant"],
        "geometry_seed": inventory["geometry_seed"],
        "measurement_seed": inventory["measurement_seed"],
        "repeat_index": inventory["repeat_index"],
        "noise_condition": inventory["noise_condition"],
        "registration_backend": result.backend,
        "backend_input_checksum": result.extra["backend_input_checksum"],
        "scan_checksum": inventory["scan_checksum"],
        "map_checksum": inventory["map_checksum"],
        "reference_pose_checksum": inventory["reference_pose_checksum"],
        "initial_transformation": _json_pose(reference_pose),
        "final_transformation": _json_pose(result.final_pose),
        **error,
        "initial_cost": result.initial_cost,
        "final_cost": result.final_cost,
        "correspondence_count": result.correspondence_count,
        "iteration_count": result.iteration_count,
        "solver_converged": result.solver_converged,
        "finite_result": result.finite_result,
        "solver_failure": result.solver_failed,
        "termination_reason": result.termination_reason,
        "failure_reason": result.failure_reason,
        "runtime_ms": result.runtime_ms,
        "fitness": result.extra.get("fitness"),
        "inlier_rmse": result.extra.get("inlier_rmse"),
    }


def _key_payload(key: SnapshotKey) -> dict[str, Any]:
    return {
        "scene_variant": key.scene_variant,
        "geometry_seed": key.geometry_seed,
        "measurement_seed": key.measurement_seed,
        "repeat_index": key.repeat_index,
        "noise_condition": key.noise_condition,
    }


def _run_one(root: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    protocol = load_protocol(root)
    firewall = DevelopmentSeedFirewall(protocol)
    key = SnapshotKey(**payload)
    snapshot = build_snapshot(protocol, firewall, key)
    native_seed = firewall.seed("backend", "native")
    open3d_seed = firewall.seed("backend", "open3d")
    checksum = snapshot.checksums["backend_input_checksum"]
    native = run_native_pair(
        snapshot.scan_points,
        snapshot.map_points,
        snapshot.reference_pose,
        snapshot.registration_config,
        native_seed,
        checksum,
    )
    open3d = run_open3d_full(
        snapshot.scan_points,
        snapshot.map_points,
        snapshot.reference_pose,
        protocol.section("open3d_registration"),
        open3d_seed,
        checksum,
    )
    inventory = snapshot.inventory_row()
    full_row = _trial_row(inventory, native.full, snapshot.reference_pose)
    frozen_row = _trial_row(inventory, native.frozen, snapshot.reference_pose)
    open3d_row = _trial_row(inventory, open3d, snapshot.reference_pose)
    pairing_values = {
        full_row["backend_input_checksum"],
        frozen_row["backend_input_checksum"],
        open3d_row["backend_input_checksum"],
    }
    diagnostics = {
        "snapshot_id": snapshot.snapshot_id,
        "scene_variant": key.scene_variant,
        "geometry_seed": key.geometry_seed,
        "measurement_seed": key.measurement_seed,
        "repeat_index": key.repeat_index,
        "noise_condition": key.noise_condition,
        **dict(native.turnover),
        **dict(native.normal_turnover),
        **dict(native.full_frozen),
        "full_translation_error_m": full_row["translation_error_m"],
        "full_rotation_error_rad": full_row["rotation_error_rad"],
        "frozen_translation_error_m": frozen_row["translation_error_m"],
        "frozen_rotation_error_rad": frozen_row["rotation_error_rad"],
        **dict(native.traditional_metrics),
    }
    return {
        "inventory": inventory,
        "trials": [full_row, frozen_row, open3d_row],
        "native_diagnostics": diagnostics,
        "snapshot_pairing_violation_count": 0 if len(pairing_values) == 1 else 1,
        "snapshot_generation_count": 1,
        "firewall": firewall.report(),
    }


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    values = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not values:
        raise ValueError(f"refusing to write empty CSV: {path}")
    fields: list[str] = []
    for row in values:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(values)


def run_development(
    root: str | Path,
    *,
    run_id: str,
    workers: int = 1,
    smoke: bool = False,
    resume: bool = False,
) -> Path:
    repository = Path(root).resolve()
    protocol = load_protocol(repository)
    validate_open3d_version()
    keys = enumerate_snapshot_keys(protocol, smoke=smoke)
    expected = 42 if smoke else 1260
    if len(keys) != expected:
        raise RuntimeError(f"snapshot enumeration mismatch: {len(keys)} != {expected}")
    result_root = repository / protocol.section("outputs")["result_root"] / str(run_id)
    data_root = repository / protocol.section("outputs")["data_root"] / str(run_id)
    chunks = result_root / "snapshot_chunks"
    chunks.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)
    started = time.time()

    pending: list[tuple[int, SnapshotKey]] = []
    for index, key in enumerate(keys):
        chunk = chunks / f"{index:04d}.json"
        if resume and chunk.exists():
            continue
        pending.append((index, key))

    def save(index: int, value: Mapping[str, Any]) -> None:
        _write_json(chunks / f"{index:04d}.json", value)

    if int(workers) <= 1:
        for index, key in pending:
            save(index, _run_one(str(repository), _key_payload(key)))
    else:
        with ProcessPoolExecutor(max_workers=int(workers)) as executor:
            futures = {
                executor.submit(_run_one, str(repository), _key_payload(key)): index
                for index, key in pending
            }
            for future in as_completed(futures):
                save(futures[future], future.result())

    records = []
    for index in range(len(keys)):
        path = chunks / f"{index:04d}.json"
        if not path.exists():
            raise RuntimeError(f"missing snapshot result chunk: {path.name}")
        records.append(json.loads(path.read_text(encoding="utf-8")))
    inventory = [record["inventory"] for record in records]
    trials = [row for record in records for row in record["trials"]]
    diagnostics = [record["native_diagnostics"] for record in records]
    _write_csv(result_root / "snapshot_inventory.csv", inventory)
    _write_csv(result_root / "trial_results.csv", trials)
    _write_csv(result_root / "native_diagnostics.csv", diagnostics)
    _write_csv(data_root / "snapshot_keys.csv", [_key_payload(key) for key in keys])

    confirmatory_access = sum(
        int(record["firewall"]["CONFIRMATORY_SEED_INSTANTIATION_COUNT"])
        for record in records
    )
    old_seed_access = sum(
        int(record["firewall"]["OLD_CAPTURE_RANGE_TEST_SEED_ACCESS_COUNT"])
        for record in records
    )
    gt_leakage = sum(
        int(record["firewall"]["GT_OPTIMIZATION_LEAKAGE_COUNT"])
        for record in records
    )
    manifest = {
        "schema_version": "zero_perturbation_development_raw_run_v1",
        "run_id": str(run_id),
        "smoke": bool(smoke),
        "protocol_sha256": protocol.source_sha256,
        "open3d_version": validate_open3d_version(),
        "worker_count": int(workers),
        "snapshot_count": len(inventory),
        "trial_count": len(trials),
        "snapshot_generation_count": sum(
            int(record["snapshot_generation_count"]) for record in records
        ),
        "snapshot_pairing_violation_count": sum(
            int(record["snapshot_pairing_violation_count"]) for record in records
        ),
        "confirmatory_seed_instantiation_count": confirmatory_access,
        "old_capture_range_test_seed_access_count": old_seed_access,
        "gt_optimization_leakage_count": gt_leakage,
        "elapsed_seconds": time.time() - started,
        "development_pipeline_executable": True,
    }
    _write_json(result_root / "raw_run_manifest.json", manifest)
    return result_root


__all__ = ["METHODS", "enumerate_snapshot_keys", "run_development"]
