"""Independent verification of the dual-backend Phase A protocol-lock artifact."""

from __future__ import annotations

import csv
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from .backend_phase_a_protocol import (
    DOCUMENT_RELATIVE,
    DOCUMENT_SHA256,
    PROTOCOL_LOCK_COMMIT,
    PROTOCOL_LOCK_TAG,
    PROTOCOL_RELATIVE,
    PROTOCOL_SHA256,
    canonical_json_sha256,
    file_sha256,
    load_backend_phase_a_protocol,
)


ARTIFACT_RELATIVE = Path("artifacts/current/zero_perturbation_backend_phase_a_lock")
BASELINE_COMMIT = "6e4cfb857fb9c3050aa42647d9f86c8892130d80"
PCL_V3_ARCHIVE_TAG = "archive/zero-perturbation-pcl-backend-qualification-v3-pass"
PCL_V3_BUNDLE = Path("/tmp/Degen-LIO-zero-perturbation-pcl-v3-pass.bundle")
PCL_V3_BUNDLE_SHA256 = "4a5744bc668b93657619632735e0395d0ccabfca8b6efdd8fedab17662158010"
LOCK_PASS_TAG = "archive/zero-perturbation-backend-phase-a-v1-lock-pass"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _verify_sums(directory: Path) -> list[str]:
    sums = directory / "SHA256SUMS"
    if not sums.is_file():
        return ["SHA256SUMS is missing"]
    errors: list[str] = []
    declared: set[str] = set()
    for line in sums.read_text(encoding="utf-8").splitlines():
        try:
            expected, relative = line.split("  ", 1)
        except ValueError:
            errors.append(f"malformed SHA256SUMS line: {line}")
            continue
        declared.add(relative)
        path = directory / relative
        if not path.is_file():
            errors.append(f"missing artifact file: {relative}")
        elif file_sha256(path) != expected:
            errors.append(f"artifact hash mismatch: {relative}")
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if declared != actual:
        errors.append("artifact SHA inventory differs from files on disk")
    return errors


