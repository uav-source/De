"""Cache-backed Phase A Stage-1 runner, not executed during the Stage-0 round."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from .backend_phase_a_protocol import load_backend_phase_a_protocol
from .backend_phase_a_v1_1 import (
    DEFAULT_PCL_CLI_RELATIVE,
    OPEN3D_BACKEND,
    PCL_BACKEND,
    RunnerContractError,
    _run_open3d,
    _run_pcl,
    atomic_write_json,
    git_worktree_clean,
    validate_existing_result,
)
from .backend_phase_a_v1_2 import (
    V1_2_PROTOCOL_SHA256,
    planned_rows,
    snapshot_directory,
    validate_protocol_lock,
    validate_snapshot_directory,
    validate_snapshot_lock,
)


def _result_path(directory: Path, trial_id: str) -> Path:
    return directory / f"{hashlib.sha256(trial_id.encode('utf-8')).hexdigest()}.json"


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
    run_id: str,
    output_dir: str | Path,
    workers: int,
) -> dict[str, Any]:
    repository = Path(root).resolve()
    destination = Path(output_dir).resolve()
    _arguments(run_id, destination, workers)
    protocol = validate_protocol_lock(protocol_lock, repository)
    snapshots = validate_snapshot_lock(snapshot_lock, repository)
    plan, trials = planned_rows(repository)
    return {
        "schema_version": "backend_phase_a_v1_2_stage1_dry_run_v1",
        "run_id": run_id,
        "output_dir": str(destination),
        "workers": int(workers),
        "protocol_sha256": V1_2_PROTOCOL_SHA256,
        "implementation_sha256": protocol["implementation_sha256"],
        "snapshot_lock_sha256": snapshots["lock_payload_sha256"],
        "snapshot_lock_required": True,
        "DRY_RUN_PLANNED_SNAPSHOT_COUNT": len(plan),
        "DRY_RUN_PLANNED_TRIAL_COUNT": len(trials),
        "DRY_RUN_SNAPSHOT_GENERATION_COUNT": 0,
        "DRY_RUN_BACKEND_EXECUTION_COUNT": 0,
        "DRY_RUN_TRIAL_RESULT_COUNT": 0,
        "dry_run_pass": len(plan) == 210 and len(trials) == 420,
    }


def execute_stage1_from_cache(
    *,
    root: str | Path,
    protocol_lock: str | Path,
    snapshot_lock: str | Path,
    run_id: str,
    output_dir: str | Path,
    workers: int,
    resume: bool,
) -> dict[str, Any]:
    """Execute backends only from a verified Stage-0 cache.

    This function is implemented for the separately authorized Stage-1 round;
    the v1.2 Stage-0 workflow never calls it.
    """

    repository = Path(root).resolve()
    destination = Path(output_dir).resolve()
    _arguments(run_id, destination, workers)
    protocol = validate_protocol_lock(protocol_lock, repository)
    snapshot_lock_value = validate_snapshot_lock(snapshot_lock, repository)
    if not git_worktree_clean(repository):
        raise RunnerContractError("formal Stage 1 requires a clean Git worktree")
    cache_root = repository / str(snapshot_lock_value["snapshot_cache_root"])
    plans, _ = planned_rows(repository)
    base = load_backend_phase_a_protocol(repository)
    pcl_contract = protocol.get("pcl_cli_binary", {})
    pcl_cli = repository / str(
        pcl_contract.get("path", DEFAULT_PCL_CLI_RELATIVE.as_posix())
    )
    run_root = destination / run_id
    if run_root.exists() and not resume:
        raise FileExistsError("formal Stage-1 output exists; use --resume")
    run_root.mkdir(parents=True, exist_ok=True)
    completed: list[str] = []
    failed: list[str] = []
    resumed_ids: list[str] = []
    backend_execution_count = 0
    trial_result_count = 0
    for plan in plans:
        snapshot_id = str(plan["snapshot_id"])
        directory = snapshot_directory(cache_root, snapshot_id)
        metadata = validate_snapshot_directory(directory)
        source = np.load(directory / "source_points.npy", allow_pickle=False)
        target = np.load(directory / "target_points.npy", allow_pickle=False)
        reference = np.load(directory / "reference_pose.npy", allow_pickle=False)
        checksums = {
            "source_checksum": metadata["source_raw_checksum"],
            "target_checksum": metadata["target_raw_checksum"],
            "reference_pose_checksum": metadata["reference_pose_raw_checksum"],
            "snapshot_checksum": metadata["snapshot_checksum"],
        }
        existing: dict[str, dict[str, Any]] = {}
        futures = {}
        with ThreadPoolExecutor(max_workers=min(int(workers), 2)) as pool:
            for backend in (OPEN3D_BACKEND, PCL_BACKEND):
                trial_id = f"{snapshot_id}/{backend}"
                result_path = _result_path(run_root / "trials", trial_id)
                if result_path.exists():
                    if not resume:
                        raise FileExistsError(f"trial exists without --resume: {trial_id}")
                    existing[backend] = validate_existing_result(
                        result_path,
                        trial_id=trial_id,
                        protocol_sha256=V1_2_PROTOCOL_SHA256,
                        implementation_sha256=protocol["implementation_sha256"],
                        checksums=checksums,
                    )
                elif backend == OPEN3D_BACKEND:
                    futures[backend] = pool.submit(
                        _run_open3d,
                        source=source,
                        target=target,
                        reference=reference,
                        trial_id=trial_id,
                        snapshot_id=snapshot_id,
                        checksums=checksums,
                        protocol_sha256=V1_2_PROTOCOL_SHA256,
                        implementation_sha256=protocol["implementation_sha256"],
                        parameters=base.data["open3d_parameter_contract"]["parameters"],
                        fixture_only=False,
                    )
                else:
                    futures[backend] = pool.submit(
                        _run_pcl,
                        source=source,
                        target=target,
                        reference=reference,
                        trial_id=trial_id,
                        snapshot_id=snapshot_id,
                        checksums=checksums,
                        protocol_sha256=V1_2_PROTOCOL_SHA256,
                        implementation_sha256=protocol["implementation_sha256"],
                        parameters=base.data["pcl_parameter_contract"]["parameters"],
                        pcl_cli=pcl_cli,
                        fixture_only=False,
                    )
            for backend in (OPEN3D_BACKEND, PCL_BACKEND):
                trial_id = f"{snapshot_id}/{backend}"
                if backend in existing:
                    payload = existing[backend]
                    resumed_ids.append(trial_id)
                else:
                    payload = futures[backend].result()
                    atomic_write_json(_result_path(run_root / "trials", trial_id), payload)
                    backend_execution_count += 1
                    trial_result_count += 1
                completed.append(trial_id)
                if payload.get("solver_failed"):
                    failed.append(trial_id)
    manifest = {
        "schema_version": "backend_phase_a_v1_2_stage1_run_manifest_v1",
        "run_id": run_id,
        "completed_trial_ids": completed,
        "failed_trial_ids": failed,
        "resumed_trial_ids": resumed_ids,
        "snapshot_generation_count": 0,
        "backend_execution_count": backend_execution_count,
        "trial_result_count": trial_result_count,
        "snapshot_lock_sha256": snapshot_lock_value["lock_payload_sha256"],
    }
    atomic_write_json(run_root / "run_manifest.json", manifest, allow_replace=resume)
    return manifest


__all__ = ["dry_run_stage1", "execute_stage1_from_cache"]
