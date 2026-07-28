"""Phase A v1.1 implementation lock, dry-run, and execution primitives."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import numpy as np
import yaml

from .backend_phase_a_metrics import (
    OPEN3D_BACKEND,
    PCL_BACKEND,
    canonical_backend_inputs,
    source_is_exact_target_subset,
    solver_failure_reasons,
    transform_update,
)
from .backend_phase_a_protocol import (
    PROTOCOL_RELATIVE as V1_PROTOCOL_RELATIVE,
    PROTOCOL_SHA256 as V1_PROTOCOL_SHA256,
    canonical_json_sha256,
    file_sha256,
    load_backend_phase_a_protocol,
)
from .metrics import pose_matrix
from .open3d_backend import run_open3d_full
from .pcl_backend import frozen_parameters, run_pcl_point_to_plane


V1_1_PROTOCOL_RELATIVE = Path("configs/zero_perturbation/backend_phase_a_v1_1.yaml")
V1_1_PROTOCOL_SHA256 = "11ad4ffa1e5303f005fa8dc600627b4a45ce31fc1bae9d8b6bb042f03a8ff27e"
V1_1_DOCUMENT_RELATIVE = Path("docs/zero_perturbation_backend_phase_a_v1_1_protocol.md")
V1_1_DOCUMENT_SHA256 = "012ddea5467d6e3176c652fa8339bca0ce1d4fe6f7605a52c58520efce324216"
V1_1_PROTOCOL_LOCK_TAG = "archive/zero-perturbation-backend-phase-a-v1.1-protocol-lock"
V1_1_LOCK_PASS_TAG = "archive/zero-perturbation-backend-phase-a-v1.1-lock-pass"
V1_PLACEHOLDER_SHA256 = "9b53842e090e69e5d8a2ff5aa5de534c53394401571cbe0b0e20d8c3565fce84"
V1_INVALIDATION_RELATIVE = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_v1_invalidation"
)
V1_1_ARTIFACT_RELATIVE = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_v1_1_lock"
)
DEFAULT_PCL_CLI_RELATIVE = Path("build/pcl_point_to_plane_v3/pcl_point_to_plane_cli")
FORMAL_RESULT_SCHEMA = "backend_phase_a_v1_1_trial_result_v1"
FIXTURE_RESULT_SCHEMA = "backend_phase_a_v1_1_fixture_trial_result_v1"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class RunnerContractError(RuntimeError):
    """Base class for execution-contract refusals."""

    classification = "LOCK_MISMATCH"


class CorruptExistingResult(RunnerContractError):
    classification = "CORRUPT_EXISTING_RESULT"


class DuplicateTrialResult(RunnerContractError):
    classification = "DUPLICATE_TRIAL"


class InfrastructureInterruption(RunnerContractError):
    classification = "INFRASTRUCTURE_INTERRUPTION"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise CorruptExistingResult(f"cannot parse JSON: {path}") from error
    if type(value) is not dict:
        raise CorruptExistingResult(f"JSON root is not an object: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))
    except (OSError, UnicodeError, csv.Error) as error:
        raise RunnerContractError(f"cannot parse planned CSV: {path}") from error


def _git_output(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def git_worktree_clean(root: Path) -> bool:
    return not _git_output(root, "status", "--porcelain")


def load_v1_1_protocol(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    source = repository / V1_1_PROTOCOL_RELATIVE
    if file_sha256(source) != V1_1_PROTOCOL_SHA256:
        raise RunnerContractError("Phase A v1.1 protocol SHA changed")
    if file_sha256(repository / V1_1_DOCUMENT_RELATIVE) != V1_1_DOCUMENT_SHA256:
        raise RunnerContractError("Phase A v1.1 protocol document SHA changed")
    try:
        data = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise RunnerContractError("invalid Phase A v1.1 YAML") from error
    if type(data) is not dict:
        raise RunnerContractError("Phase A v1.1 root is not a mapping")
    protocol = data.get("protocol", {})
    if (
        protocol.get("protocol_type")
        != "dual_independent_backend_phase_a_qualification"
        or float(protocol.get("protocol_version", 0.0)) != 1.1
        or protocol.get("amendment_type") != "implementation_only_correction"
        or protocol.get("formal_execution_authorized_before_v1_1_lock") is not False
    ):
        raise RunnerContractError("Phase A v1.1 amendment identity changed")
    base = data.get("base_protocol", {})
    if (
        base.get("path") != V1_PROTOCOL_RELATIVE.as_posix()
        or base.get("sha256") != V1_PROTOCOL_SHA256
        or file_sha256(repository / V1_PROTOCOL_RELATIVE) != V1_PROTOCOL_SHA256
    ):
        raise RunnerContractError("Phase A v1 base protocol reference changed")
    load_backend_phase_a_protocol(repository)
    return data


def scientific_contract_diff(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    amendment = load_v1_1_protocol(repository)
    base = load_backend_phase_a_protocol(repository)
    inherited = tuple(
        amendment["inherited_scientific_contract"]["byte_exact_sections"]
    )
    section_hashes = {
        section: canonical_json_sha256(base.data[section]) for section in inherited
    }
    required = amendment["inherited_scientific_contract"][
        "required_difference_counts"
    ]
    output = {
        "schema_version": "backend_phase_a_v1_to_v1_1_diff_v1",
        "base_protocol_path": V1_PROTOCOL_RELATIVE.as_posix(),
        "base_protocol_sha256": V1_PROTOCOL_SHA256,
        "amendment_protocol_path": V1_1_PROTOCOL_RELATIVE.as_posix(),
        "amendment_protocol_sha256": V1_1_PROTOCOL_SHA256,
        "inheritance_mode": "verified_base_protocol_sections_by_reference",
        "inherited_section_sha256": section_hashes,
        **{name: int(value) for name, value in required.items()},
        "runner_implementation_difference_count": int(
            file_sha256(repository / "scripts/168_run_backend_phase_a.py")
            != V1_PLACEHOLDER_SHA256
        ),
    }
    output["scientific_contract_unchanged"] = all(
        output[name] == 0 for name in required
    )
    return output


def implementation_hashes(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    paths = {
        "scene_generator": "src/capture_range/day2_development_scene.py",
        "snapshot_builder": "src/zero_perturbation/snapshot_builder.py",
        "open3d_backend": "src/zero_perturbation/open3d_backend.py",
        "pcl_python_adapter": "src/zero_perturbation/pcl_backend.py",
        "pcl_cli_source": "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp",
        "rotation_metric": "src/zero_perturbation/rotation_metrics.py",
        "runner": "scripts/168_run_backend_phase_a.py",
        "runner_engine": "src/zero_perturbation/backend_phase_a_v1_1.py",
        "v1_1_verifier": "src/zero_perturbation/backend_phase_a_v1_1_verification.py",
        "protocol_yaml": V1_1_PROTOCOL_RELATIVE.as_posix(),
        "protocol_markdown": V1_1_DOCUMENT_RELATIVE.as_posix(),
    }
    files = {
        label: {"path": path, "sha256": file_sha256(repository / path)}
        for label, path in paths.items()
    }
    binary = repository / DEFAULT_PCL_CLI_RELATIVE
    if not binary.is_file():
        raise FileNotFoundError(f"frozen PCL CLI binary missing: {binary}")
    result = {
        "schema_version": "backend_phase_a_v1_1_implementation_hashes_v1",
        "files": files,
        "pcl_cli_binary": {
            "path": DEFAULT_PCL_CLI_RELATIVE.as_posix(),
            "sha256": file_sha256(binary),
        },
    }
    result["implementation_sha256"] = canonical_json_sha256(result)
    return result


def verify_planned_manifests(
    root: str | Path, snapshot_path: str | Path, trial_path: str | Path
) -> dict[str, Any]:
    repository = Path(root).resolve()
    base = load_backend_phase_a_protocol(repository)
    snapshot_file = Path(snapshot_path)
    trial_file = Path(trial_path)
    snapshots = _read_csv(snapshot_file)
    trials = _read_csv(trial_file)
    expected_snapshots = [
        {key: str(value) for key, value in row.row().items()}
        for row in base.planned_snapshots()
    ]
    expected_trials = [
        {key: str(value) for key, value in row.row().items()}
        for row in base.planned_trials()
    ]
    if snapshots != expected_snapshots or trials != expected_trials:
        raise RunnerContractError("v1.1 planned IDs differ from frozen v1 enumeration")
    native = sum("native" in row["backend"].lower() for row in trials)
    open3d = sum(row["backend"] == OPEN3D_BACKEND for row in trials)
    pcl = sum(row["backend"] == PCL_BACKEND for row in trials)
    if (len(snapshots), len(trials), native, open3d, pcl) != (210, 420, 0, 210, 210):
        raise RunnerContractError("v1.1 plan cardinality changed")
    return {
        "planned_snapshot_count": len(snapshots),
        "planned_trial_count": len(trials),
        "native_planned_trial_count": native,
        "open3d_planned_trial_count": open3d,
        "pcl_planned_trial_count": pcl,
        "snapshots": snapshots,
        "trials": trials,
    }


def validate_v1_1_lock_document(
    path: str | Path,
    root: str | Path,
    *,
    require_formal_authority: bool = True,
) -> dict[str, Any]:
    repository = Path(root).resolve()
    lock_path = Path(path).resolve()
    if not lock_path.is_file():
        raise FileNotFoundError("--protocol-lock file does not exist")
    document = _read_json(lock_path)
    if document.get("schema_version") != "backend_phase_a_v1_1_protocol_lock_v1":
        raise RunnerContractError("old v1 or unknown Phase A lock is not executable")
    stored = document.get("lock_payload_sha256")
    payload = {
        key: value for key, value in document.items() if key != "lock_payload_sha256"
    }
    if not isinstance(stored, str) or canonical_json_sha256(payload) != stored:
        raise RunnerContractError("Phase A v1.1 lock payload SHA mismatch")
    load_v1_1_protocol(repository)
    if (
        document.get("protocol_sha256") != V1_1_PROTOCOL_SHA256
        or document.get("protocol_document_sha256") != V1_1_DOCUMENT_SHA256
        or document.get("base_protocol_sha256") != V1_PROTOCOL_SHA256
    ):
        raise RunnerContractError("Phase A v1.1 lock protocol reference changed")
    if require_formal_authority and document.get("formal_execution_authorized") is not True:
        raise PermissionError("Phase A v1.1 formal execution is not authorized")
    implementation = document.get("implementation", {})
    for label, item in implementation.get("files", {}).items():
        candidate = repository / str(item.get("path", ""))
        if not candidate.is_file() or file_sha256(candidate) != item.get("sha256"):
            raise RunnerContractError(f"implementation SHA mismatch: {label}")
    expected_implementation = canonical_json_sha256(implementation)
    if document.get("implementation_sha256") != expected_implementation:
        raise RunnerContractError("implementation lock digest mismatch")
    binary = implementation.get("pcl_cli_binary", {})
    binary_path = repository / str(binary.get("path", ""))
    if not binary_path.is_file() or file_sha256(binary_path) != binary.get("sha256"):
        raise RunnerContractError("PCL CLI binary SHA mismatch")
    snapshots = repository / str(document.get("planned_snapshots_path", ""))
    trials = repository / str(document.get("planned_trials_path", ""))
    if (
        not snapshots.is_file()
        or file_sha256(snapshots) != document.get("planned_snapshots_sha256")
        or not trials.is_file()
        or file_sha256(trials) != document.get("planned_trials_sha256")
    ):
        raise RunnerContractError("planned manifest SHA mismatch")
    verify_planned_manifests(repository, snapshots, trials)
    base = load_backend_phase_a_protocol(repository)
    if document.get("open3d_parameter_sha256") != base.data[
        "open3d_parameter_contract"
    ]["canonical_sha256"]:
        raise RunnerContractError("Open3D parameter SHA mismatch")
    if document.get("pcl_parameter_sha256") != base.data[
        "pcl_parameter_contract"
    ]["canonical_sha256"]:
        raise RunnerContractError("PCL parameter SHA mismatch")
    return document


def _validate_run_arguments(run_id: str, output_dir: Path, workers: int) -> None:
    if not RUN_ID_PATTERN.fullmatch(str(run_id)):
        raise ValueError("--run-id must be a portable non-empty identifier")
    if int(workers) < 1:
        raise ValueError("--workers must be positive")
    candidate = output_dir.resolve()
    existing = candidate
    while not existing.exists() and existing != existing.parent:
        existing = existing.parent
    if not existing.is_dir() or not os.access(existing, os.W_OK):
        raise PermissionError(f"output path is not writable: {output_dir}")


def dry_run(
    *,
    root: str | Path,
    protocol_lock: str | Path,
    run_id: str,
    output_dir: str | Path,
    workers: int,
) -> dict[str, Any]:
    repository = Path(root).resolve()
    destination = Path(output_dir)
    _validate_run_arguments(run_id, destination, workers)
    lock = validate_v1_1_lock_document(
        protocol_lock, repository, require_formal_authority=False
    )
    plan = verify_planned_manifests(
        repository,
        repository / lock["planned_snapshots_path"],
        repository / lock["planned_trials_path"],
    )
    return {
        "schema_version": "backend_phase_a_v1_1_dry_run_v1",
        "run_id": str(run_id),
        "output_dir": str(destination.resolve()),
        "workers": int(workers),
        "protocol_sha256": V1_1_PROTOCOL_SHA256,
        "implementation_sha256": lock["implementation_sha256"],
        "formal_execution_authorized_by_lock": bool(
            lock.get("formal_execution_authorized") is True
        ),
        "DRY_RUN_PLANNED_SNAPSHOT_COUNT": plan["planned_snapshot_count"],
        "DRY_RUN_PLANNED_TRIAL_COUNT": plan["planned_trial_count"],
        "DRY_RUN_RNG_INSTANTIATION_COUNT": 0,
        "DRY_RUN_SNAPSHOT_GENERATION_COUNT": 0,
        "DRY_RUN_BACKEND_EXECUTION_COUNT": 0,
        "DRY_RUN_TRIAL_RESULT_COUNT": 0,
        "pcl_cli_discovered": True,
        "path_writable": True,
        "dry_run_pass": True,
    }


def atomic_write_json(
    path: str | Path, value: Mapping[str, Any], *, allow_replace: bool = False
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not allow_replace:
        raise DuplicateTrialResult(f"refusing to overwrite existing result: {destination}")
    temporary = destination.with_name(
        f"{destination.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    if temporary.exists():
        raise RunnerContractError(f"temporary output already exists: {temporary}")
    payload = (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if destination.exists() and not allow_replace:
            raise DuplicateTrialResult(
                f"result appeared before atomic rename: {destination}"
            )
        os.replace(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _result_path(directory: Path, trial_id: str) -> Path:
    token = hashlib.sha256(trial_id.encode("utf-8")).hexdigest()
    return directory / f"{token}.json"


def _snapshot_checksum(checksums: Mapping[str, str]) -> str:
    return canonical_json_sha256(
        {
            "source_checksum": checksums["source_checksum"],
            "target_checksum": checksums["target_checksum"],
            "reference_pose_checksum": checksums["reference_pose_checksum"],
        }
    )


def _open3d_parameters(base: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "registration_method": "point_to_plane",
        "maximum_correspondence_distance_m": float(
            base["maximum_correspondence_distance_m"]
        ),
        "target_normal_estimation": dict(base["target_normal_estimation"]),
        "icp_convergence": dict(base["convergence"]),
    }


def _common_trial_fields(
    *,
    trial_id: str,
    snapshot_id: str,
    backend: str,
    checksums: Mapping[str, str],
    protocol_sha256: str,
    implementation_sha256: str,
    fixture_only: bool,
) -> dict[str, Any]:
    return {
        "schema_version": (
            FIXTURE_RESULT_SCHEMA if fixture_only else FORMAL_RESULT_SCHEMA
        ),
        "planned_trial_id": trial_id,
        "trial_id": trial_id,
        "snapshot_id": snapshot_id,
        "backend": backend,
        "protocol_sha256": protocol_sha256,
        "implementation_sha256": implementation_sha256,
        "is_formal_phase_a": not fixture_only,
        "fixture_only": fixture_only,
        **{name: str(value) for name, value in checksums.items()},
    }


def _run_open3d(
    *,
    source: np.ndarray,
    target: np.ndarray,
    reference: np.ndarray,
    trial_id: str,
    snapshot_id: str,
    checksums: Mapping[str, str],
    protocol_sha256: str,
    implementation_sha256: str,
    parameters: Mapping[str, Any],
    fixture_only: bool,
) -> dict[str, Any]:
    common = _common_trial_fields(
        trial_id=trial_id,
        snapshot_id=snapshot_id,
        backend=OPEN3D_BACKEND,
        checksums=checksums,
        protocol_sha256=protocol_sha256,
        implementation_sha256=implementation_sha256,
        fixture_only=fixture_only,
    )
    try:
        result = run_open3d_full(
            source,
            target,
            reference,
            _open3d_parameters(parameters),
            backend_seed=0,
            input_checksum=checksums["snapshot_checksum"],
        )
        update = transform_update(reference, result.final_pose)
        audit = update["rotation_audit"]
        payload: dict[str, Any] = {
            **common,
            "final_transform": result.final_pose.tolist(),
            "final_transform_finite": bool(np.all(np.isfinite(result.final_pose))),
            "fitness": result.extra.get("fitness"),
            "fitness_finite": bool(np.isfinite(result.extra.get("fitness"))),
            "inlier_rmse": result.extra.get("inlier_rmse"),
            "inlier_rmse_finite": bool(np.isfinite(result.extra.get("inlier_rmse"))),
            "correspondence_count": int(result.correspondence_count),
            "runtime_ms": float(result.runtime_ms),
            "exception": None,
            "raw_rotation_finite": audit["raw_rotation_finite"],
            "raw_rotation_determinant": audit.get("determinant"),
            "orthogonality_defect_fro": audit.get("orthogonality_defect_fro"),
            "projection_correction_fro": audit.get("projection_correction_fro"),
            "rotation_matrix_quality_pass": audit["rotation_matrix_quality_pass"],
            "translation_update_m": update["translation_update_m"],
            "rotation_update_rad": update["rotation_update_rad"],
            "finite_output": bool(result.finite_result),
        }
    except Exception as error:
        payload = {
            **common,
            "final_transform": None,
            "final_transform_finite": False,
            "fitness": None,
            "fitness_finite": False,
            "inlier_rmse": None,
            "inlier_rmse_finite": False,
            "correspondence_count": 0,
            "runtime_ms": None,
            "exception": f"{type(error).__name__}: {error}",
            "raw_rotation_finite": False,
            "raw_rotation_determinant": None,
            "orthogonality_defect_fro": None,
            "projection_correction_fro": None,
            "rotation_matrix_quality_pass": False,
            "translation_update_m": None,
            "rotation_update_rad": None,
            "finite_output": False,
        }
    expected = {
        name: checksums[name]
        for name in (
            "source_checksum",
            "target_checksum",
            "reference_pose_checksum",
            "snapshot_checksum",
        )
    }
    reasons = solver_failure_reasons(OPEN3D_BACKEND, payload, expected)
    payload["solver_failure_reasons"] = list(reasons)
    payload["solver_failed"] = bool(reasons)
    payload["failure_classifications"] = (
        ["BACKEND_EXCEPTION"]
        if payload["exception"]
        else (["NONFINITE_OUTPUT"] if not payload["finite_output"] else [])
    )
    if reasons and "SCIENTIFIC_SOLVER_FAILURE" not in payload["failure_classifications"]:
        payload["failure_classifications"].append("SCIENTIFIC_SOLVER_FAILURE")
    return payload


def _run_pcl(
    *,
    source: np.ndarray,
    target: np.ndarray,
    reference: np.ndarray,
    trial_id: str,
    snapshot_id: str,
    checksums: Mapping[str, str],
    protocol_sha256: str,
    implementation_sha256: str,
    parameters: Mapping[str, Any],
    pcl_cli: Path,
    fixture_only: bool,
) -> dict[str, Any]:
    common = _common_trial_fields(
        trial_id=trial_id,
        snapshot_id=snapshot_id,
        backend=PCL_BACKEND,
        checksums=checksums,
        protocol_sha256=protocol_sha256,
        implementation_sha256=implementation_sha256,
        fixture_only=fixture_only,
    )
    try:
        result = run_pcl_point_to_plane(
            source,
            target,
            reference,
            trial_id=trial_id,
            checksums={
                name: checksums[name]
                for name in (
                    "source_checksum",
                    "target_checksum",
                    "reference_pose_checksum",
                    "snapshot_checksum",
                )
            },
            executable=pcl_cli,
            parameters=frozen_parameters(parameters),
        )
        update = (
            transform_update(reference, result.final_transformation)
            if result.final_transformation is not None
            else None
        )
        audit = update["rotation_audit"] if update else {}
        payload: dict[str, Any] = {
            **common,
            "pcl_version": result.pcl_version,
            "pcl_cli_sha256": file_sha256(pcl_cli),
            "cli_exit_code": result.cli_exit_code,
            "has_converged_raw": result.has_converged,
            "fitness_score": result.fitness_score,
            "fitness_finite": result.fitness_finite,
            "iteration_count": result.iteration_count,
            "correspondence_count": result.correspondence_count,
            "runtime_ms": result.runtime_ms,
            "exception": None,
            "failure_reason": result.failure_reason,
            "source_normal_finite_count": result.source_normal_statistics["finite_count"],
            "source_normal_zero_count": result.source_normal_statistics["zero_count"],
            "source_normal_nan_count": result.source_normal_statistics["nan_count"],
            "source_normal_norm_min": result.source_normal_statistics["norm_min"],
            "source_normal_norm_median": result.source_normal_statistics["norm_median"],
            "source_normal_norm_max": result.source_normal_statistics["norm_max"],
            "target_normal_finite_count": result.target_normal_statistics["finite_count"],
            "target_normal_zero_count": result.target_normal_statistics["zero_count"],
            "target_normal_nan_count": result.target_normal_statistics["nan_count"],
            "target_normal_norm_min": result.target_normal_statistics["norm_min"],
            "target_normal_norm_median": result.target_normal_statistics["norm_median"],
            "target_normal_norm_max": result.target_normal_statistics["norm_max"],
            "final_transform": (
                result.final_transformation.tolist()
                if result.final_transformation is not None
                else None
            ),
            "final_transform_finite": result.final_transform_finite,
            "raw_rotation_finite": audit.get("raw_rotation_finite", False),
            "raw_rotation_determinant": audit.get("determinant"),
            "orthogonality_defect_fro": audit.get("orthogonality_defect_fro"),
            "projection_correction_fro": audit.get("projection_correction_fro"),
            "rotation_matrix_quality_pass": audit.get(
                "rotation_matrix_quality_pass", False
            ),
            "translation_update_m": (
                update["translation_update_m"] if update else None
            ),
            "rotation_update_rad": update["rotation_update_rad"] if update else None,
            "finite_output": result.finite_output,
        }
    except Exception as error:
        payload = {
            **common,
            "pcl_version": None,
            "pcl_cli_sha256": file_sha256(pcl_cli),
            "cli_exit_code": -1,
            "has_converged_raw": False,
            "fitness_score": None,
            "fitness_finite": False,
            "iteration_count": 0,
            "correspondence_count": 0,
            "runtime_ms": None,
            "exception": f"{type(error).__name__}: {error}",
            "failure_reason": "BACKEND_EXCEPTION",
            "source_normal_finite_count": 0,
            "source_normal_zero_count": -1,
            "source_normal_nan_count": -1,
            "source_normal_norm_min": None,
            "source_normal_norm_median": None,
            "source_normal_norm_max": None,
            "target_normal_finite_count": 0,
            "target_normal_zero_count": -1,
            "target_normal_nan_count": -1,
            "target_normal_norm_min": None,
            "target_normal_norm_median": None,
            "target_normal_norm_max": None,
            "final_transform": None,
            "final_transform_finite": False,
            "raw_rotation_finite": False,
            "raw_rotation_determinant": None,
            "orthogonality_defect_fro": None,
            "projection_correction_fro": None,
            "rotation_matrix_quality_pass": False,
            "translation_update_m": None,
            "rotation_update_rad": None,
            "finite_output": False,
        }
    expected = {
        name: checksums[name]
        for name in (
            "source_checksum",
            "target_checksum",
            "reference_pose_checksum",
            "snapshot_checksum",
        )
    }
    reasons = solver_failure_reasons(PCL_BACKEND, payload, expected)
    payload["solver_failure_reasons"] = list(reasons)
    payload["solver_failed"] = bool(reasons)
    payload["failure_classifications"] = (
        ["BACKEND_EXCEPTION"]
        if payload["exception"]
        else (["NONFINITE_OUTPUT"] if not payload["finite_output"] else [])
    )
    if reasons and "SCIENTIFIC_SOLVER_FAILURE" not in payload["failure_classifications"]:
        payload["failure_classifications"].append("SCIENTIFIC_SOLVER_FAILURE")
    return payload


def validate_existing_result(
    path: Path,
    *,
    trial_id: str,
    protocol_sha256: str,
    implementation_sha256: str,
    checksums: Mapping[str, str],
) -> dict[str, Any]:
    try:
        payload = _read_json(path)
    except CorruptExistingResult:
        raise
    if payload.get("planned_trial_id") != trial_id:
        raise CorruptExistingResult("existing result trial identity changed")
    if (
        payload.get("protocol_sha256") != protocol_sha256
        or payload.get("implementation_sha256") != implementation_sha256
    ):
        raise RunnerContractError("existing result protocol/implementation SHA mismatch")
    for name, expected in checksums.items():
        if payload.get(name) != expected:
            raise RunnerContractError(f"existing result checksum mismatch: {name}")
    return payload


def execute_fixture_chain(
    *,
    root: str | Path,
    points: np.ndarray,
    output_dir: str | Path,
    pcl_cli: str | Path | None = None,
    resume: bool = False,
    backend_hooks: Mapping[str, Callable[..., dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Execute exactly one non-formal identity fixture through both result paths."""

    repository = Path(root).resolve()
    destination = Path(output_dir).resolve()
    canonical = canonical_backend_inputs(points, points, np.eye(4, dtype=np.float64))
    if not source_is_exact_target_subset(
        canonical["source_points"], canonical["target_points"]
    ):
        raise ValueError("fixture source is not the exact target cloud")
    checksums = {
        "source_checksum": canonical["source_checksum"],
        "target_checksum": canonical["target_checksum"],
        "reference_pose_checksum": canonical["reference_pose_checksum"],
    }
    checksums["snapshot_checksum"] = _snapshot_checksum(checksums)
    protocol_sha = V1_1_PROTOCOL_SHA256
    implementation_sha = canonical_json_sha256(
        {
            "runner_fixture": "nonformal",
            "runner_sha256": file_sha256(
                repository / "scripts/168_run_backend_phase_a.py"
            ),
        }
    )
    snapshot_id = "fixture-only/backend-phase-a-runner/nondegenerate-identity"
    snapshot_payload = {
        "schema_version": "backend_phase_a_v1_1_fixture_snapshot_v1",
        "snapshot_id": snapshot_id,
        "is_formal_phase_a": False,
        "fixture_only": True,
        "source_point_count": int(canonical["source_points"].shape[0]),
        "target_point_count": int(canonical["target_points"].shape[0]),
        "unique_source_coordinate_count": int(
            np.unique(canonical["source_points"], axis=0).shape[0]
        ),
        "unique_target_coordinate_count": int(
            np.unique(canonical["target_points"], axis=0).shape[0]
        ),
        "finite_source_count": int(
            np.all(np.isfinite(canonical["source_points"]), axis=1).sum()
        ),
        "finite_target_count": int(
            np.all(np.isfinite(canonical["target_points"]), axis=1).sum()
        ),
        **checksums,
    }
    snapshot_path = destination / "snapshots" / "fixture_snapshot.json"
    if snapshot_path.exists():
        if not resume:
            raise DuplicateTrialResult("fixture snapshot already exists")
        existing = _read_json(snapshot_path)
        if existing != snapshot_payload:
            raise CorruptExistingResult("existing fixture snapshot changed")
    else:
        atomic_write_json(snapshot_path, snapshot_payload)

    base = load_backend_phase_a_protocol(repository)
    pcl_path = Path(pcl_cli or repository / DEFAULT_PCL_CLI_RELATIVE).resolve()
    hooks = dict(backend_hooks or {})
    completed: list[str] = []
    failed: list[str] = []
    resumed: list[str] = []
    input_rows: list[dict[str, Any]] = []
    for backend in (OPEN3D_BACKEND, PCL_BACKEND):
        trial_id = f"{snapshot_id}/{backend}"
        result_path = _result_path(destination / "trials", trial_id)
        if result_path.exists():
            if not resume:
                raise DuplicateTrialResult(f"fixture trial already exists: {trial_id}")
            payload = validate_existing_result(
                result_path,
                trial_id=trial_id,
                protocol_sha256=protocol_sha,
                implementation_sha256=implementation_sha,
                checksums=checksums,
            )
            resumed.append(trial_id)
        else:
            hook = hooks.get(backend)
            if hook is not None:
                payload = hook(
                    source=canonical["source_points"],
                    target=canonical["target_points"],
                    reference=canonical["reference_pose"],
                    trial_id=trial_id,
                    snapshot_id=snapshot_id,
                    checksums=checksums,
                    protocol_sha256=protocol_sha,
                    implementation_sha256=implementation_sha,
                    fixture_only=True,
                )
            elif backend == OPEN3D_BACKEND:
                payload = _run_open3d(
                    source=canonical["source_points"],
                    target=canonical["target_points"],
                    reference=canonical["reference_pose"],
                    trial_id=trial_id,
                    snapshot_id=snapshot_id,
                    checksums=checksums,
                    protocol_sha256=protocol_sha,
                    implementation_sha256=implementation_sha,
                    parameters=base.data["open3d_parameter_contract"]["parameters"],
                    fixture_only=True,
                )
            else:
                payload = _run_pcl(
                    source=canonical["source_points"],
                    target=canonical["target_points"],
                    reference=canonical["reference_pose"],
                    trial_id=trial_id,
                    snapshot_id=snapshot_id,
                    checksums=checksums,
                    protocol_sha256=protocol_sha,
                    implementation_sha256=implementation_sha,
                    parameters=base.data["pcl_parameter_contract"]["parameters"],
                    pcl_cli=pcl_path,
                    fixture_only=True,
                )
            atomic_write_json(result_path, payload)
        completed.append(trial_id)
        if payload.get("solver_failed"):
            failed.append(trial_id)
        input_rows.append(
            {
                "planned_trial_id": trial_id,
                "backend": backend,
                **{name: payload[name] for name in checksums},
            }
        )
    mismatch_count = int(
        len({row["source_checksum"] for row in input_rows}) != 1
        or len({row["target_checksum"] for row in input_rows}) != 1
        or len({row["reference_pose_checksum"] for row in input_rows}) != 1
        or len({row["snapshot_checksum"] for row in input_rows}) != 1
    )
    manifest = {
        "schema_version": "backend_phase_a_v1_1_fixture_manifest_v1",
        "is_formal_phase_a": False,
        "fixture_only": True,
        "fixture_snapshot_count": 1,
        "fixture_trial_count": 2,
        "completed_trial_ids": completed,
        "pending_trial_ids": [],
        "failed_trial_ids": failed,
        "resumed_trial_ids": resumed,
        "backend_input_checksum_mismatch_count": mismatch_count,
        "formal_rng_instantiation_count": 0,
        "formal_snapshot_generation_count": 0,
        "formal_backend_execution_count": 0,
        "formal_trial_result_count": 0,
        "confirmatory_seed_access_count": 0,
        "old_capture_test_seed_access_count": 0,
        "native_formal_execution_count": 0,
    }
    atomic_write_json(destination / "fixture_manifest.json", manifest, allow_replace=resume)
    return manifest