def _git_tag_target(repository: Path, tag: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"{tag}^{{}}"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _git_unchanged(repository: Path, *paths: str) -> bool:
    return (
        subprocess.run(
            ["git", "diff", "--quiet", BASELINE_COMMIT, "--", *paths],
            cwd=repository,
            check=False,
        ).returncode
        == 0
    )


def _expected_snapshot_row(snapshot: Any) -> dict[str, str]:
    return {key: str(value) for key, value in snapshot.row().items()}


def _expected_trial_row(trial: Any) -> dict[str, str]:
    return {key: str(value) for key, value in trial.row().items()}


def verify_backend_phase_a_lock(
    root: str | Path, *, require_final: bool = False
) -> dict[str, Any]:
    repository = Path(root).resolve()
    artifact = repository / ARTIFACT_RELATIVE
    errors: list[str] = []
    try:
        protocol = load_backend_phase_a_protocol(repository)
    except Exception as error:  # verifier records rather than masks all downstream checks
        return {
            "schema_version": "backend_phase_a_lock_verification_v1",
            "verification_pass": False,
            "error_count": 1,
            "errors": [f"protocol load failed: {error}"],
        }

    required = set(protocol.data["artifact_contract"]["required_files"])
    actual_names = {path.name for path in artifact.iterdir() if path.is_file()}
    if actual_names != required:
        errors.append(
            f"artifact file inventory mismatch: missing={sorted(required-actual_names)}, "
            f"extra={sorted(actual_names-required)}"
        )
    errors.extend(_verify_sums(artifact))

    snapshots = _read_csv(artifact / "planned_snapshots.csv")
    trials = _read_csv(artifact / "planned_trials.csv")
    expected_snapshots = [
        _expected_snapshot_row(snapshot) for snapshot in protocol.planned_snapshots()
    ]
    expected_trials = [
        _expected_trial_row(trial) for trial in protocol.planned_trials()
    ]
    if snapshots != expected_snapshots:
        errors.append("planned snapshot rows differ from exact RNG-free enumeration")
    if trials != expected_trials:
        errors.append("planned trial rows differ from exact RNG-free enumeration")
    backend_counts = Counter(row.get("backend", "") for row in trials)
    if len(snapshots) != 210 or len(trials) != 420:
        errors.append("planned row cardinality is not 210/420")
    if backend_counts != {
        "open3d_point_to_plane": 210,
        "pcl_iterative_closest_point_with_normals": 210,
    }:
        errors.append(f"planned backend counts changed: {dict(backend_counts)}")
    if any("native" in row.get("backend", "").lower() for row in trials):
        errors.append("Native appears in planned trials")
    forbidden_plan_fields = {
        "points",
        "source_points",
        "target_points",
        "point_cloud",
        "pcd_path",
    }
    if snapshots and forbidden_plan_fields & set(snapshots[0]):
        errors.append("planned snapshot manifest contains point-cloud fields")

    self_audit = protocol.self_audit()
    lock = _read_json(artifact / "backend_phase_a_protocol_lock.json")
    stored_lock_hash = lock.get("lock_payload_sha256")
    payload = {key: value for key, value in lock.items() if key != "lock_payload_sha256"}
    if canonical_json_sha256(payload) != stored_lock_hash:
        errors.append("protocol lock payload hash does not verify")
    if lock.get("protocol_sha256") != PROTOCOL_SHA256:
        errors.append("protocol lock references wrong YAML SHA")
    if lock.get("protocol_document_sha256") != DOCUMENT_SHA256:
        errors.append("protocol lock references wrong Markdown SHA")
    if lock.get("planned_snapshot_count") != 210 or lock.get("planned_trial_count") != 420:
        errors.append("protocol lock planned counts changed")

    parameters = _read_json(artifact / "backend_parameter_contract.json")
    if parameters.get("open3d_parameter_sha256") != protocol.data[
        "open3d_parameter_contract"
    ]["canonical_sha256"]:
        errors.append("Open3D parameter-lock hash mismatch")
    if parameters.get("pcl_parameter_sha256") != protocol.data[
        "pcl_parameter_contract"
    ]["canonical_sha256"]:
        errors.append("PCL parameter-lock hash mismatch")
    if not parameters.get("OPEN3D_PARAMETER_LOCK_PASS"):
        errors.append("Open3D parameter lock did not pass")
    if not parameters.get("PCL_PARAMETER_LOCK_PASS"):
        errors.append("PCL parameter lock did not pass")

    transform = _read_json(artifact / "transform_semantics.json")
    if transform != {
        "T_delta": "inverse(T_reference) @ T_estimated",
        "T_estimated_direction": "source_frame_to_target_map_frame",
        "T_reference_direction": "source_frame_to_target_map_frame",
        "rotation_update": "reflection_safe_nearest_SO3_SVD_then_atan2_geodesic",
        "translation_update": "norm(T_delta[0:3, 3])",
    }:
        errors.append("transform-semantics artifact changed")

    metrics = _read_json(artifact / "metric_contract.json")
    if not (
        metrics.get("raw_trace_acos_gate_forbidden") is True
        and metrics.get("q95")
        == {"implementation": "numpy.quantile", "method": "linear", "q": 0.95}
        and metrics.get("median") == {"implementation": "numpy.median"}
    ):
        errors.append("metric contract changed")
    gates = _read_json(artifact / "gate_contract.json")
    if gates.get("snapshot_diversity", {}).get(
        "minimum_unique_source_checksum_count"
    ) != 10:
        errors.append("snapshot diversity threshold changed")

    seed_audit = _read_json(artifact / "seed_usage_audit.json")
    zero_seed_fields = (
        "PHASE_A_RNG_INSTANTIATION_COUNT",
        "PHASE_A_SNAPSHOT_GENERATION_COUNT",
        "PHASE_A_BACKEND_EXECUTION_COUNT",
        "PHASE_A_TRIAL_RESULT_COUNT",
        "CONFIRMATORY_RNG_INSTANTIATION_COUNT",
        "OLD_CAPTURE_TEST_RNG_INSTANTIATION_COUNT",
        "NATIVE_FORMAL_EXECUTION_COUNT",
    )
    if any(seed_audit.get(field) != 0 for field in zero_seed_fields):
        errors.append("one or more lock-round execution/RNG counters are nonzero")
    if seed_audit.get("development_geometry_seeds") != list(
        protocol.geometry_seeds
    ) or seed_audit.get("development_measurement_seeds") != list(
        protocol.measurement_seeds
    ):
        errors.append("seed audit differs from Development schedule")

    hashes = _read_json(artifact / "implementation_hashes.json")
    for label, item in hashes["files"].items():
        path = repository / item["path"]
        if not path.is_file() or file_sha256(path) != item["sha256"]:
            errors.append(f"implementation hash mismatch: {label}")
    binary = hashes.get("pcl_cli_binary")
    if binary:
        binary_path = repository / binary["path"]
        if not binary_path.is_file() or file_sha256(binary_path) != binary["sha256"]:
            errors.append("PCL CLI binary hash mismatch")

    test_report = _read_json(artifact / "test_report.json")
    manifest = _read_json(artifact / "run_manifest.json")
    decision = _read_json(artifact / "final_decision.json")
    if manifest.get("planned_snapshot_count") != 210 or manifest.get(
        "planned_trial_count"
    ) != 420:
        errors.append("run manifest plan counts changed")
    for field in (
        "phase_a_rng_instantiation_count",
        "phase_a_snapshot_generation_count",
        "phase_a_backend_execution_count",
        "phase_a_trial_result_count",
        "phase_b_execution_count",
    ):
        if manifest.get(field) != 0:
            errors.append(f"run manifest counter is nonzero: {field}")
    if manifest.get("phase_a_runner_invoked") is not False:
        errors.append("run manifest says Phase A runner was invoked")

    expected_fixed = {
        "BACKEND_PHASE_A_EXECUTED": False,
        "BACKEND_PHASE_A_COMPLETE": False,
        "TWO_INDEPENDENT_BACKENDS_QUALIFIED": False,
        "DAY1_SCIENTIFIC_VALIDATION_PASS": "NOT_EVALUATED",
        "PHASE_B_AUTHORIZED": False,
        "FULL_DEVELOPMENT_AUTHORIZED": False,
        "CONFIRMATORY_AUTHORIZED": False,
        "REAL_DATA_AUTHORIZED": False,
        "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED": False,
    }
    for field, expected in expected_fixed.items():
        if decision.get(field) != expected:
            errors.append(f"fixed non-execution decision changed: {field}")
    if decision.get("NEW_PROTOCOL_AMBIGUITIES_FOUND") is not False:
        errors.append("protocol ambiguities are not false")
    expected_self_audit = [
        {"name": name, "result": result}
        for name, result in self_audit.items()
    ]
    if decision.get("protocol_self_audit") != expected_self_audit:
        errors.append("decision protocol self-audit list changed")

    protected = {
        "open3d_modified": not _git_unchanged(
            repository, "src/zero_perturbation/open3d_backend.py"
        ),
        "pcl_implementation_modified": not _git_unchanged(
            repository,
            "src/zero_perturbation/pcl_backend.py",
            "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp",
            "tools/pcl_point_to_plane/rotation_metric_v3.hpp",
        ),
        "native_modified": not _git_unchanged(
            repository, "src/zero_perturbation/native_backend.py"
        ),
        "odi_modified": not _git_unchanged(
            repository, "src/degen_detector/odi_tracker.py", "configs/detector"
        ),
        "fast_lio2_modified": not _git_unchanged(
            repository, "src/fastlio2_adapter", "manifests/harmful_bias"
        ),
        "scene_generator_modified": not _git_unchanged(
            repository, "src/capture_range/day2_development_scene.py"
        ),
    }
    if any(protected.values()):
        errors.append(f"protected implementation changed: {protected}")
    changed = subprocess.run(
        ["git", "diff", "--name-only", BASELINE_COMMIT, "--"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if any("d50" in path.lower() for path in changed):
        errors.append("a d50 path changed")

    if _git_tag_target(repository, PCL_V3_ARCHIVE_TAG) != BASELINE_COMMIT:
        errors.append("PCL v3 pass archive tag target mismatch")
    if not PCL_V3_BUNDLE.is_file() or file_sha256(PCL_V3_BUNDLE) != PCL_V3_BUNDLE_SHA256:
        errors.append("PCL v3 pass bundle missing or hash mismatch")
    if _git_tag_target(repository, PROTOCOL_LOCK_TAG) != PROTOCOL_LOCK_COMMIT:
        errors.append("Phase A protocol-lock tag target mismatch")

    report = (artifact / "phase_a_lock_report.md").read_text(encoding="utf-8")
    for heading in (
        "## Decision",
        "## Planned matrix",
        "## Input and transform contracts",
        "## Backend parameter locks",
        "## Failure and Gate contracts",
        "## Non-execution and scope audit",
    ):
        if heading not in report:
            errors.append(f"lock report heading missing: {heading}")

    final_status_pass = bool(
        test_report.get("python_full_pytest_status") == "PASS"
        and test_report.get("pcl_v3_ctest_status") == "PASS"
        and decision.get("BACKEND_PHASE_A_PROTOCOL_LOCK_PASS") is True
        and decision.get("BACKEND_PHASE_A_RUN_AUTHORIZED") is True
        and lock.get("BACKEND_PHASE_A_RUN_AUTHORIZED") is True
    )
    if require_final:
        if not final_status_pass:
            errors.append("final test/lock authorization status is not PASS")
        if _git_tag_target(repository, LOCK_PASS_TAG) != subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip():
            errors.append("lock-pass tag does not point to final HEAD")
        if subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        ).stdout:
            errors.append("final worktree is not clean")

    return {
        "schema_version": "backend_phase_a_lock_verification_v1",
        "verification_pass": not errors,
        "error_count": len(errors),
        "errors": errors,
        "planned_snapshot_count": len(snapshots),
        "planned_trial_count": len(trials),
        "native_planned_trial_count": sum(
            "native" in row.get("backend", "").lower() for row in trials
        ),
        "artifact_sha_verification_pass": not _verify_sums(artifact),
        "structural_lock_pass": not errors,
        "final_status_pass": final_status_pass,
        "backend_phase_a_executed": decision.get("BACKEND_PHASE_A_EXECUTED"),
        "day1_scientific_validation_pass": decision.get(
            "DAY1_SCIENTIFIC_VALIDATION_PASS"
        ),
        **protected,
    }


__all__ = [
    "ARTIFACT_RELATIVE",
    "LOCK_PASS_TAG",
    "verify_backend_phase_a_lock",
]
