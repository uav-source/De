"""Independent verification of the Phase A v1.1 implementation lock."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any

from .backend_phase_a_protocol import file_sha256
from .backend_phase_a_v1_1 import (
    V1_1_ARTIFACT_RELATIVE,
    V1_1_LOCK_PASS_TAG,
    V1_1_PROTOCOL_SHA256,
    V1_INVALIDATION_RELATIVE,
    V1_PLACEHOLDER_SHA256,
    git_worktree_clean,
    scientific_contract_diff,
    validate_v1_1_lock_document,
    verify_planned_manifests,
)


REQUIRED_FILES = {
    "backend_phase_a_v1_1_protocol_lock.json",
    "phase_a_v1_to_v1_1_diff.json",
    "planned_snapshots.csv",
    "planned_trials.csv",
    "backend_parameter_contract.json",
    "implementation_hashes.json",
    "runner_contract.json",
    "runner_fixture_test_report.json",
    "dry_run_report.json",
    "seed_usage_audit.json",
    "artifact_verification.json",
    "run_manifest.json",
    "final_decision.json",
    "phase_a_v1_1_lock_report.md",
    "SHA256SUMS",
}


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def _verify_sums(artifact: Path) -> list[str]:
    sums = artifact / "SHA256SUMS"
    if not sums.is_file():
        return ["SHA256SUMS missing"]
    errors: list[str] = []
    declared: set[str] = set()
    for line in sums.read_text(encoding="utf-8").splitlines():
        try:
            expected, relative = line.split("  ", 1)
        except ValueError:
            errors.append(f"malformed SHA line: {line}")
            continue
        declared.add(relative)
        path = artifact / relative
        if not path.is_file():
            errors.append(f"declared artifact missing: {relative}")
        elif file_sha256(path) != expected:
            errors.append(f"artifact SHA mismatch: {relative}")
    actual = {
        path.relative_to(artifact).as_posix()
        for path in artifact.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if actual != declared:
        errors.append("SHA256SUMS inventory differs from artifact files")
    return errors


def _tag_target(root: Path, tag: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"{tag}^{{}}"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def verify_v1_1_lock(
    root: str | Path, *, require_final: bool = False
) -> dict[str, Any]:
    repository = Path(root).resolve()
    artifact = repository / V1_1_ARTIFACT_RELATIVE
    errors: list[str] = []
    if not artifact.is_dir():
        return {
            "schema_version": "backend_phase_a_v1_1_lock_verification_v1",
            "verification_pass": False,
            "error_count": 1,
            "errors": ["v1.1 lock artifact directory missing"],
        }
    actual = {path.name for path in artifact.iterdir() if path.is_file()}
    if actual != REQUIRED_FILES:
        errors.append(
            f"artifact inventory mismatch: missing={sorted(REQUIRED_FILES-actual)}, "
            f"extra={sorted(actual-REQUIRED_FILES)}"
        )
    errors.extend(_verify_sums(artifact))

    invalidation = repository / V1_INVALIDATION_RELATIVE
    if not invalidation.is_dir() or not (invalidation / "SHA256SUMS").is_file():
        errors.append("v1 invalidation evidence is missing")
    else:
        errors.extend(
            f"v1 invalidation: {error}" for error in _verify_sums(invalidation)
        )
        invalidation_decision = _json(invalidation / "final_decision.json")
        if not (
            invalidation_decision.get("PHASE_A_V1_RUN_AUTHORIZATION_INVALIDATED")
            is True
            and invalidation_decision.get("PHASE_A_V1_FORMAL_TRIALS_EXECUTED") == 0
        ):
            errors.append("v1 invalidation decision changed")

    try:
        lock = validate_v1_1_lock_document(
            artifact / "backend_phase_a_v1_1_protocol_lock.json", repository
        )
    except Exception as error:
        errors.append(f"v1.1 protocol lock validation failed: {error}")
        lock = {}

    try:
        plan = verify_planned_manifests(
            repository,
            artifact / "planned_snapshots.csv",
            artifact / "planned_trials.csv",
        )
    except Exception as error:
        errors.append(f"planned manifest verification failed: {error}")
        plan = {
            "planned_snapshot_count": 0,
            "planned_trial_count": 0,
            "native_planned_trial_count": 0,
        }

    diff = _json(artifact / "phase_a_v1_to_v1_1_diff.json")
    expected_diff = scientific_contract_diff(repository)
    if diff != expected_diff:
        errors.append("v1-to-v1.1 diff differs from independent recomputation")
    zero_fields = (
        "scientific_parameter_difference_count",
        "scene_difference_count",
        "seed_difference_count",
        "threshold_difference_count",
        "backend_parameter_difference_count",
        "metric_difference_count",
    )
    if any(diff.get(field) != 0 for field in zero_fields):
        errors.append("one or more scientific difference counts are nonzero")
    if diff.get("runner_implementation_difference_count", 0) <= 0:
        errors.append("runner implementation did not change from placeholder")

    implementation = _json(artifact / "implementation_hashes.json")
    if implementation != lock.get("implementation"):
        errors.append("implementation hashes differ from protocol lock")
    runner_item = implementation.get("files", {}).get("runner", {})
    if runner_item.get("sha256") == V1_PLACEHOLDER_SHA256:
        errors.append("v1.1 runner still has placeholder SHA")

    parameter = _json(artifact / "backend_parameter_contract.json")
    if not (
        parameter.get("OPEN3D_PARAMETER_LOCK_PASS") is True
        and parameter.get("PCL_PARAMETER_LOCK_PASS") is True
        and parameter.get("scientific_parameter_difference_count") == 0
    ):
        errors.append("backend parameter contract did not pass")

    runner = _json(artifact / "runner_contract.json")
    forbidden = {
        "--ignore-lock",
        "--override-parameters",
        "--change-thresholds",
        "--exclude-scene",
        "--skip-failure",
        "--replace-seed",
        "--backend-subset",
        "--native",
    }
    if not (
        runner.get("placeholder_present") is False
        and forbidden.isdisjoint(set(runner.get("supported_cli_arguments", [])))
        and runner.get("formal_execution_called") is False
    ):
        errors.append("runner contract evidence failed")

    fixture = _json(artifact / "runner_fixture_test_report.json")
    if not (
        fixture.get("fixture_snapshot_count") == 1
        and fixture.get("fixture_trial_count") == 2
        and fixture.get("open3d_fixture_trial_pass") is True
        and fixture.get("pcl_fixture_trial_pass") is True
        and fixture.get("backend_input_checksum_mismatch_count") == 0
        and fixture.get("is_formal_phase_a") is False
    ):
        errors.append("fixture execution evidence failed")

    dry = _json(artifact / "dry_run_report.json")
    if not (
        dry.get("dry_run_pass") is True
        and dry.get("DRY_RUN_PLANNED_SNAPSHOT_COUNT") == 210
        and dry.get("DRY_RUN_PLANNED_TRIAL_COUNT") == 420
        and dry.get("DRY_RUN_RNG_INSTANTIATION_COUNT") == 0
        and dry.get("DRY_RUN_BACKEND_EXECUTION_COUNT") == 0
    ):
        errors.append("dry-run evidence failed")

    seed = _json(artifact / "seed_usage_audit.json")
    zero_counters = (
        "FORMAL_RNG_INSTANTIATION_COUNT",
        "FORMAL_SNAPSHOT_GENERATION_COUNT",
        "FORMAL_BACKEND_EXECUTION_COUNT",
        "FORMAL_TRIAL_RESULT_COUNT",
        "CONFIRMATORY_SEED_ACCESS_COUNT",
        "OLD_CAPTURE_TEST_SEED_ACCESS_COUNT",
        "NATIVE_FORMAL_EXECUTION_COUNT",
    )
    if any(seed.get(field) != 0 for field in zero_counters):
        errors.append("one or more correction-round formal/seed counters are nonzero")

    artifact_verification = _json(artifact / "artifact_verification.json")
    if artifact_verification.get("precommit_structural_verification_pass") is not True:
        errors.append("artifact precommit structural verification is not PASS")
    manifest = _json(artifact / "run_manifest.json")
    if not (
        manifest.get("formal_phase_a_executed") is False
        and manifest.get("phase_b_executed") is False
        and manifest.get("git_push_performed") is False
    ):
        errors.append("correction-round run manifest changed")
    decision = _json(artifact / "final_decision.json")
    fixed = {
        "BACKEND_PHASE_A_V1_1_PROTOCOL_LOCK_PASS": True,
        "BACKEND_PHASE_A_V1_1_RUN_AUTHORIZED": True,
        "BACKEND_PHASE_A_V1_1_EXECUTED": False,
        "BACKEND_PHASE_A_COMPLETE": False,
        "TWO_INDEPENDENT_BACKENDS_QUALIFIED": False,
        "DAY1_SCIENTIFIC_VALIDATION_PASS": "NOT_EVALUATED",
        "PHASE_B_AUTHORIZED": False,
        "FULL_DEVELOPMENT_AUTHORIZED": False,
        "CONFIRMATORY_AUTHORIZED": False,
        "REAL_DATA_AUTHORIZED": False,
        "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED": False,
    }
    for field, expected in fixed.items():
        if decision.get(field) != expected:
            errors.append(f"final decision mismatch: {field}")

    with (artifact / "planned_trials.csv").open(newline="", encoding="utf-8") as stream:
        planned_rows = list(csv.DictReader(stream))
    if any("native" in row.get("backend", "").lower() for row in planned_rows):
        errors.append("Native appears in v1.1 planned trials")

    final_status_pass = bool(
        not errors
        and decision.get("BACKEND_PHASE_A_V1_1_PROTOCOL_LOCK_PASS") is True
        and decision.get("BACKEND_PHASE_A_V1_1_RUN_AUTHORIZED") is True
    )
    if require_final:
        head = _git_output(repository, "rev-parse", "HEAD")
        if _tag_target(repository, V1_1_LOCK_PASS_TAG) != head:
            errors.append("v1.1 lock-pass tag does not point to HEAD")
        if not git_worktree_clean(repository):
            errors.append("final worktree is not clean")

    return {
        "schema_version": "backend_phase_a_v1_1_lock_verification_v1",
        "verification_pass": not errors,
        "error_count": len(errors),
        "errors": errors,
        "artifact_sha_verification_pass": not _verify_sums(artifact),
        "planned_snapshot_count": plan["planned_snapshot_count"],
        "planned_trial_count": plan["planned_trial_count"],
        "native_planned_trial_count": plan["native_planned_trial_count"],
        "formal_phase_a_executed": False,
        "day1_scientific_validation_pass": "NOT_EVALUATED",
        "final_status_pass": final_status_pass,
        "protocol_sha256": V1_1_PROTOCOL_SHA256,
    }


def _git_output(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


__all__ = ["REQUIRED_FILES", "verify_v1_1_lock"]