def execute_formal_phase_a(
    *,
    root: str | Path,
    protocol_lock: str | Path,
    run_id: str,
    output_dir: str | Path,
    workers: int,
    resume: bool,
) -> dict[str, Any]:
    """Execute the locked formal matrix; this correction round never calls it."""

    repository = Path(root).resolve()
    destination = Path(output_dir).resolve()
    _validate_run_arguments(run_id, destination, workers)
    lock = validate_v1_1_lock_document(protocol_lock, repository)
    if not git_worktree_clean(repository):
        raise RunnerContractError("formal Phase A requires a clean Git worktree")
    plan = verify_planned_manifests(
        repository,
        repository / lock["planned_snapshots_path"],
        repository / lock["planned_trials_path"],
    )
    run_root = destination / run_id
    if run_root.exists() and not resume:
        raise FileExistsError("formal output exists; use --resume without changing inputs")
    run_root.mkdir(parents=True, exist_ok=True)

    # Imports occur only after every lock, plan, path, and worktree check passes.
    from .protocol import DevelopmentSeedFirewall, load_protocol
    from .snapshot_builder import build_snapshot
    from .types import SnapshotKey

    development = load_protocol(repository)
    firewall = DevelopmentSeedFirewall(development)
    base = load_backend_phase_a_protocol(repository)
    pcl_cli = repository / lock["implementation"]["pcl_cli_binary"]["path"]
    completed: list[str] = []
    failed: list[str] = []
    resumed_ids: list[str] = []
    pending = [str(row["planned_trial_id"]) for row in plan["trials"]]
    backend_execution_count = 0
    trial_result_count = 0
    snapshot_generation_count = 0
    open3d_lock = threading.Lock()

    for snapshot_plan in plan["snapshots"]:
        key = SnapshotKey(
            scene_variant=snapshot_plan["scene_variant"],
            geometry_seed=int(snapshot_plan["geometry_seed_value"]),
            measurement_seed=int(snapshot_plan["measurement_seed_value"]),
            repeat_index=int(snapshot_plan["repeat_index"]),
            noise_condition="IDEAL_MATCHED",
        )
        bundle = build_snapshot(development, firewall, key)
        snapshot_generation_count += 1
        reference = pose_matrix(bundle.reference_pose)
        canonical = canonical_backend_inputs(
            bundle.scan_points, bundle.map_points, reference
        )
        # Exact provenance is evaluated after applying the frozen reference pose.
        homogeneous = np.column_stack(
            (canonical["source_points"].astype(np.float64), np.ones(len(canonical["source_points"])))
        )
        source_in_target = (reference @ homogeneous.T).T[:, :3].astype("<f4")
        if not source_is_exact_target_subset(source_in_target, canonical["target_points"]):
            raise RunnerContractError("IDEAL_MATCHED source provenance check failed")
        checksums = {
            "source_checksum": canonical["source_checksum"],
            "target_checksum": canonical["target_checksum"],
            "reference_pose_checksum": canonical["reference_pose_checksum"],
        }
        checksums["snapshot_checksum"] = _snapshot_checksum(checksums)
        snapshot_id = snapshot_plan["snapshot_id"]
        snapshot_payload = {
            "schema_version": "backend_phase_a_v1_1_formal_snapshot_v1",
            **snapshot_plan,
            "source_point_count": len(canonical["source_points"]),
            "target_point_count": len(canonical["target_points"]),
            "unique_source_coordinate_count": int(
                np.unique(canonical["source_points"], axis=0).shape[0]
            ),
            "unique_target_coordinate_count": int(
                np.unique(canonical["target_points"], axis=0).shape[0]
            ),
            "finite_source_count": int(
                np.all(np.isfinite(canonical["source_points"]), axis=1).sum()
            ),
            "finite_target_count": int(
                np.all(np.isfinite(canonical["target_points"]), axis=1).sum()
            ),
            **checksums,
            "protocol_sha256": V1_1_PROTOCOL_SHA256,
            "implementation_sha256": lock["implementation_sha256"],
            "is_formal_phase_a": True,
            "fixture_only": False,
        }
        snapshot_path = _result_path(run_root / "snapshots", snapshot_id)
        if snapshot_path.exists():
            if not resume or _read_json(snapshot_path) != snapshot_payload:
                raise CorruptExistingResult("existing formal snapshot changed")
        else:
            atomic_write_json(snapshot_path, snapshot_payload)

        def open3d_task() -> dict[str, Any]:
            with open3d_lock:
                return _run_open3d(
                    source=canonical["source_points"],
                    target=canonical["target_points"],
                    reference=canonical["reference_pose"],
                    trial_id=f"{snapshot_id}/{OPEN3D_BACKEND}",
                    snapshot_id=snapshot_id,
                    checksums=checksums,
                    protocol_sha256=V1_1_PROTOCOL_SHA256,
                    implementation_sha256=lock["implementation_sha256"],
                    parameters=base.data["open3d_parameter_contract"]["parameters"],
                    fixture_only=False,
                )

        def pcl_task() -> dict[str, Any]:
            return _run_pcl(
                source=canonical["source_points"],
                target=canonical["target_points"],
                reference=canonical["reference_pose"],
                trial_id=f"{snapshot_id}/{PCL_BACKEND}",
                snapshot_id=snapshot_id,
                checksums=checksums,
                protocol_sha256=V1_1_PROTOCOL_SHA256,
                implementation_sha256=lock["implementation_sha256"],
                parameters=base.data["pcl_parameter_contract"]["parameters"],
                pcl_cli=pcl_cli,
                fixture_only=False,
            )

        jobs = ((OPEN3D_BACKEND, open3d_task), (PCL_BACKEND, pcl_task))
        existing_payloads: dict[str, dict[str, Any]] = {}
        tasks_to_run: dict[str, Callable[[], dict[str, Any]]] = {}
        for backend, task in jobs:
            trial_id = f"{snapshot_id}/{backend}"
            result_path = _result_path(run_root / "trials", trial_id)
            if result_path.exists():
                if not resume:
                    raise DuplicateTrialResult(f"formal result exists: {trial_id}")
                existing_payloads[backend] = validate_existing_result(
                    result_path,
                    trial_id=trial_id,
                    protocol_sha256=V1_1_PROTOCOL_SHA256,
                    implementation_sha256=lock["implementation_sha256"],
                    checksums=checksums,
                )
            else:
                tasks_to_run[backend] = task
        with ThreadPoolExecutor(max_workers=min(int(workers), 2)) as pool:
            futures = {
                backend: pool.submit(task)
                for backend, task in tasks_to_run.items()
            }
            for backend, _ in jobs:
                trial_id = f"{snapshot_id}/{backend}"
                result_path = _result_path(run_root / "trials", trial_id)
                if backend in existing_payloads:
                    payload = existing_payloads[backend]
                    resumed_ids.append(trial_id)
                else:
                    try:
                        payload = futures[backend].result()
                    except (KeyboardInterrupt, SystemExit) as error:
                        interruption = {
                            "classification": "INFRASTRUCTURE_INTERRUPTION",
                            "planned_trial_id": trial_id,
                            "exception": type(error).__name__,
                        }
                        atomic_write_json(
                            _result_path(run_root / "interruptions", trial_id),
                            interruption,
                        )
                        raise
                    backend_execution_count += 1
                    atomic_write_json(result_path, payload)
                    trial_result_count += 1
                completed.append(trial_id)
                if payload.get("solver_failed"):
                    failed.append(trial_id)
                pending.remove(trial_id)

    manifest = {
        "schema_version": "backend_phase_a_v1_1_formal_run_manifest_v1",
        "run_id": run_id,
        "completed_trial_ids": completed,
        "pending_trial_ids": pending,
        "failed_trial_ids": failed,
        "resumed_trial_ids": resumed_ids,
        "snapshot_generation_count": snapshot_generation_count,
        "backend_execution_count": backend_execution_count,
        "trial_result_count": trial_result_count,
        **firewall.report(),
    }
    atomic_write_json(run_root / "run_manifest.json", manifest, allow_replace=resume)
    return manifest


__all__ = [
    "CorruptExistingResult",
    "DEFAULT_PCL_CLI_RELATIVE",
    "DuplicateTrialResult",
    "FIXTURE_RESULT_SCHEMA",
    "InfrastructureInterruption",
    "RunnerContractError",
    "V1_1_ARTIFACT_RELATIVE",
    "V1_1_DOCUMENT_RELATIVE",
    "V1_1_DOCUMENT_SHA256",
    "V1_1_LOCK_PASS_TAG",
    "V1_1_PROTOCOL_LOCK_TAG",
    "V1_1_PROTOCOL_RELATIVE",
    "V1_1_PROTOCOL_SHA256",
    "V1_INVALIDATION_RELATIVE",
    "V1_PLACEHOLDER_SHA256",
    "atomic_write_json",
    "dry_run",
    "execute_fixture_chain",
    "execute_formal_phase_a",
    "git_worktree_clean",
    "implementation_hashes",
    "load_v1_1_protocol",
    "scientific_contract_diff",
    "validate_existing_result",
    "validate_v1_1_lock_document",
    "verify_planned_manifests",
]
