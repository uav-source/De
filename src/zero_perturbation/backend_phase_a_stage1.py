"""Future formal Stage-1 runner guarded by a new result-contract execution lock.

The old v1.2 authorization is intentionally not accepted. This module is not
called by the concentrated execution-chain audit.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .backend_phase_a_protocol import load_backend_phase_a_protocol
from .backend_phase_a_v1_1 import RunnerContractError, git_worktree_clean
from .backend_phase_a_v1_2 import (
    V1_2_PROTOCOL_SHA256,
    planned_rows,
    snapshot_directory,
    validate_protocol_lock,
    validate_snapshot_directory,
    validate_snapshot_lock,
)
from .phase_a_attempt_events import append_attempt_event
from .phase_a_execution_chain_audit import (
    DEFAULT_PCL_CLI_RELATIVE,
    execute_open3d_fixture,
    execute_pcl_fixture,
)
from .phase_a_execution_chain_fixture import FixtureSnapshot
from .phase_a_formal_execution_lock_schema import (
    IMPLEMENTATION_MANIFEST_RELATIVE_PATH,
    implementation_binding_sha256,
    validate_phase_a_formal_execution_lock_strict,
)
from .phase_a_trial_result_schema import (
    OPEN3D_BACKEND,
    PCL_BACKEND,
    SCHEMA_VERSION,
    canonical_json_bytes,
    file_sha256,
)
from .phase_a_trial_result_writer import (
    atomic_write_bytes,
    result_filename,
    write_phase_a_trial_result,
)
from .phase_a_trial_resume import validate_existing_trial_result_for_resume


def validate_stage1_execution_lock(
    path: str | Path,
    *,
    root: str | Path,
    protocol_lock: str | Path,
    snapshot_lock: str | Path,
    implementation_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compatibility name with strict v1 semantics; legacy lock formats are rejected."""

    repository = Path(root).resolve()
    manifest = (
        Path(implementation_manifest_path).resolve()
        if implementation_manifest_path is not None
        else repository / IMPLEMENTATION_MANIFEST_RELATIVE_PATH
    )
    return validate_phase_a_formal_execution_lock_strict(
        path,
        root=repository,
        protocol_lock=protocol_lock,
        snapshot_lock=snapshot_lock,
        implementation_manifest_path=manifest,
    )


def _arguments(run_id: str, output_dir: Path, workers: int) -> None:
    if not run_id or int(workers) < 1:
        raise ValueError("run ID and a positive worker count are required")
    existing = output_dir.resolve()
    while not existing.exists() and existing != existing.parent:
        existing = existing.parent
    if not existing.is_dir():
        raise PermissionError("output path has no existing directory ancestor")


