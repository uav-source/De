"""Seed-free, real-write runtime lifecycle qualification fixture.

This is an execution-contract qualification, not a Confirmatory experiment.
It materializes only the three long-standing deterministic fixture snapshots,
executes the two frozen qualified backends, and keeps every mutable byte below
an externally validated runtime root.  No Confirmatory seed or plan is read.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from .contracts import file_sha256
from .phase_a_execution_chain_audit import (
    execute_open3d_fixture,
    execute_pcl_fixture,
)
from .phase_a_execution_chain_fixture import FixtureSnapshot, build_fixture_snapshots
from .phase_a_trial_result_schema import (
    OPEN3D_BACKEND,
    PCL_BACKEND,
    canonical_json_bytes as trial_json_bytes,
    load_json_strict,
    validate_phase_a_trial_result_strict,
)
from .phase_a_trial_result_writer import result_filename
from .phase_a_trial_resume import (
    CorruptExistingResult,
    validate_existing_trial_result_for_resume,
)
from .runtime_lifecycle_io import (
    SingleWriterLease,
    append_event_v2,
    atomic_create_bytes,
    atomic_create_canonical_json,
    atomic_publish_directory,
    atomic_replace_canonical_json,
    canonical_json_sha256,
    read_canonical_json,
    read_event_journal_v2,
    write_once_immutable_run_lock,
)
from .runtime_path_policy import RuntimePathLayout


RUN_CONTRACT_SCHEMA = "runtime_lifecycle_fixture_run_contract_v1"
SNAPSHOT_METADATA_SCHEMA = "runtime_lifecycle_fixture_snapshot_v1"
RAW_MANIFEST_SCHEMA = "runtime_lifecycle_fixture_raw_result_manifest_v1"
RUN_REPORT_SCHEMA = "runtime_lifecycle_fixture_execution_report_v1"
BACKENDS = (OPEN3D_BACKEND, PCL_BACKEND)
EXPECTED_SNAPSHOT_COUNT = 3
EXPECTED_TRIAL_COUNT = 6


class RuntimeLifecycleCorruption(RuntimeError):
    """A pre-existing runtime object failed its immutable binding."""

    classification = "CORRUPT_OR_TAMPERED_RUNTIME_OBJECT"


def _strict_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = read_canonical_json(path)
    except (OSError, ValueError) as error:
        raise RuntimeLifecycleCorruption(f"invalid {label}: {path}") from error
    if type(value) is not dict:
        raise RuntimeLifecycleCorruption(f"{label} must be a JSON object")
    return value


def _raw_array_sha256(value: np.ndarray) -> str:
    array = np.asarray(value)
    if not array.flags.c_contiguous:
        raise RuntimeLifecycleCorruption("snapshot array is not C-contiguous")
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_npy(path: Path, value: np.ndarray) -> None:
    with path.open("xb") as stream:
        np.save(stream, value, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())


def _snapshot_token(snapshot_id: str) -> str:
    token = snapshot_id.rsplit("/", 1)[-1]
    if not token or token in {".", ".."} or "/" in token:
        raise ValueError("unsafe fixture snapshot ID")
    return token


def _lineage_expected(fixture: FixtureSnapshot) -> bool:
    return fixture.condition in {
        "FIXTURE_IDENTITY",
        "FIXTURE_NONIDENTITY_REFERENCE",
    }


def _planned_trials(fixtures: Sequence[FixtureSnapshot]) -> list[dict[str, str]]:
    return [
        {
            "backend": backend,
            "condition": fixture.condition,
            "planned_trial_id": f"{fixture.snapshot_id}/{backend}",
            "snapshot_id": fixture.snapshot_id,
        }
        for fixture in fixtures
        for backend in BACKENDS
    ]


def build_fixture_run_contract(
    *,
    repository: str | Path,
    layout: RuntimePathLayout,
    run_id: str,
    workers: int,
    expected_commit: str,
    expected_branch: str,
    expected_tag: str,
    runtime_path_policy_sha256: str,
    qualification_delay_seconds: float,
) -> dict[str, Any]:
    root = Path(repository).resolve()
    if run_id != layout.run_id:
        raise ValueError("run ID differs from runtime path layout")
    if isinstance(workers, bool) or not isinstance(workers, int) or workers <= 0:
        raise ValueError("workers must be a positive integer")
    if qualification_delay_seconds < 0.0:
        raise ValueError("qualification delay must be nonnegative")
    fixtures = build_fixture_snapshots()
    manifest = json.loads(
        (root / "frozen_assets/frozen_experiment_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    return {
        "schema_version": RUN_CONTRACT_SCHEMA,
        "fixture_only": True,
        "formal_confirmatory_science_evaluated": False,
        "formal_seed_values_included": False,
        "fixture_generation_rng_count": 0,
        "run_id": run_id,
        "workers": workers,
        "expected_commit": expected_commit,
        "expected_branch": expected_branch,
        "expected_tag": expected_tag,
        "runtime_paths": layout.as_dict(),
        "runtime_path_policy_sha256": runtime_path_policy_sha256,
        "qualification_delay_seconds": float(qualification_delay_seconds),
        "fixture_plan_path": "frozen_assets/fixtures/fixture_plan.json",
        "fixture_plan_sha256": file_sha256(
            root / "frozen_assets/fixtures/fixture_plan.json"
        ),
        "fixture_snapshot_lock_path": (
            "frozen_assets/fixtures/fixture_snapshot_lock.json"
        ),
        "fixture_snapshot_lock_sha256": file_sha256(
            root / "frozen_assets/fixtures/fixture_snapshot_lock.json"
        ),
        "fixture_backend_parameter_lock_path": (
            "frozen_assets/fixtures/fixture_backend_parameter_lock.json"
        ),
        "fixture_backend_parameter_lock_sha256": file_sha256(
            root / "frozen_assets/fixtures/fixture_backend_parameter_lock.json"
        ),
        "implementation_sha256": manifest["manifest_payload_sha256"],
        "pcl_cli_path": "bin/pcl_point_to_plane_cli",
        "pcl_cli_sha256": file_sha256(root / "bin/pcl_point_to_plane_cli"),
        "planned_snapshots": [
            {
                "condition": item.condition,
                "expected_failure_classifications": list(
                    item.expected_failure_classifications
                ),
                "lineage_sidecar_required": _lineage_expected(item),
                "reference_pose_checksum": item.checksums[
                    "reference_pose_checksum"
                ],
                "scene_variant": item.scene_variant,
                "snapshot_checksum": item.checksums["snapshot_checksum"],
                "snapshot_id": item.snapshot_id,
                "source_checksum": item.checksums["source_checksum"],
                "target_checksum": item.checksums["target_checksum"],
            }
            for item in fixtures
        ],
        "planned_trials": _planned_trials(fixtures),
    }


def _snapshot_metadata(
    fixture: FixtureSnapshot, file_hashes: Mapping[str, str]
) -> dict[str, Any]:
    unsigned = {
        "schema_version": SNAPSHOT_METADATA_SCHEMA,
        "fixture_only": True,
        "formal_confirmatory_science_evaluated": False,
        "random_seed_used": False,
        "condition": fixture.condition,
        "scene_variant": fixture.scene_variant,
        "snapshot_id": fixture.snapshot_id,
        "checksums": dict(fixture.checksums),
        "file_sha256": dict(sorted(file_hashes.items())),
        "lineage_sidecar_required": _lineage_expected(fixture),
    }
    return {**unsigned, "metadata_payload_sha256": canonical_json_sha256(unsigned)}


def _populate_snapshot(directory: Path, fixture: FixtureSnapshot) -> None:
    paths = {
        "source_points.npy": fixture.source,
        "target_points.npy": fixture.target,
        "reference_pose.npy": fixture.reference,
    }
    for name, value in paths.items():
        _write_npy(directory / name, value)
    if _lineage_expected(fixture):
        indices = np.arange(len(fixture.source), dtype="<i8")
        _write_npy(directory / "source_parent_target_indices.npy", indices)
    hashes = {
        path.name: file_sha256(path)
        for path in sorted(directory.iterdir(), key=lambda item: item.name)
    }
    atomic_create_canonical_json(
        directory / "metadata.json", _snapshot_metadata(fixture, hashes)
    )


def _expected_snapshot_files(fixture: FixtureSnapshot) -> set[str]:
    result = {
        "metadata.json",
        "reference_pose.npy",
        "source_points.npy",
        "target_points.npy",
    }
    if _lineage_expected(fixture):
        result.add("source_parent_target_indices.npy")
    return result


def validate_runtime_snapshot(
    snapshot_dir: str | Path, fixture: FixtureSnapshot
) -> FixtureSnapshot:
    root = Path(snapshot_dir)
    if root.is_symlink() or not root.is_dir():
        raise RuntimeLifecycleCorruption("snapshot directory is missing or a symlink")
    inventory = list(root.iterdir())
    if any(path.is_symlink() or not path.is_file() for path in inventory):
        raise RuntimeLifecycleCorruption("snapshot inventory contains unsafe entries")
    actual = {path.name for path in inventory}
    expected = _expected_snapshot_files(fixture)
    if actual != expected:
        raise RuntimeLifecycleCorruption(
            f"snapshot inventory mismatch: missing={sorted(expected-actual)}, "
            f"extra={sorted(actual-expected)}"
        )
    metadata = _strict_object(root / "metadata.json", "snapshot metadata")
    recorded_payload = metadata.get("metadata_payload_sha256")
    unsigned = {
        key: value for key, value in metadata.items() if key != "metadata_payload_sha256"
    }
    if recorded_payload != canonical_json_sha256(unsigned):
        raise RuntimeLifecycleCorruption("snapshot metadata payload SHA mismatch")
    expected_identity = {
        "schema_version": SNAPSHOT_METADATA_SCHEMA,
        "fixture_only": True,
        "formal_confirmatory_science_evaluated": False,
        "random_seed_used": False,
        "condition": fixture.condition,
        "scene_variant": fixture.scene_variant,
        "snapshot_id": fixture.snapshot_id,
        "checksums": dict(fixture.checksums),
        "lineage_sidecar_required": _lineage_expected(fixture),
    }
    if any(metadata.get(name) != value for name, value in expected_identity.items()):
        raise RuntimeLifecycleCorruption("snapshot metadata identity mismatch")
    file_hashes = metadata.get("file_sha256")
    expected_hash_names = expected - {"metadata.json"}
    if type(file_hashes) is not dict or set(file_hashes) != expected_hash_names:
        raise RuntimeLifecycleCorruption("snapshot file-SHA inventory mismatch")
    for name, expected_sha in file_hashes.items():
        if file_sha256(root / name) != expected_sha:
            raise RuntimeLifecycleCorruption(f"snapshot file SHA mismatch: {name}")
    try:
        source = np.load(root / "source_points.npy", allow_pickle=False)
        target = np.load(root / "target_points.npy", allow_pickle=False)
        reference = np.load(root / "reference_pose.npy", allow_pickle=False)
    except (OSError, ValueError) as error:
        raise RuntimeLifecycleCorruption("snapshot array load failed") from error
    arrays = {
        "source_checksum": source,
        "target_checksum": target,
        "reference_pose_checksum": reference,
    }
    for name, value in arrays.items():
        if _raw_array_sha256(value) != fixture.checksums[name]:
            raise RuntimeLifecycleCorruption(f"snapshot scientific checksum mismatch: {name}")
    if not (
        np.array_equal(source, fixture.source)
        and np.array_equal(target, fixture.target)
        and np.array_equal(reference, fixture.reference)
    ):
        raise RuntimeLifecycleCorruption("snapshot scientific array changed")
    if _lineage_expected(fixture):
        try:
            lineage = np.load(
                root / "source_parent_target_indices.npy", allow_pickle=False
            )
        except (OSError, ValueError) as error:
            raise RuntimeLifecycleCorruption("lineage sidecar load failed") from error
        if (
            lineage.dtype != np.dtype("<i8")
            or lineage.shape != (len(source),)
            or not np.array_equal(lineage, np.arange(len(source), dtype="<i8"))
        ):
            raise RuntimeLifecycleCorruption("lineage sidecar identity mismatch")
        reconstructed = (
            (reference[:3, :3] @ source.astype(np.float64).T).T
            + reference[:3, 3]
        ).astype("<f4")
        if not np.array_equal(reconstructed, target[lineage]):
            raise RuntimeLifecycleCorruption("lineage reconstruction mismatch")
    return FixtureSnapshot(
        snapshot_id=fixture.snapshot_id,
        scene_variant=fixture.scene_variant,
        condition=fixture.condition,
        source=source,
        target=target,
        reference=reference,
        expected_failure_classifications=fixture.expected_failure_classifications,
        checksums=dict(fixture.checksums),
    )


def prepare_runtime_snapshots(
    *,
    layout: RuntimePathLayout,
    after_commit: Callable[[str, int], None] | None = None,
) -> dict[str, Any]:
    layout.snapshot_cache.mkdir(parents=True, exist_ok=True)
    fixtures = build_fixture_snapshots()
    generated: list[str] = []
    skipped: list[str] = []
    for fixture in fixtures:
        destination = layout.snapshot_cache / _snapshot_token(fixture.snapshot_id)
        if destination.exists() or destination.is_symlink():
            validate_runtime_snapshot(destination, fixture)
            skipped.append(fixture.snapshot_id)
            continue
        atomic_publish_directory(
            destination,
            lambda staging, item=fixture: _populate_snapshot(staging, item),
        )
        validate_runtime_snapshot(destination, fixture)
        generated.append(fixture.snapshot_id)
        if after_commit is not None:
            after_commit(fixture.snapshot_id, len(generated))
    validate_all_runtime_snapshots(layout)
    return {
        "generated_snapshot_ids": generated,
        "generated_snapshot_count": len(generated),
        "resume_skipped_valid_snapshot_ids": skipped,
        "resume_skipped_valid_snapshot_count": len(skipped),
    }


def validate_all_runtime_snapshots(
    layout: RuntimePathLayout,
) -> tuple[FixtureSnapshot, ...]:
    fixtures = build_fixture_snapshots()
    expected_names = {_snapshot_token(item.snapshot_id) for item in fixtures}
    if not layout.snapshot_cache.is_dir() or layout.snapshot_cache.is_symlink():
        raise RuntimeLifecycleCorruption("snapshot cache is missing or unsafe")
    actual = {path.name for path in layout.snapshot_cache.iterdir()}
    if actual != expected_names:
        raise RuntimeLifecycleCorruption("snapshot cache reverse inventory mismatch")
    return tuple(
        validate_runtime_snapshot(
            layout.snapshot_cache / _snapshot_token(item.snapshot_id), item
        )
        for item in fixtures
    )


def _raw_paths(layout: RuntimePathLayout) -> tuple[Path, Path]:
    return layout.raw_results / "results", layout.raw_results / "raw_result_manifest.json"


def _empty_raw_manifest(run_id: str, contract_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": RAW_MANIFEST_SCHEMA,
        "run_id": run_id,
        "run_contract_sha256": contract_sha256,
        "results": {},
    }


def _read_raw_manifest(
    path: Path, *, run_id: str, contract_sha256: str
) -> dict[str, Any]:
    value = _strict_object(path, "raw result manifest")
    if (
        set(value)
        != {"schema_version", "run_id", "run_contract_sha256", "results"}
        or value.get("schema_version") != RAW_MANIFEST_SCHEMA
        or value.get("run_id") != run_id
        or value.get("run_contract_sha256") != contract_sha256
        or type(value.get("results")) is not dict
    ):
        raise RuntimeLifecycleCorruption("raw result manifest contract mismatch")
    return value


def _trial_common(
    repository: Path,
    fixture: FixtureSnapshot,
    backend: str,
    implementation_sha256: str,
) -> dict[str, Any]:
    return {
        "backend": backend,
        "condition": fixture.condition,
        "implementation_sha256": implementation_sha256,
        "planned_trial_id": f"{fixture.snapshot_id}/{backend}",
        "protocol_sha256": file_sha256(
            repository / "frozen_assets/fixtures/fixture_plan.json"
        ),
        "reference_pose_checksum": fixture.checksums["reference_pose_checksum"],
        "scene_variant": fixture.scene_variant,
        "schema_version": "phase_a_trial_result_v1",
        "snapshot_checksum": fixture.checksums["snapshot_checksum"],
        "snapshot_id": fixture.snapshot_id,
        "snapshot_lock_sha256": file_sha256(
            repository / "frozen_assets/fixtures/fixture_snapshot_lock.json"
        ),
        "source_checksum": fixture.checksums["source_checksum"],
        "target_checksum": fixture.checksums["target_checksum"],
    }


def _expected_trials(
    repository: Path,
    fixtures: Sequence[FixtureSnapshot],
    implementation_sha256: str,
) -> dict[str, tuple[FixtureSnapshot, str, dict[str, Any]]]:
    return {
        common["planned_trial_id"]: (fixture, backend, common)
        for fixture in fixtures
        for backend in BACKENDS
        for common in (
            _trial_common(repository, fixture, backend, implementation_sha256),
        )
    }


def _validate_result_entry(
    *,
    path: Path,
    entry: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        value = validate_existing_trial_result_for_resume(
            path, manifest_entry=entry, expected=expected
        )
    except (OSError, ValueError, CorruptExistingResult) as error:
        raise RuntimeLifecycleCorruption(
            f"trial result failed strict resume validation: {path.name}"
        ) from error
    if path.read_bytes() != trial_json_bytes(value):
        raise RuntimeLifecycleCorruption("trial result JSON is not canonical")
    return value


def audit_runtime_results(
    *,
    repository: str | Path,
    layout: RuntimePathLayout,
    run_id: str,
    contract_sha256: str,
    implementation_sha256: str,
    allow_orphans: bool = False,
) -> dict[str, Any]:
    root = Path(repository).resolve()
    fixtures = validate_all_runtime_snapshots(layout)
    expected = _expected_trials(root, fixtures, implementation_sha256)
    results_dir, manifest_path = _raw_paths(layout)
    manifest = _read_raw_manifest(
        manifest_path, run_id=run_id, contract_sha256=contract_sha256
    )
    manifest_ids = set(manifest["results"])
    expected_ids = set(expected)
    rows: list[dict[str, Any]] = []
    referenced: set[str] = set()
    for trial_id in sorted(manifest_ids & expected_ids):
        entry = manifest["results"][trial_id]
        if type(entry) is not dict or set(entry) != {
            "path",
            "planned_trial_id",
            "sha256",
        }:
            raise RuntimeLifecycleCorruption("raw result entry schema mismatch")
        filename = result_filename(trial_id)
        if (
            entry.get("planned_trial_id") != trial_id
            or entry.get("path") != filename
        ):
            raise RuntimeLifecycleCorruption("raw result entry identity mismatch")
        path = results_dir / filename
        if path.is_symlink() or not path.is_file():
            raise RuntimeLifecycleCorruption("raw result path is missing or unsafe")
        if file_sha256(path) != entry.get("sha256"):
            raise RuntimeLifecycleCorruption("raw result SHA mismatch")
        rows.append(
            _validate_result_entry(path=path, entry=entry, expected=expected[trial_id][2])
        )
        referenced.add(filename)
    actual_files: set[str] = set()
    if results_dir.exists():
        if results_dir.is_symlink() or not results_dir.is_dir():
            raise RuntimeLifecycleCorruption("raw results directory is unsafe")
        for path in results_dir.iterdir():
            if path.is_symlink() or not path.is_file():
                raise RuntimeLifecycleCorruption("raw results inventory is unsafe")
            actual_files.add(path.name)
    orphans = sorted(actual_files - referenced)
    extra_ids = sorted(manifest_ids - expected_ids)
    missing_ids = sorted(expected_ids - manifest_ids)
    if extra_ids or (orphans and not allow_orphans):
        raise RuntimeLifecycleCorruption("raw result reverse inventory mismatch")
    return {
        "manifest": manifest,
        "rows": rows,
        "missing_trial_ids": missing_ids,
        "extra_trial_ids": extra_ids,
        "orphan_result_files": orphans,
        "duplicate_trial_count": len(rows) - len({row["planned_trial_id"] for row in rows}),
        "checksum_mismatch_count": 0,
        "corrupt_trial_count": 0,
    }


def recover_canonical_result_orphans(
    *,
    repository: str | Path,
    layout: RuntimePathLayout,
    run_id: str,
    contract_sha256: str,
    implementation_sha256: str,
) -> dict[str, Any]:
    root = Path(repository).resolve()
    fixtures = validate_all_runtime_snapshots(layout)
    expected = _expected_trials(root, fixtures, implementation_sha256)
    report = audit_runtime_results(
        repository=root,
        layout=layout,
        run_id=run_id,
        contract_sha256=contract_sha256,
        implementation_sha256=implementation_sha256,
        allow_orphans=True,
    )
    results_dir, manifest_path = _raw_paths(layout)
    manifest = report["manifest"]
    missing = set(report["missing_trial_ids"])
    filename_to_id = {result_filename(trial_id): trial_id for trial_id in missing}
    recovered: list[str] = []
    for filename in report["orphan_result_files"]:
        trial_id = filename_to_id.get(filename)
        if trial_id is None:
            raise RuntimeLifecycleCorruption(f"unrecognized result orphan: {filename}")
        path = results_dir / filename
        entry = {
            "path": filename,
            "planned_trial_id": trial_id,
            "sha256": file_sha256(path),
        }
        _validate_result_entry(path=path, entry=entry, expected=expected[trial_id][2])
        manifest["results"][trial_id] = entry
        recovered.append(trial_id)
    if recovered:
        atomic_replace_canonical_json(manifest_path, manifest)
    return {
        "recovered_orphan_result_count": len(recovered),
        "recovered_orphan_trial_ids": sorted(recovered),
    }


def execute_runtime_trials(
    *,
    repository: str | Path,
    layout: RuntimePathLayout,
    run_id: str,
    invocation_id: str,
    contract_sha256: str,
    implementation_sha256: str,
    resume: bool,
    after_commit: Callable[[str, int], None] | None = None,
) -> dict[str, Any]:
    root = Path(repository).resolve()
    fixtures = validate_all_runtime_snapshots(layout)
    expected = _expected_trials(root, fixtures, implementation_sha256)
    results_dir, manifest_path = _raw_paths(layout)
    layout.raw_results.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    if not manifest_path.exists():
        atomic_create_canonical_json(
            manifest_path, _empty_raw_manifest(run_id, contract_sha256)
        )
    elif not resume:
        raise FileExistsError("raw result manifest exists without resume")
    recovered = recover_canonical_result_orphans(
        repository=root,
        layout=layout,
        run_id=run_id,
        contract_sha256=contract_sha256,
        implementation_sha256=implementation_sha256,
    )
    inventory = audit_runtime_results(
        repository=root,
        layout=layout,
        run_id=run_id,
        contract_sha256=contract_sha256,
        implementation_sha256=implementation_sha256,
    )
    manifest = inventory["manifest"]
    parameter_lock = json.loads(
        (root / "frozen_assets/fixtures/fixture_backend_parameter_lock.json").read_text(
            encoding="utf-8"
        )
    )
    pcl_cli = root / "bin/pcl_point_to_plane_cli"
    layout.backend_temporary.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(layout.backend_temporary)
    layout.attempt_events.mkdir(parents=True, exist_ok=True)
    events_path = layout.attempt_events / "events.ndjson"
    completed: list[str] = []
    executed: list[str] = []
    skipped: list[str] = []
    executions = 0
    open3d_seed_calls = 0
    for fixture in fixtures:
        for backend in BACKENDS:
            trial_id = f"{fixture.snapshot_id}/{backend}"
            common = expected[trial_id][2]
            existing = manifest["results"].get(trial_id)
            path = results_dir / result_filename(trial_id)
            if existing is not None:
                _validate_result_entry(path=path, entry=existing, expected=common)
                append_event_v2(
                    events_path,
                    run_id=run_id,
                    invocation_id=invocation_id,
                    event_type="SKIPPED_VALID_RESULT",
                    planned_trial_id=trial_id,
                    backend=backend,
                    result_sha256=existing["sha256"],
                )
                skipped.append(trial_id)
                completed.append(trial_id)
                continue
            append_event_v2(
                events_path,
                run_id=run_id,
                invocation_id=invocation_id,
                event_type="STARTED",
                planned_trial_id=trial_id,
                backend=backend,
            )
            if backend == OPEN3D_BACKEND:
                result = execute_open3d_fixture(
                    fixture=fixture,
                    common=common,
                    parameters=parameter_lock["open3d_parameter_contract"]["parameters"],
                )
                open3d_seed_calls += 1
            elif backend == PCL_BACKEND:
                result = execute_pcl_fixture(
                    fixture=fixture,
                    common=common,
                    parameters=parameter_lock["pcl_parameter_contract"]["parameters"],
                    pcl_cli=pcl_cli,
                )
            else:  # pragma: no cover - frozen tuple protects this branch
                raise PermissionError("Native and unknown backends are forbidden")
            payload = validate_phase_a_trial_result_strict(result)
            atomic_create_bytes(path, trial_json_bytes(payload))
            digest = file_sha256(path)
            manifest["results"][trial_id] = {
                "path": path.name,
                "planned_trial_id": trial_id,
                "sha256": digest,
            }
            atomic_replace_canonical_json(manifest_path, manifest)
            append_event_v2(
                events_path,
                run_id=run_id,
                invocation_id=invocation_id,
                event_type="COMPLETED",
                planned_trial_id=trial_id,
                backend=backend,
                result_sha256=digest,
            )
            executions += 1
            executed.append(trial_id)
            completed.append(trial_id)
            if after_commit is not None:
                after_commit(trial_id, executions)
    final = audit_runtime_results(
        repository=root,
        layout=layout,
        run_id=run_id,
        contract_sha256=contract_sha256,
        implementation_sha256=implementation_sha256,
    )
    if final["missing_trial_ids"] or len(final["rows"]) != EXPECTED_TRIAL_COUNT:
        raise RuntimeError("fixture trial matrix is incomplete")
    events = read_event_journal_v2(events_path, expected_run_id=run_id)
    return {
        "backend_execution_count_this_invocation": executions,
        "backend_determinism_seed_call_count_this_invocation": open3d_seed_calls,
        "executed_trial_ids": executed,
        "completed_trial_ids": completed,
        "resume_skipped_valid_result_count": len(skipped),
        "resumed_trial_ids": skipped,
        "recovered_orphan_result_count": recovered[
            "recovered_orphan_result_count"
        ],
        "event_count": len(events),
        "rows": final["rows"],
        "raw_result_manifest_sha256": file_sha256(manifest_path),
    }


def load_completed_fixture_results(
    *,
    repository: str | Path,
    layout: RuntimePathLayout,
    run_id: str,
    contract_sha256: str,
    implementation_sha256: str,
) -> list[dict[str, Any]]:
    report = audit_runtime_results(
        repository=repository,
        layout=layout,
        run_id=run_id,
        contract_sha256=contract_sha256,
        implementation_sha256=implementation_sha256,
    )
    if report["missing_trial_ids"] or len(report["rows"]) != EXPECTED_TRIAL_COUNT:
        raise RuntimeError("fixture results are incomplete")
    return sorted(report["rows"], key=lambda row: row["planned_trial_id"])


def summarize_fixture_outcomes(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    expected = {
        fixture.condition: set(fixture.expected_failure_classifications)
        for fixture in build_fixture_snapshots()
    }
    pairing: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        pairing.setdefault(str(row["snapshot_id"]), []).append(row)
    checksum_fields = (
        "snapshot_checksum",
        "source_checksum",
        "target_checksum",
        "reference_pose_checksum",
    )
    pairing_mismatch = sum(
        len(group) != 2
        or {row["backend"] for row in group} != set(BACKENDS)
        or any(group[0][name] != group[1][name] for name in checksum_fields)
        for group in pairing.values()
    )
    outcome_mismatch = sum(
        row["failure_classification"] not in expected[row["condition"]]
        for row in rows
    )
    return {
        "fixture_snapshot_count": len(pairing),
        "fixture_trial_count": len(rows),
        "backend_trial_counts": dict(
            sorted(Counter(row["backend"] for row in rows).items())
        ),
        "pairing_mismatch_count": pairing_mismatch,
        "outcome_mismatch_count": outcome_mismatch,
        "FIXTURE_EXECUTION_CHAIN_PASS": bool(
            len(pairing) == EXPECTED_SNAPSHOT_COUNT
            and len(rows) == EXPECTED_TRIAL_COUNT
            and pairing_mismatch == 0
            and outcome_mismatch == 0
        ),
    }


def publish_fixture_runtime_artifact(
    *,
    layout: RuntimePathLayout,
    primary: Mapping[str, Any],
    independent: Mapping[str, Any],
    run_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Publish in the external publisher area, then atomically stage a copy.

    The frozen v2 publisher remains byte-for-byte unchanged.  This lifecycle
    wrapper supplies the two external path boundaries required by the repaired
    contract without changing publication semantics or repository state.
    """

    from .synthetic_confirmatory_v2_artifact_verifier import (
        verify_synthetic_confirmatory_v2_fixture_artifact,
    )
    from .synthetic_confirmatory_v2_publisher import (
        publish_synthetic_confirmatory_v2_fixture,
    )

    publisher_output = layout.publisher_staging / "fixture_publication"
    final_artifact = layout.artifact_staging / "fixture_publication"
    publication = publish_synthetic_confirmatory_v2_fixture(
        primary=primary,
        independent=independent,
        run_manifest=run_manifest,
        artifact_dir=publisher_output,
    )
    publisher_verification = verify_synthetic_confirmatory_v2_fixture_artifact(
        publisher_output, write_report=False
    )
    if publisher_verification.get("FIXTURE_ARTIFACT_VERIFICATION_PASS") is not True:
        raise RuntimeLifecycleCorruption("publisher staging verification failed")

    def populate(staging: Path) -> None:
        shutil.copytree(publisher_output, staging, dirs_exist_ok=True)

    atomic_publish_directory(final_artifact, populate)
    final_verification = verify_synthetic_confirmatory_v2_fixture_artifact(
        final_artifact, write_report=False
    )
    if final_verification != publisher_verification:
        raise RuntimeLifecycleCorruption(
            "artifact stage differs from verified publisher staging"
        )
    return {
        **publication,
        "publisher_staging_path": str(publisher_output),
        "artifact_staging_path": str(final_artifact),
        "publisher_staging_verification": publisher_verification,
        "artifact_staging_verification": final_verification,
    }


