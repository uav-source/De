"""Layer-separated Phase A v2 execution engine and zero-execution dry-run."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .backend_phase_a_v1_2 import snapshot_directory
from .phase_a_attempt_events import append_attempt_event
from .phase_a_execution_chain_audit import (
    execute_fixture_audit_trials,
    execute_open3d_fixture,
    execute_pcl_fixture,
)
from .phase_a_execution_chain_fixture import FixtureSnapshot
from .phase_a_formal_run_lock_v2 import (
    FormalRunLockError,
    validate_formal_run_lock_payload,
    validate_plan_bindings,
)
from .phase_a_implementation_lock_v2 import (
    ImplementationLockError,
    load_implementation_lock,
)
from .phase_a_lock_architecture_v2 import (
    LockArchitectureError,
    SNAPSHOT_BINDING_NAME,
    validate_snapshot_binding,
)
from .phase_a_scientific_lock_v2 import ScientificLockError, load_scientific_lock
from .phase_a_trial_result_schema import (
    OPEN3D_BACKEND,
    PCL_BACKEND,
    SCHEMA_VERSION,
    canonical_json_bytes,
    canonical_json_sha256,
    file_sha256,
)
from .phase_a_trial_result_writer import (
    atomic_write_bytes,
    result_filename,
    write_phase_a_trial_result,
)
from .phase_a_trial_resume import validate_existing_trial_result_for_resume


OPEN3D_PLAN_BACKEND = "open3d_point_to_plane"
PCL_PLAN_BACKEND = "pcl_iterative_closest_point_with_normals"
NATIVE_BACKENDS = frozenset({"native_full", "native_frozen"})


class LockValidationFailure(RuntimeError):
    """Stable pre-cache lock failure with a machine-readable classification."""

    def __init__(self, classification: str, message: str):
        super().__init__(f"{classification}: {message}")
        self.classification = classification


@dataclass
class ValidationTrace:
    steps: list[str] = field(default_factory=list)
    cache_read_count: int = 0
    formal_seed_access_count: int = 0
    backend_execution_count: int = 0
    trial_result_count: int = 0
    attempt_started_count: int = 0

    def mark(self, step: str) -> None:
        self.steps.append(step)


def _json(path: Path, classification: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LockValidationFailure(classification, f"cannot parse {path}") from error
    if type(value) is not dict:
        raise LockValidationFailure(classification, f"JSON root is not an object: {path}")
    return value


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _classify_layer_error(error: Exception, default: str) -> LockValidationFailure:
    message = str(error)
    for classification in (
        "LOCK_LAYER_VIOLATION",
        "IMPLEMENTATION_SHA_MISMATCH",
        "TRIAL_PLAN_MISMATCH",
        "SCIENTIFIC_LOCK_INVALID",
        "SNAPSHOT_LOCK_INVALID",
        "IMPLEMENTATION_LOCK_INVALID",
        "FORMAL_RUN_LOCK_INVALID",
    ):
        if classification in message:
            return LockValidationFailure(classification, message)
    return LockValidationFailure(default, message)


def _validate_environment(repository: Path) -> dict[str, Any]:
    if sys.version_info[:2] != (3, 11):
        raise LockValidationFailure("FORMAL_RUN_LOCK_INVALID", "Python 3.11 is required")
    try:
        import open3d as o3d
    except Exception as error:  # pragma: no cover - environment-specific import failure
        raise LockValidationFailure("FORMAL_RUN_LOCK_INVALID", "Open3D import failed") from error
    if str(o3d.__version__) != "0.19.0+b012259":
        raise LockValidationFailure("FORMAL_RUN_LOCK_INVALID", "Open3D version changed")
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout:
        raise LockValidationFailure("FORMAL_RUN_LOCK_INVALID", "formal run requires clean worktree")
    return {"open3d_version": str(o3d.__version__), "python_version": sys.version.split()[0], "worktree_clean": True}


def validate_lock_stack(
    *, root: str | Path, formal_run_lock: str | Path,
    trace: ValidationTrace | None = None, require_environment: bool = True,
) -> dict[str, Any]:
    """Validate all lock layers in the mandatory pre-cache order."""

    repository = Path(root).resolve()
    audit = trace if trace is not None else ValidationTrace()
    formal_path = Path(formal_run_lock).resolve()

    # 1-3: Formal lock read, schema, and payload.
    formal_raw = _json(formal_path, "FORMAL_RUN_LOCK_INVALID")
    audit.mark("formal_run_lock_read")
    try:
        formal = validate_formal_run_lock_payload(formal_raw, root=repository)
    except FormalRunLockError as error:
        raise _classify_layer_error(error, "FORMAL_RUN_LOCK_INVALID") from error
    audit.mark("formal_run_lock_schema_and_payload_verified")

    # 4-6: Scientific lock read, SHA, payload, and layer purity.
    scientific_path = _resolve(repository, str(formal["scientific_protocol_lock_path"]))
    if not scientific_path.is_file() or file_sha256(scientific_path) != formal["scientific_protocol_lock_sha256"]:
        raise LockValidationFailure("SCIENTIFIC_LOCK_INVALID", "scientific lock file SHA mismatch")
    try:
        scientific = load_scientific_lock(scientific_path, root=repository)
    except ScientificLockError as error:
        raise _classify_layer_error(error, "SCIENTIFIC_LOCK_INVALID") from error
    audit.mark("scientific_lock_verified")

    # 7-8: Existing byte-exact Snapshot Lock and the v2 reference binding.
    snapshot_path = _resolve(repository, str(formal["snapshot_lock_path"]))
    if not snapshot_path.is_file() or file_sha256(snapshot_path) != formal["snapshot_lock_sha256"]:
        raise LockValidationFailure("SNAPSHOT_LOCK_INVALID", "snapshot lock file SHA mismatch")
    snapshot = _json(snapshot_path, "SNAPSHOT_LOCK_INVALID")
    snapshot_payload = dict(snapshot)
    stored_snapshot_sha = snapshot_payload.pop("lock_payload_sha256", None)
    if stored_snapshot_sha != canonical_json_sha256(snapshot_payload):
        raise LockValidationFailure("SNAPSHOT_LOCK_INVALID", "snapshot lock payload SHA mismatch")
    if snapshot.get("PHASE_A_V1_2_STAGE0_PASS") is not True:
        raise LockValidationFailure("SNAPSHOT_LOCK_INVALID", "Stage-0 is not PASS")
    binding_path = scientific_path.parent / SNAPSHOT_BINDING_NAME
    binding_raw = _json(binding_path, "SNAPSHOT_LOCK_INVALID")
    try:
        binding = validate_snapshot_binding(
            binding_raw,
            root=repository,
            expected_snapshot_path=str(formal["snapshot_lock_path"]),
            expected_snapshot_sha256=str(formal["snapshot_lock_sha256"]),
        )
    except LockArchitectureError as error:
        raise _classify_layer_error(error, "SNAPSHOT_LOCK_INVALID") from error
    audit.mark("snapshot_lock_verified")

    # 9-12: Implementation lock payload, layer purity, and live component SHA.
    implementation_path = _resolve(repository, str(formal["execution_implementation_lock_path"]))
    if not implementation_path.is_file() or file_sha256(implementation_path) != formal["execution_implementation_lock_sha256"]:
        raise LockValidationFailure("IMPLEMENTATION_LOCK_INVALID", "implementation lock file SHA mismatch")
    try:
        implementation = load_implementation_lock(implementation_path, root=repository)
    except ImplementationLockError as error:
        raise _classify_layer_error(error, "IMPLEMENTATION_LOCK_INVALID") from error
    audit.mark("implementation_lock_verified")

    # 13-15: Exact plans, backend boundary, and the sole authorization edge.
    try:
        plans = validate_plan_bindings(formal, root=repository)
    except FormalRunLockError as error:
        raise _classify_layer_error(error, "TRIAL_PLAN_MISMATCH") from error
    if formal["planned_snapshot_count"] != scientific["planned_snapshot_count"] or formal["planned_trial_count"] != scientific["planned_trial_count"]:
        raise LockValidationFailure("TRIAL_PLAN_MISMATCH", "scientific/formal planned counts differ")
    if formal["condition"] != scientific["condition"]:
        raise LockValidationFailure("TRIAL_PLAN_MISMATCH", "scientific/formal condition differs")
    if formal["allowed_backends"] != scientific["allowed_backends"]:
        raise LockValidationFailure("TRIAL_PLAN_MISMATCH", "scientific/formal allowed backends differ")
    if formal["forbidden_backends"] != scientific["forbidden_backends"]:
        raise LockValidationFailure("TRIAL_PLAN_MISMATCH", "scientific/formal forbidden backends differ")
    if formal["formal_execution_authorized"] is not True:
        raise LockValidationFailure("FORMAL_RUN_LOCK_INVALID", "formal execution is not authorized")
    audit.mark("trial_plan_and_authorization_verified")

    # 16: environment/worktree validation. Only after this may cache be read.
    environment = _validate_environment(repository) if require_environment else {"validation_skipped_for_test": True}
    audit.mark("environment_verified")
    return {
        "binding": binding,
        "environment": environment,
        "formal": formal,
        "implementation": implementation,
        "plans": plans,
        "scientific": scientific,
        "snapshot": snapshot,
        "trace": audit,
    }


def _verify_snapshot_files(directory: Path, expected_id: str, trace: ValidationTrace) -> None:
    expected_names = {
        "metadata.json", "source_points.npy", "target_points.npy", "reference_pose.npy",
        "source_parent_target_indices.npy",
    }
    if not directory.is_dir() or {item.name for item in directory.iterdir()} != expected_names:
        raise LockValidationFailure("SNAPSHOT_LOCK_INVALID", f"cache file set: {expected_id}")
    metadata = _json(directory / "metadata.json", "SNAPSHOT_LOCK_INVALID")
    trace.cache_read_count += 1
    payload = dict(metadata)
    stored = payload.pop("metadata_payload_sha256", None)
    if stored != canonical_json_sha256(payload) or metadata.get("snapshot_id") != expected_id:
        raise LockValidationFailure("SNAPSHOT_LOCK_INVALID", f"cache metadata: {expected_id}")
    hashes = metadata.get("array_file_sha256", {})
    for name in sorted(expected_names - {"metadata.json"}):
        if file_sha256(directory / name) != hashes.get(name):
            raise LockValidationFailure("SNAPSHOT_LOCK_INVALID", f"cache array SHA: {expected_id}/{name}")


def dry_run_phase_a_v2(
    *, root: str | Path, formal_run_lock: str | Path, run_id: str,
    output_dir: str | Path, workers: int,
) -> dict[str, Any]:
    if not run_id or int(workers) < 1:
        raise ValueError("run ID and positive worker count are required")
    repository = Path(root).resolve()
    trace = ValidationTrace()
    stack = validate_lock_stack(root=repository, formal_run_lock=formal_run_lock, trace=trace)
    cache_root = repository / str(stack["binding"]["stage0_cache_root"])
    for row in stack["plans"]["snapshots"]:
        identifier = str(row["snapshot_id"])
        _verify_snapshot_files(snapshot_directory(cache_root, identifier), identifier, trace)
    trials = stack["plans"]["trials"]
    open3d_count = sum(row["backend"] == OPEN3D_PLAN_BACKEND for row in trials)
    pcl_count = sum(row["backend"] == PCL_PLAN_BACKEND for row in trials)
    native_count = sum(row["backend"] in NATIVE_BACKENDS for row in trials)
    return {
        "ATTEMPT_STARTED_COUNT": trace.attempt_started_count,
        "FORMAL_BACKEND_EXECUTION_COUNT": trace.backend_execution_count,
        "FORMAL_DRY_RUN_PASS": (
            trace.cache_read_count == 210 and len(trials) == 420
            and open3d_count == 210 and pcl_count == 210 and native_count == 0
            and trace.formal_seed_access_count == 0 and trace.backend_execution_count == 0
            and trace.trial_result_count == 0 and trace.attempt_started_count == 0
        ),
        "FORMAL_SEED_ACCESS_COUNT": trace.formal_seed_access_count,
        "FORMAL_TRIAL_RESULT_COUNT": trace.trial_result_count,
        "IMPLEMENTATION_LOCK_VERIFICATION": "PASS",
        "NATIVE_EXECUTION_COUNT": trace.backend_execution_count if native_count else 0,
        "PLANNED_NATIVE_TRIAL_COUNT": native_count,
        "PLANNED_OPEN3D_TRIAL_COUNT": open3d_count,
        "PLANNED_PCL_TRIAL_COUNT": pcl_count,
        "PLANNED_SNAPSHOT_COUNT": len(stack["plans"]["snapshots"]),
        "PLANNED_TRIAL_COUNT": len(trials),
        "SCIENTIFIC_LOCK_VERIFICATION": "PASS",
        "SNAPSHOT_CACHE_SHA_VERIFICATION_COUNT": trace.cache_read_count,
        "SNAPSHOT_LOCK_VERIFICATION": "PASS",
        "FORMAL_RUN_LOCK_VERIFICATION": "PASS",
        "output_dir": str(Path(output_dir).resolve()),
        "run_id": run_id,
        "schema_version": "backend_phase_a_v2_dry_run_v1",
        "validation_steps": trace.steps,
        "workers": int(workers),
    }


def execute_fixture_audit_trials_v2(**kwargs: Any) -> dict[str, Any]:
    """Fixture-only qualification path through the v2 engine boundary."""

    result = execute_fixture_audit_trials(**kwargs)
    return {**result, "execution_engine": "backend_phase_a_v2"}


def execute_phase_a_v2(
    *, root: str | Path, formal_run_lock: str | Path, run_id: str,
    output_dir: str | Path, workers: int, resume: bool,
) -> dict[str, Any]:
    """Execute a future authorized formal matrix without consulting the legacy lock."""

    repository = Path(root).resolve()
    trace = ValidationTrace()
    stack = validate_lock_stack(root=repository, formal_run_lock=formal_run_lock, trace=trace)
    run_root = Path(output_dir).resolve() / run_id
    if run_root.exists() and not resume:
        raise FileExistsError("formal output exists; use --resume")
    run_root.mkdir(parents=True, exist_ok=True)
    result_dir = run_root / "raw_results"
    manifest_path = run_root / "raw_result_manifest.json"
    manifest = _json(manifest_path, "FORMAL_RUN_LOCK_INVALID") if manifest_path.exists() else {
        "results": {}, "run_id": run_id, "schema_version": "phase_a_raw_result_manifest_v1"
    }
    trials_by_snapshot: dict[str, list[dict[str, str]]] = {}
    for row in stack["plans"]["trials"]:
        trials_by_snapshot.setdefault(str(row["snapshot_id"]), []).append(row)
    cache_root = repository / str(stack["binding"]["stage0_cache_root"])
    snapshot_lock_sha = stack["formal"]["snapshot_lock_sha256"]
    implementation_sha = stack["implementation"]["implementation_payload_sha256"]
    completed: list[str] = []
    resumed_ids: list[str] = []
    failed: list[str] = []
    for plan in stack["plans"]["snapshots"]:
        snapshot_id = str(plan["snapshot_id"])
        directory = snapshot_directory(cache_root, snapshot_id)
        _verify_snapshot_files(directory, snapshot_id, trace)
        import numpy as np
        metadata = _json(directory / "metadata.json", "SNAPSHOT_LOCK_INVALID")
        fixture = FixtureSnapshot(
            snapshot_id=snapshot_id,
            scene_variant=str(plan["scene_variant"]),
            condition=str(plan["condition"]),
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
        for trial in trials_by_snapshot[snapshot_id]:
            plan_backend = str(trial["backend"])
            backend = OPEN3D_BACKEND if plan_backend == OPEN3D_PLAN_BACKEND else PCL_BACKEND
            trial_id = str(trial["planned_trial_id"])
            common = {
                "backend": backend,
                "condition": fixture.condition,
                "implementation_sha256": implementation_sha,
                "planned_trial_id": trial_id,
                "protocol_sha256": stack["formal"]["scientific_protocol_lock_sha256"],
                "reference_pose_checksum": fixture.checksums["reference_pose_checksum"],
                "scene_variant": fixture.scene_variant,
                "schema_version": SCHEMA_VERSION,
                "snapshot_checksum": fixture.checksums["snapshot_checksum"],
                "snapshot_id": snapshot_id,
                "snapshot_lock_sha256": snapshot_lock_sha,
                "source_checksum": fixture.checksums["source_checksum"],
                "target_checksum": fixture.checksums["target_checksum"],
            }
            result_path = result_dir / result_filename(trial_id)
            if result_path.exists():
                if not resume:
                    raise FileExistsError(f"trial exists without --resume: {trial_id}")
                payload = validate_existing_trial_result_for_resume(
                    result_path, manifest_entry=manifest["results"].get(trial_id), expected=common
                )
                resumed_ids.append(trial_id)
                append_attempt_event(run_root / "attempt_events.ndjson", planned_trial_id=trial_id,
                    snapshot_id=snapshot_id, backend=backend, event_type="SKIPPED_VALID_RESULT", detail=None)
            else:
                append_attempt_event(run_root / "attempt_events.ndjson", planned_trial_id=trial_id,
                    snapshot_id=snapshot_id, backend=backend, event_type="STARTED", detail=None)
                trace.attempt_started_count += 1
                parameters = stack["scientific"]["backend_parameters"][plan_backend]
                payload = execute_open3d_fixture(fixture=fixture, common=common, parameters=parameters) if backend == OPEN3D_BACKEND else execute_pcl_fixture(
                    fixture=fixture, common=common, parameters=parameters,
                    pcl_cli=repository / "build/pcl_point_to_plane_v3/pcl_point_to_plane_cli")
                path, digest = write_phase_a_trial_result(result_dir, payload)
                manifest["results"][trial_id] = {"path": path.name, "planned_trial_id": trial_id, "sha256": digest}
                atomic_write_bytes(manifest_path, canonical_json_bytes(manifest), replace=manifest_path.exists())
                append_attempt_event(run_root / "attempt_events.ndjson", planned_trial_id=trial_id,
                    snapshot_id=snapshot_id, backend=backend, event_type="COMPLETED", detail=None)
                trace.backend_execution_count += 1
                trace.trial_result_count += 1
            completed.append(trial_id)
            if payload["solver_failure"]:
                failed.append(trial_id)
    output = {
        "backend_execution_count": trace.backend_execution_count,
        "completed_trial_ids": completed,
        "failed_trial_ids": failed,
        "resumed_trial_ids": resumed_ids,
        "run_id": run_id,
        "schema_version": "backend_phase_a_v2_stage1_run_manifest_v1",
        "snapshot_generation_count": 0,
        "snapshot_lock_sha256": snapshot_lock_sha,
        "trial_result_count": trace.trial_result_count,
        "trial_result_schema_version": SCHEMA_VERSION,
    }
    atomic_write_bytes(run_root / "run_manifest.json", canonical_json_bytes(output), replace=resume)
    return output


__all__ = [
    "LockValidationFailure",
    "ValidationTrace",
    "dry_run_phase_a_v2",
    "execute_fixture_audit_trials_v2",
    "execute_phase_a_v2",
    "validate_lock_stack",
]