def dry_run_stage1(
    *,
    root: str | Path,
    protocol_lock: str | Path,
    snapshot_lock: str | Path,
    formal_execution_lock: str | Path,
    run_id: str,
    output_dir: str | Path,
    workers: int,
    implementation_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    repository = Path(root).resolve()
    destination = Path(output_dir).resolve()
    execution = validate_stage1_execution_lock(
        formal_execution_lock,
        root=repository,
        protocol_lock=protocol_lock,
        snapshot_lock=snapshot_lock,
        implementation_manifest_path=implementation_manifest_path,
    )
    _arguments(run_id, destination, workers)
    validate_protocol_lock(protocol_lock, repository)
    snapshot_lock_value = validate_snapshot_lock(snapshot_lock, repository)
    plan, trials = planned_rows(repository)
    cache_root = repository / str(snapshot_lock_value["snapshot_cache_root"])
    cache_validation_count = 0
    for row in plan:
        validate_snapshot_directory(snapshot_directory(cache_root, str(row["snapshot_id"])))
        cache_validation_count += 1
    return {
        "ATTEMPT_STARTED_EVENT_COUNT": 0,
        "DRY_RUN_CACHE_VALIDATION_COUNT": cache_validation_count,
        "DRY_RUN_BACKEND_EXECUTION_COUNT": 0,
        "DRY_RUN_NATIVE_PLANNED_TRIAL_COUNT": 0,
        "DRY_RUN_OPEN3D_PLANNED_TRIAL_COUNT": sum(
            row["backend"] == OPEN3D_BACKEND for row in trials
        ),
        "DRY_RUN_PCL_PLANNED_TRIAL_COUNT": sum(
            row["backend"] == PCL_BACKEND for row in trials
        ),
        "DRY_RUN_PLANNED_SNAPSHOT_COUNT": len(plan),
        "DRY_RUN_PLANNED_TRIAL_COUNT": len(trials),
        "DRY_RUN_SNAPSHOT_GENERATION_COUNT": 0,
        "DRY_RUN_TRIAL_RESULT_COUNT": 0,
        "FORMAL_BACKEND_EXECUTION_COUNT": 0,
        "FORMAL_SEED_ACCESS_COUNT": 0,
        "FORMAL_TRIAL_RESULT_COUNT": 0,
        "NATIVE_EXECUTION_COUNT": 0,
        "dry_run_pass": (
            len(plan) == 210
            and len(trials) == 420
            and cache_validation_count == 210
        ),
        "implementation_sha256": implementation_binding_sha256(execution),
        "output_dir": str(destination),
        "protocol_sha256": V1_2_PROTOCOL_SHA256,
        "run_id": run_id,
        "schema_version": "backend_phase_a_v1_2_stage1_dry_run_v2",
        "snapshot_lock_sha256": file_sha256(snapshot_lock),
        "trial_result_schema_version": SCHEMA_VERSION,
        "workers": int(workers),
    }


def execute_stage1_from_cache(
    *,
    root: str | Path,
    protocol_lock: str | Path,
    snapshot_lock: str | Path,
    formal_execution_lock: str | Path,
    run_id: str,
    output_dir: str | Path,
    workers: int,
    resume: bool,
) -> dict[str, Any]:
    repository = Path(root).resolve()
    destination = Path(output_dir).resolve()
    execution = validate_stage1_execution_lock(
        formal_execution_lock,
        root=repository,
        protocol_lock=protocol_lock,
        snapshot_lock=snapshot_lock,
    )
    _arguments(run_id, destination, workers)
    if not git_worktree_clean(repository):
        raise RunnerContractError("formal Stage-1 requires a clean Git worktree")
    validate_protocol_lock(protocol_lock, repository)
    snapshot_lock_value = validate_snapshot_lock(snapshot_lock, repository)
    cache_root = repository / str(snapshot_lock_value["snapshot_cache_root"])
    plans, _ = planned_rows(repository)
    base = load_backend_phase_a_protocol(repository)
    pcl_cli = repository / DEFAULT_PCL_CLI_RELATIVE
    run_root = destination / run_id
    if run_root.exists() and not resume:
        raise FileExistsError("formal Stage-1 output exists; use --resume")
    run_root.mkdir(parents=True, exist_ok=True)
    results_dir = run_root / "raw_results"
    result_manifest_path = run_root / "raw_result_manifest.json"
    if result_manifest_path.exists():
        result_manifest = json.loads(result_manifest_path.read_text(encoding="utf-8"))
    else:
        result_manifest = {
            "results": {},
            "run_id": run_id,
            "schema_version": "phase_a_raw_result_manifest_v1",
        }
    completed: list[str] = []
    failed: list[str] = []
    resumed_ids: list[str] = []
    backend_execution_count = 0
    snapshot_lock_sha = file_sha256(snapshot_lock)
    implementation_sha = implementation_binding_sha256(execution)
    for plan in plans:
        snapshot_id = str(plan["snapshot_id"])
        directory = snapshot_directory(cache_root, snapshot_id)
        metadata = validate_snapshot_directory(directory)
        fixture = FixtureSnapshot(
            snapshot_id=snapshot_id,
            scene_variant=str(plan["scene_variant"]),
            condition="IDEAL_MATCHED",
            source=np.load(directory / "source_points.npy", allow_pickle=False),
            target=np.load(directory / "target_points.npy", allow_pickle=False),
            reference=np.load(directory / "reference_pose.npy", allow_pickle=False),
            expected_failure_classifications=("NONE",),
            checksums={
                "source_checksum": metadata["source_raw_checksum"],
                "target_checksum": metadata["target_raw_checksum"],
                "reference_pose_checksum": metadata["reference_pose_raw_checksum"],
                "snapshot_checksum": metadata["snapshot_checksum"],
            },
        )
        for backend in (OPEN3D_BACKEND, PCL_BACKEND):
            trial_id = f"{snapshot_id}/{backend}"
            common = {
                "backend": backend,
                "condition": "IDEAL_MATCHED",
                "implementation_sha256": implementation_sha,
                "planned_trial_id": trial_id,
                "protocol_sha256": V1_2_PROTOCOL_SHA256,
                "reference_pose_checksum": fixture.checksums["reference_pose_checksum"],
                "scene_variant": fixture.scene_variant,
                "schema_version": SCHEMA_VERSION,
                "snapshot_checksum": fixture.checksums["snapshot_checksum"],
                "snapshot_id": snapshot_id,
                "snapshot_lock_sha256": snapshot_lock_sha,
                "source_checksum": fixture.checksums["source_checksum"],
                "target_checksum": fixture.checksums["target_checksum"],
            }
            result_path = results_dir / result_filename(trial_id)
            if result_path.exists():
                if not resume:
                    raise FileExistsError(f"trial exists without --resume: {trial_id}")
                payload = validate_existing_trial_result_for_resume(
                    result_path,
                    manifest_entry=result_manifest["results"].get(trial_id),
                    expected=common,
                )
                resumed_ids.append(trial_id)
                append_attempt_event(
                    run_root / "attempt_events.ndjson",
                    planned_trial_id=trial_id,
                    snapshot_id=snapshot_id,
                    backend=backend,
                    event_type="SKIPPED_VALID_RESULT",
                    detail=None,
                )
            else:
                append_attempt_event(
                    run_root / "attempt_events.ndjson",
                    planned_trial_id=trial_id,
                    snapshot_id=snapshot_id,
                    backend=backend,
                    event_type="STARTED",
                    detail=None,
                )
                if backend == OPEN3D_BACKEND:
                    payload = execute_open3d_fixture(
                        fixture=fixture,
                        common=common,
                        parameters=base.data["open3d_parameter_contract"]["parameters"],
                    )
                else:
                    payload = execute_pcl_fixture(
                        fixture=fixture,
                        common=common,
                        parameters=base.data["pcl_parameter_contract"]["parameters"],
                        pcl_cli=pcl_cli,
                    )
                path, sha = write_phase_a_trial_result(results_dir, payload)
                result_manifest["results"][trial_id] = {
                    "path": path.name,
                    "planned_trial_id": trial_id,
                    "sha256": sha,
                }
                atomic_write_bytes(
                    result_manifest_path,
                    canonical_json_bytes(result_manifest),
                    replace=result_manifest_path.exists(),
                )
                append_attempt_event(
                    run_root / "attempt_events.ndjson",
                    planned_trial_id=trial_id,
                    snapshot_id=snapshot_id,
                    backend=backend,
                    event_type="COMPLETED",
                    detail=None,
                )
                backend_execution_count += 1
            completed.append(trial_id)
            if payload["solver_failure"]:
                failed.append(trial_id)
    manifest = {
        "backend_execution_count": backend_execution_count,
        "completed_trial_ids": completed,
        "failed_trial_ids": failed,
        "resumed_trial_ids": resumed_ids,
        "run_id": run_id,
        "schema_version": "backend_phase_a_v1_2_stage1_run_manifest_v2",
        "snapshot_generation_count": 0,
        "snapshot_lock_sha256": snapshot_lock_sha,
        "trial_result_count": backend_execution_count,
        "trial_result_schema_version": SCHEMA_VERSION,
    }
    atomic_write_bytes(
        run_root / "run_manifest.json",
        canonical_json_bytes(manifest),
        replace=resume,
    )
    return manifest


__all__ = [
    "dry_run_stage1",
    "execute_stage1_from_cache",
    "validate_stage1_execution_lock",
]