def run_fixture_lifecycle(
    *,
    repository: str | Path,
    layout: RuntimePathLayout,
    run_id: str,
    invocation_id: str,
    workers: int,
    resume: bool,
    expected_commit: str,
    expected_branch: str,
    expected_tag: str,
    runtime_path_policy_sha256: str,
    qualification_delay_seconds: float = 0.0,
    git_gate: Callable[[str], Mapping[str, Any]] | None = None,
    prebootstrapped_root: bool = False,
    single_writer_lease_path: str | Path | None = None,
) -> dict[str, Any]:
    """Execute snapshots and trials under one immutable external run contract."""

    if type(prebootstrapped_root) is not bool:
        raise TypeError("prebootstrapped_root must be bool")
    if single_writer_lease_path is not None and not prebootstrapped_root:
        raise ValueError(
            "an external single-writer lease is reserved for prebootstrapped runs"
        )
    if single_writer_lease_path is not None:
        expected_external_lease = (
            layout.run_root.parent / f".{layout.run_root.name}.bootstrap.lease"
        )
        supplied_external_lease = Path(
            os.path.abspath(os.fspath(single_writer_lease_path))
        )
        if supplied_external_lease != expected_external_lease:
            raise ValueError("prebootstrapped runs require the exact external lease")
    root = Path(repository).resolve()
    contract = build_fixture_run_contract(
        repository=root,
        layout=layout,
        run_id=run_id,
        workers=workers,
        expected_commit=expected_commit,
        expected_branch=expected_branch,
        expected_tag=expected_tag,
        runtime_path_policy_sha256=runtime_path_policy_sha256,
        qualification_delay_seconds=qualification_delay_seconds,
    )
    contract_sha = canonical_json_sha256(contract)
    if git_gate is not None:
        git_gate("RESUME_GIT_GATE" if resume else "PRE_RUN_GIT_GATE")
    layout.run_root.mkdir(
        parents=True, exist_ok=(resume or prebootstrapped_root)
    )
    lease_path = (
        Path(single_writer_lease_path)
        if single_writer_lease_path is not None
        else layout.run_root / "single_writer.lease"
    )
    with SingleWriterLease(lease_path):
        if git_gate is not None:
            git_gate("POST_LEASE_GIT_GATE")
        lock = write_once_immutable_run_lock(
            layout.snapshot_lock, contract, resume=resume
        )

        def snapshot_commit(_snapshot_id: str, _count: int) -> None:
            if git_gate is not None:
                git_gate("MID_SNAPSHOT_GIT_GATE")
            if qualification_delay_seconds:
                time.sleep(qualification_delay_seconds)

        snapshots = prepare_runtime_snapshots(
            layout=layout, after_commit=snapshot_commit
        )
        if git_gate is not None:
            git_gate("POST_SNAPSHOT_GIT_GATE")

        def trial_commit(_trial_id: str, _count: int) -> None:
            if git_gate is not None:
                git_gate("MID_TRIAL_GIT_GATE")
            if qualification_delay_seconds:
                time.sleep(qualification_delay_seconds)

        trials = execute_runtime_trials(
            repository=root,
            layout=layout,
            run_id=run_id,
            invocation_id=invocation_id,
            contract_sha256=contract_sha,
            implementation_sha256=contract["implementation_sha256"],
            resume=resume,
            after_commit=trial_commit,
        )
        outcomes = summarize_fixture_outcomes(trials["rows"])
        report = {
            "schema_version": RUN_REPORT_SCHEMA,
            "run_id": run_id,
            "invocation_id": invocation_id,
            "resume": resume,
            "workers": workers,
            "runtime_paths": layout.as_dict(),
            "run_contract_sha256": contract_sha,
            "immutable_run_lock_sha256": file_sha256(layout.snapshot_lock),
            "fixture_generation_rng_count": 0,
            "formal_confirmatory_seed_access_count": 0,
            "new_confirmatory_namespace_generation_count": 0,
            "native_execution_count": 0,
            **snapshots,
            **{key: value for key, value in trials.items() if key != "rows"},
            **outcomes,
        }
        layout.temporary_inventory.mkdir(parents=True, exist_ok=True)
        report_path = layout.temporary_inventory / f"{invocation_id}.json"
        atomic_create_canonical_json(report_path, report)
        if git_gate is not None:
            git_gate("POST_TRIAL_GIT_GATE")
        return report


__all__ = [
    "BACKENDS",
    "EXPECTED_SNAPSHOT_COUNT",
    "EXPECTED_TRIAL_COUNT",
    "RAW_MANIFEST_SCHEMA",
    "RUN_CONTRACT_SCHEMA",
    "RUN_REPORT_SCHEMA",
    "RuntimeLifecycleCorruption",
    "audit_runtime_results",
    "build_fixture_run_contract",
    "execute_runtime_trials",
    "load_completed_fixture_results",
    "prepare_runtime_snapshots",
    "publish_fixture_runtime_artifact",
    "recover_canonical_result_orphans",
    "run_fixture_lifecycle",
    "summarize_fixture_outcomes",
    "validate_all_runtime_snapshots",
    "validate_runtime_snapshot",
]
