#!/usr/bin/env python3
"""Publish the compact, seed-free v3 bootstrap-repair r2 pre-run package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


FROZEN_MAMBA_ROOT_PREFIX = "/home/lj/.local/share/degen-lio-micromamba"
SOURCE_REPOSITORY = Path("/home/lj/Degen-LIO")
FORMAL_RUNTIME_ROOT = Path(
    "/home/lj/zero_perturbation_runtime/confirmatory/synthetic_confirmatory_v3"
)
FAILED_CANDIDATE_COMMIT = "37a2625365012b0deefb59bbc068fd8283174b5a"
FAILED_CANDIDATE_TAG = (
    "archive/zero-perturbation-synthetic-confirmatory-v3-"
    "bootstrap-repair-candidate"
)
FAILED_QUALIFICATION_ROOT = Path(
    "/home/lj/zero_perturbation_runtime/qualification/"
    "v3_bootstrap_state_machine_v1"
)
QUALIFICATION_ROOT = Path(
    "/home/lj/zero_perturbation_runtime/qualification/"
    "v3_bootstrap_state_machine_requalification_v2"
)
REPAIR_BRANCH = "fix/zero-perturbation-v3-formal-bootstrap-state-machine"
CANDIDATE_TAG = (
    "archive/zero-perturbation-synthetic-confirmatory-v3-"
    "publisher-envelope-repair-candidate"
)
FINAL_TAG = (
    "archive/zero-perturbation-synthetic-confirmatory-v3-"
    "bootstrap-repair-r2-pre-run-pass"
)
OLD_PRERUN_COMMIT = "38d3dcddd818eb9ae243f73837d863f52bd1e233"
OLD_PRERUN_TAG = "archive/zero-perturbation-synthetic-confirmatory-v3-pre-run-pass"
FAILURE_TAG = (
    "archive/zero-perturbation-synthetic-confirmatory-v3-"
    "bootstrap-contract-fail"
)
OLD_PRERUN_BUNDLE = Path(
    "/tmp/zero-perturbation-synthetic-confirmatory-v3-pre-run.bundle"
)
OLD_PRERUN_BUNDLE_SHA256 = (
    "c78dcc8b9177256b1ed11dfe4e9dcfd24a1f586035e211e3514ba63d7ba246f7"
)
FAILURE_BUNDLE = Path(
    "/tmp/zero-perturbation-synthetic-confirmatory-v3-bootstrap-contract-fail.bundle"
)
FAILURE_BUNDLE_SHA256 = (
    "754c0492ea3feceeb8547470b78cd3162ad957fa88552c27434950686782f363"
)
DESTINATION_RELATIVE = Path(
    "artifacts/synthetic_confirmatory_v3_bootstrap_repair_r2_prerun"
)
MANIFEST_RELATIVE = Path(
    "frozen_assets/synthetic_confirmatory_formal_manifest_v3_bootstrap_repair_r2.json"
)
PROFILE_RELATIVE = Path(
    "frozen_assets/"
    "synthetic_confirmatory_v3_execution_profile_bootstrap_repair_r2.json"
)
DEFAULT_QUALIFICATION_REPORT = (
    QUALIFICATION_ROOT
    / "working_inventory/bootstrap_repair_requalification_v2.json"
)
DEFAULT_TEST_REPORT = QUALIFICATION_ROOT / "test_logs/combined_test_report.json"
ROOT_CAUSE = "QUALIFIER_TO_FROZEN_PUBLISHER_FIXTURE_ENVELOPE_MISMATCH"

FIXTURE_TABLES = (
    "fixture_trial_inventory.csv",
    "fixture_snapshot_inventory.csv",
    "fixture_backend_summary.csv",
    "fixture_failure_inventory.csv",
    "fixture_pairing_audit.csv",
    "fixture_resume_equivalence.csv",
    "fixture_gate_summary.csv",
)
FIXTURE_FIGURES = (
    "fixture_execution_matrix.png",
    "fixture_failure_matrix.png",
    "fixture_update_metrics.png",
)
FIXTURE_ROOT_FILES = (
    "synthetic_confirmatory_report.md",
    "primary_analysis.json",
    "independent_verification.json",
    "final_decision.json",
    "run_manifest.json",
    "SHA256SUMS",
    "artifact_verification.json",
)
PUBLISHER_FIELDS = (
    "backend_execution_count",
    "fixture_snapshot_count",
    "fixture_trial_count",
    "formal_confirmatory_science_evaluated",
    "formal_v2_seed_reference_count",
    "fresh_resume_scientific_equivalence",
    "resume_backend_execution_count",
    "schema_version",
)
RAW_FIELDS = tuple(
    "formal_v3_seed_reference_count"
    if name == "formal_v2_seed_reference_count"
    else name
    for name in PUBLISHER_FIELDS
)
SEED_FIELDS = (
    "formal_v1_seed_reference_count",
    "formal_v2_seed_reference_count",
    "formal_v3_seed_reference_count",
    "confirmatory_seed_access_count",
    "confirmatory_rng_instantiation_count",
    "confirmatory_snapshot_construction_count",
    "confirmatory_backend_execution_count",
)
SCIENTIFIC_ZERO_FIELDS = (
    "scene_difference_count",
    "condition_difference_count",
    "planned_snapshot_count_difference",
    "planned_trial_count_difference",
    "seed_namespace_difference_count",
    "seed_value_difference_count",
    "snapshot_scientific_schema_difference_count",
    "trial_scientific_field_difference_count",
    "lineage_semantics_difference_count",
    "phase_a_closure_difference_count",
    "backend_algorithm_difference_count",
    "backend_parameter_difference_count",
    "translation_metric_difference_count",
    "rotation_metric_difference_count",
    "quantile_method_difference_count",
    "H1_definition_difference_count",
    "H1_threshold_difference_count",
    "H2_definition_difference_count",
    "H2_threshold_difference_count",
    "H3_definition_difference_count",
    "H3_threshold_difference_count",
    "H4_definition_difference_count",
    "H4_threshold_difference_count",
    "H5_definition_difference_count",
    "H5_threshold_difference_count",
    "H6_definition_difference_count",
    "H6_threshold_difference_count",
    "common_association_difference_count",
    "turnover_difference_count",
    "systematic_offset_difference_count",
    "frozen_model_file_difference_count",
    "frozen_model_parameter_difference_count",
)
PROTECTED_SHA256 = {
    "protocols/synthetic_confirmatory_protocol_v3.json": (
        "216bfe1b0f9d5fef0f9c11235099979b56394d99ea82452d0f476ddc2d777831"
    ),
    "protocols/synthetic_confirmatory_gate_contract_v3.json": (
        "3f66adb54705d2a08803f6916291bc543f14401f22556468576c2f09b66f30e1"
    ),
    "protocols/synthetic_confirmatory_planned_snapshots_v3.csv": (
        "dbe75e9df8545b1c61c61bac2baa3ee2c525aeda65b9db10215c61863b3b29ef"
    ),
    "protocols/synthetic_confirmatory_planned_trials_v3.csv": (
        "f5b2f6fb84e3a64e686eacfc22c8ec90d6bc9c14860116e8b51f4d628a77b8d4"
    ),
    "frozen_assets/synthetic_confirmatory_v3_seed_schedule.json": (
        "a0e7921b9c1282d4b12e3e0cccccd3d66ee3cbc10ff5b4666a6c0cb01f521fbc"
    ),
    "frozen_assets/confirmatory_development_trained_models_v1.json": (
        "99806f83d3a0d2393ee7e36e8c06f14a1a8a44fb8d02b074ebc2d9fe750d0872"
    ),
    "bin/pcl_point_to_plane_cli": (
        "d42ce655df74117f0e6965c9df1326526fabba9f4e65ed10a5644ed911fad7ff"
    ),
    "src/phase_a_harness/formal_runtime_state_machine.py": (
        "3f4c9a84865c3085e7c31928a73fd76ce31e139035dd56b608cf299b9c78a3"
    ),
    "src/phase_a_harness/runtime_lifecycle_io.py": (
        "62c69842f67f9da9fd5a6af917a7951995c6dba3b2fd2ca6ab4f6143d56a9b76"
    ),
    "src/phase_a_harness/runtime_lifecycle_fixture.py": (
        "14bc9be9d3c6c6ace54d06140b0179e250ffaf32b0c7bf466c8210bbce47d394"
    ),
    "src/phase_a_harness/synthetic_confirmatory_v2_analysis.py": (
        "183ed8b8c352214345cf4add7c856982955bfbd8070a59bd5036b17e4c461f8c"
    ),
    "src/phase_a_harness/synthetic_confirmatory_v2_independent_verifier.py": (
        "4f136a7e1fd025c6a848bfeafa6b96a9c5b643525fa86fa24360e71a6c2ff2d2"
    ),
    "src/phase_a_harness/synthetic_confirmatory_v2_publisher.py": (
        "5e6bfebbcc23545609b9ea8528d08a5d8443cff748b8ba6d0cf719b417ffc217"
    ),
    "src/phase_a_harness/synthetic_confirmatory_v2_artifact_verifier.py": (
        "7f7f38fdbb5e16cc6ac7cf6b3b4e46f5c0880351f586dd89242a9bc4c4038a52"
    ),
}
EXPECTED_TEST_COUNTS = {
    "envelope_compatibility": 23,
    "bootstrap_state_machine": 35,
    "runtime_lifecycle_specialized": 117,
    "v3_specialized": 26,
    "v2_scientific_chain_regression": 66,
    "full_harness": 501,
    "pcl_fixture": 3,
}


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _strict_object(path: str | Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in items:
            if key in value:
                raise ValueError(f"duplicate JSON key in {path}: {key}")
            value[key] = item
        return value

    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise FileNotFoundError(f"required JSON is absent or linked: {candidate}")
    value = json.loads(
        candidate.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if type(value) is not dict:
        raise ValueError(f"JSON root is not an object: {candidate}")
    return value


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments],
        cwd=repository,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def _bundle_pass(repository: Path, path: Path, expected: str) -> bool:
    if path.is_symlink() or not path.is_file() or _sha256(path) != expected:
        return False
    return (
        subprocess.run(
            ["git", "bundle", "verify", str(path)],
            cwd=repository,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        ).returncode
        == 0
    )


def _tree_binding(root: Path) -> dict[str, Any]:
    if root.is_symlink() or not root.is_dir():
        raise FileNotFoundError(f"preserved qualification root is absent: {root}")
    rows: list[dict[str, Any]] = []
    unsafe: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            unsafe.append(relative)
        elif path.is_file():
            rows.append(
                {
                    "path": relative,
                    "sha256": _sha256(path),
                    "size_bytes": path.stat().st_size,
                }
            )
    encoded = json.dumps(
        rows, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return {
        "file_count": len(rows),
        "file_content_bytes": sum(row["size_bytes"] for row in rows),
        "inventory_sha256": hashlib.sha256(encoded).hexdigest(),
        "symlink_paths": unsafe,
    }


def _assert_environment(repository: Path) -> None:
    if os.environ.get("PYTHONNOUSERSITE") != "1":
        raise PermissionError("publication requires PYTHONNOUSERSITE=1")
    if os.environ.get("MAMBA_ROOT_PREFIX") != FROZEN_MAMBA_ROOT_PREFIX:
        raise PermissionError("publication requires frozen MAMBA_ROOT_PREFIX")
    if (
        repository == SOURCE_REPOSITORY.resolve()
        or SOURCE_REPOSITORY.resolve() in repository.parents
    ):
        raise PermissionError("publication must run in the standalone harness")
    if FORMAL_RUNTIME_ROOT.exists() or FORMAL_RUNTIME_ROOT.is_symlink():
        raise PermissionError("formal v3 runtime root exists")
    source = SOURCE_REPOSITORY.resolve()
    for entry in [
        *sys.path,
        *(item for item in os.environ.get("PYTHONPATH", "").split(os.pathsep) if item),
    ]:
        candidate = (Path.cwd() if not entry else Path(entry)).resolve()
        if (
            candidate == source
            or source in candidate.parents
            or candidate in source.parents
        ):
            raise PermissionError("source repository is on the Python search path")


def _assert_external_file(path: Path) -> Path:
    candidate = Path(os.path.abspath(os.fspath(path)))
    if QUALIFICATION_ROOT not in candidate.parents:
        raise ValueError(f"evidence is outside the new qualification root: {candidate}")
    if candidate.is_symlink() or not candidate.is_file():
        raise FileNotFoundError(f"evidence is absent or linked: {candidate}")
    cursor = candidate
    while cursor != QUALIFICATION_ROOT.parent:
        if cursor.is_symlink():
            raise ValueError(f"evidence path has a symlink component: {cursor}")
        cursor = cursor.parent
    return candidate


def _candidate_binding(
    repository: Path, candidate_commit: str, candidate_tag: str
) -> dict[str, Any]:
    if candidate_tag != CANDIDATE_TAG:
        raise PermissionError("candidate tag name differs from the frozen r2 name")
    values = {
        "head": _git(repository, "rev-parse", "HEAD^{commit}"),
        "branch": _git(repository, "branch", "--show-current"),
        "candidate_tag_commit": _git(
            repository, "rev-parse", f"{candidate_tag}^{{commit}}"
        ),
        "failed_candidate_tag_commit": _git(
            repository, "rev-parse", f"{FAILED_CANDIDATE_TAG}^{{commit}}"
        ),
        "old_prerun_tag_commit": _git(
            repository, "rev-parse", f"{OLD_PRERUN_TAG}^{{commit}}"
        ),
        "failure_tag_commit": _git(
            repository, "rev-parse", f"{FAILURE_TAG}^{{commit}}"
        ),
        "status": _git(
            repository, "status", "--porcelain=v1", "--untracked-files=all"
        ),
    }
    if not (
        values["head"] == candidate_commit
        and values["branch"] == REPAIR_BRANCH
        and values["candidate_tag_commit"] == candidate_commit
        and values["failed_candidate_tag_commit"] == FAILED_CANDIDATE_COMMIT
        and values["old_prerun_tag_commit"] == OLD_PRERUN_COMMIT
        and values["failure_tag_commit"] == OLD_PRERUN_COMMIT
        and values["status"] == ""
        and _bundle_pass(repository, OLD_PRERUN_BUNDLE, OLD_PRERUN_BUNDLE_SHA256)
        and _bundle_pass(repository, FAILURE_BUNDLE, FAILURE_BUNDLE_SHA256)
    ):
        raise PermissionError("candidate or preserved Git/archive binding failed")
    return values


def _require_qualification(value: Mapping[str, Any]) -> None:
    required = {
        "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": True,
        "FIXTURE_ENVELOPE_COMPATIBILITY_PASS": True,
        "PUBLISHER_INPUT_SCHEMA_PASS": True,
        "PUBLISHER_INVENTORY_PASS": True,
        "ARTIFACT_VERIFIER_PASS": True,
        "FRESH_FIXTURE_EXECUTION_PASS": True,
        "RESUME_FIXTURE_EXECUTION_PASS": True,
        "ABSENT_STATE_PASS": True,
        "BOOTSTRAP_ONLY_STATE_PASS": True,
        "RESUMABLE_STATE_PASS": True,
        "INVALID_STATE_PASS": True,
        "COMMAND_LOG_PRELOCK_INTERRUPTION_PASS": True,
        "BOOTSTRAP_ONLY_RECOVERY_PASS": True,
        "LOCK_ATOMIC_INTERRUPTION_PASS": True,
        "PARTIAL_LOCK_ACCEPTED_COUNT": 0,
        "VALID_SNAPSHOT_REEXECUTION_COUNT": 0,
        "VALID_TRIAL_REEXECUTION_COUNT": 0,
        "SNAPSHOT_CHECKSUM_CHANGE_AFTER_RESUME": 0,
        "TRIAL_CHECKSUM_CHANGE_AFTER_RESUME": 0,
        "PRIMARY_INDEPENDENT_DIFFERENCE_COUNT": 0,
        "ALL_GIT_GATES_PASS": True,
        "V3_SEED_ACCESS_COUNT": 0,
        "V3_RNG_INSTANTIATION_COUNT": 0,
        "V3_SNAPSHOT_CONSTRUCTION_COUNT": 0,
        "V3_BACKEND_EXECUTION_COUNT": 0,
        "V3_TRIAL_RESULT_COUNT": 0,
    }
    failures = [
        f"{name}={value.get(name)!r}"
        for name, expected in required.items()
        if type(value.get(name)) is not type(expected)
        or value.get(name) != expected
    ]
    invalid = value.get("invalid_state_rejection", {})
    if (
        type(invalid) is not dict
        or invalid.get("INVALID_RUNTIME_STATE_REJECTION_COUNT") != 20
        or invalid.get("INVALID_RUNTIME_STATE_FALSE_ACCEPT_COUNT") != 0
    ):
        failures.append("invalid-state 20/0 evidence")
    for name in (
        "raw_v3_fixture_envelope",
        "frozen_publisher_fixture_envelope",
        "publisher_input_validation",
        "fixture_envelope_scientific_equivalence",
        "fixture_seed_reference_audit",
        "publication",
        "artifact_verification",
        "formal_dry_run",
    ):
        if type(value.get(name)) is not dict:
            failures.append(f"missing mapping {name}")
    if failures:
        raise PermissionError("qualification evidence failed: " + ", ".join(failures))


def _normalize_tests(value: Mapping[str, Any], candidate_commit: str) -> dict[str, Any]:
    groups = value.get("groups")
    if type(groups) is not dict or set(groups) != set(EXPECTED_TEST_COUNTS):
        raise ValueError("test report group inventory differs from the frozen matrix")
    for name, expected in EXPECTED_TEST_COUNTS.items():
        row = groups[name]
        if not (
            type(row) is dict
            and row.get("tests") == expected
            and row.get("passed") == expected
            and row.get("failures") == 0
            and row.get("errors") == 0
            and row.get("skipped") == 0
            and isinstance(row.get("junit_sha256"), str)
            and len(row["junit_sha256"]) == 64
        ):
            raise PermissionError(f"test group did not pass exactly: {name}")
    if (
        value.get("TEST_SUITE_PASS") is not True
        or value.get("candidate_commit") != candidate_commit
        or value.get("formal_runtime_root_created") is not False
    ):
        raise PermissionError("combined test report binding failed")
    return json.loads(json.dumps(value, allow_nan=False))


def _protected_bindings(repository: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for relative, expected in PROTECTED_SHA256.items():
        actual = _sha256(repository / relative)
        if actual != expected:
            raise PermissionError(f"protected file changed: {relative}")
        result[relative] = {
            "expected_sha256": expected,
            "actual_sha256": actual,
        }
    return result


def _write_package(
    destination: Path,
    payload: Mapping[str, Any | str],
    verifier: Any,
) -> dict[str, Any]:
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"refusing to replace pre-run artifact: {destination}")
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=parent)
    )
    staging = temporary / "artifact"
    staging.mkdir()
    try:
        for name, value in payload.items():
            data = value.encode("utf-8") if isinstance(value, str) else _json_bytes(value)
            (staging / name).write_bytes(data)
        manifest_stream = io.StringIO(newline="")
        writer = csv.DictWriter(
            manifest_stream,
            fieldnames=("path", "size_bytes", "sha256"),
            lineterminator="\n",
        )
        writer.writeheader()
        for name in sorted(payload):
            path = staging / name
            writer.writerow(
                {
                    "path": name,
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
        (staging / "MANIFEST.csv").write_text(
            manifest_stream.getvalue(), encoding="utf-8", newline=""
        )
        checksum_names = sorted((*payload, "MANIFEST.csv"))
        (staging / "SHA256SUMS").write_text(
            "".join(
                f"{_sha256(staging / name)}  {name}\n" for name in checksum_names
            ),
            encoding="utf-8",
        )
        staged = verifier(staging)
        if staged.get("PRE_RUN_ARTIFACT_VERIFICATION_PASS") is not True:
            raise RuntimeError(
                "staged pre-run artifact verification failed: "
                + json.dumps(staged, sort_keys=True)
            )
        os.replace(staging, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    published = verifier(destination)
    if published != staged:
        raise RuntimeError("published artifact verification differs from staging")
    return published


def build_artifact(
    *,
    repository: Path,
    candidate_commit: str,
    candidate_tag: str,
    qualification_report_path: Path,
    test_report_path: Path,
) -> dict[str, Any]:
    _assert_environment(repository)
    destination = repository / DESTINATION_RELATIVE
    git = _candidate_binding(repository, candidate_commit, candidate_tag)
    previous_before = _tree_binding(FAILED_QUALIFICATION_ROOT)
    qualification_path = _assert_external_file(qualification_report_path)
    tests_path = _assert_external_file(test_report_path)
    qualification = _strict_object(qualification_path)
    tests = _normalize_tests(_strict_object(tests_path), candidate_commit)
    _require_qualification(qualification)
    protected = _protected_bindings(repository)

    sys.path.insert(0, str(repository / "src"))
    from phase_a_harness.synthetic_confirmatory_v3_bootstrap_repair_r2_artifact_verifier import (
        PAYLOAD_FILES,
        verify_bootstrap_repair_r2_prerun_artifact,
    )
    from phase_a_harness.synthetic_confirmatory_v3_contract import load_v3_contract

    manifest_path = repository / MANIFEST_RELATIVE
    profile_path = repository / PROFILE_RELATIVE
    manifest = load_v3_contract(manifest_path)
    profile = _strict_object(profile_path)
    if (
        manifest.get("expected_release_tag") != FINAL_TAG
        or manifest.get("run_id") != "synthetic-confirmatory-v3"
        or manifest.get("planned_snapshot_count") != 595
        or manifest.get("planned_trial_count") != 1190
        or profile.get("expected_release_tag") != FINAL_TAG
        or profile.get("formal_execution_state") != "NOT_EXECUTED"
    ):
        raise PermissionError("r2 manifest/profile formal identity failed")

    raw = qualification["raw_v3_fixture_envelope"]
    adapted = qualification["frozen_publisher_fixture_envelope"]
    seed_audit = qualification["fixture_seed_reference_audit"]
    equivalence = qualification["fixture_envelope_scientific_equivalence"]
    input_validation = qualification["publisher_input_validation"]
    publication = qualification["publication"]
    artifact_live = qualification["artifact_verification"]
    dry = qualification["formal_dry_run"]
    if (
        raw.get("schema_version")
        != "synthetic_confirmatory_v3_bootstrap_fixture_run_v1"
        or tuple(sorted(raw)) != tuple(sorted(RAW_FIELDS))
        or adapted.get("schema_version")
        != "synthetic_confirmatory_v2_fixture_run_v1"
        or tuple(sorted(adapted)) != tuple(sorted(PUBLISHER_FIELDS))
        or any(
            type(seed_audit.get(name)) is not int or seed_audit.get(name) != 0
            for name in SEED_FIELDS
        )
        or equivalence.get(
            "FIXTURE_ENVELOPE_SCIENTIFIC_LEAF_DIFFERENCE_COUNT"
        )
        != 0
        or equivalence.get(
            "FIXTURE_ENVELOPE_SCIENTIFIC_MAX_NUMERICAL_DIFFERENCE"
        )
        != 0.0
        or equivalence.get("original_input_modified") is not False
    ):
        raise PermissionError("adapter or zero-seed evidence failed")
    plan_required = {
        "V3_DRY_RUN_PASS": True,
        "V3_FORMAL_RUNTIME_ROOT_NOT_CREATED": True,
        "planned_snapshot_count": 595,
        "unique_snapshot_count": 595,
        "planned_trial_count": 1190,
        "unique_trial_count": 1190,
        "duplicate_snapshot_count": 0,
        "duplicate_trial_count": 0,
        "pairing_violation_count": 0,
        "independent_pseudoreplication_count": 0,
        "native_trial_count": 0,
    }
    if any(dry.get(name) != expected for name, expected in plan_required.items()):
        raise PermissionError("formal dry-run cardinality failed")
    if dry.get("condition_snapshot_counts") != {
        "FULL_NOISE": 525,
        "IDEAL_MATCHED": 35,
        "INDEPENDENT_NOISE_FREE": 35,
    } or dry.get("backend_trial_counts") != {
        "Native": 0,
        "Open3D": 595,
        "PCL": 595,
    }:
        raise PermissionError("formal dry-run condition/backend counts failed")

    artifact_verification = {
        **json.loads(json.dumps(artifact_live, allow_nan=False)),
        "ARTIFACT_VERIFIER_PASS": (
            artifact_live.get("FIXTURE_ARTIFACT_VERIFICATION_PASS") is True
        ),
    }
    publisher_inventory = {
        "schema_version": "synthetic_confirmatory_v3_fixture_publisher_inventory_r2",
        "PUBLISHER_INVENTORY_PASS": (
            publication.get("FIXTURE_ARTIFACT_VERIFICATION_PASS") is True
            and publication.get("published_file_count") == 17
        ),
        "table_count": 7,
        "tables": list(FIXTURE_TABLES),
        "figure_count": 3,
        "figures": list(FIXTURE_FIGURES),
        "root_file_count": 7,
        "root_files": list(FIXTURE_ROOT_FILES),
        "published_file_count": publication.get("published_file_count"),
        "missing_count": len(artifact_live.get("missing_required_files", [])),
        "extra_count": len(artifact_live.get("extra_files", [])),
        "sha256_mismatch_count": len(
            artifact_live.get("sha256_mismatch_files", [])
        ),
        "publication": publication,
    }
    git_reports = qualification["git_gate_reports"]
    git_gate_report = {
        "schema_version": "synthetic_confirmatory_v3_r2_git_gate_report_v1",
        "reports": git_reports,
        "checkpoint_count": len(git_reports),
        "POST_PUBLISHER_GIT_GATE_PASS": any(
            row.get("checkpoint") == "POST_PUBLISHER_GIT_GATE"
            and row.get("RUNTIME_GIT_GATE_PASS") is True
            for row in git_reports
        ),
        "FINAL_GIT_GATE_PASS": any(
            row.get("checkpoint") == "FINAL_GIT_GATE"
            and row.get("RUNTIME_GIT_GATE_PASS") is True
            for row in git_reports
        ),
        "ALL_GIT_GATES_PASS": qualification["ALL_GIT_GATES_PASS"],
    }
    scientific_diff = {
        "schema_version": (
            "synthetic_confirmatory_v3_publisher_envelope_repair_scientific_diff_v1"
        ),
        **{name: 0 for name in SCIENTIFIC_ZERO_FIELDS},
        "allowed_differences": {
            "fixture_envelope_schema_adapter_difference_count": 1,
            "qualification_version_metadata_difference_count": 1,
            "formal_manifest_binding_difference_count": 1,
            "pre_run_artifact_difference_count": 1,
            "expected_tag_difference_count": 1,
        },
    }
    changed = [
        name
        for name in _git(
            repository,
            "diff",
            "--name-only",
            f"{FAILED_CANDIDATE_COMMIT}..{candidate_commit}",
        ).splitlines()
        if name
    ]
    protected_paths = {
        "src/phase_a_harness/formal_runtime_state_machine.py",
        "src/phase_a_harness/runtime_lifecycle_io.py",
        "src/phase_a_harness/runtime_lifecycle_fixture.py",
        "src/phase_a_harness/synthetic_confirmatory_v2_analysis.py",
        "src/phase_a_harness/synthetic_confirmatory_v2_independent_verifier.py",
        "src/phase_a_harness/synthetic_confirmatory_v2_publisher.py",
        "src/phase_a_harness/synthetic_confirmatory_v2_artifact_verifier.py",
        *PROTECTED_SHA256.keys(),
    }
    forbidden_changed = sorted(set(changed) & protected_paths)
    if forbidden_changed:
        raise PermissionError(f"candidate changed protected paths: {forbidden_changed}")

    previous_binding = {
        "schema_version": (
            "synthetic_confirmatory_v3_previous_qualification_root_binding_v1"
        ),
        "PREVIOUS_QUALIFICATION_ROOT_PRESERVED": True,
        "root": str(FAILED_QUALIFICATION_ROOT),
        "read_only_use": True,
        "continued_or_reused": False,
        "initial_audit_inventory_sha256": (
            "3b628bf1d06ce29e0102bf5283aea869238b04449a92ffd8136664428b9c78a3"
        ),
        **previous_before,
    }
    failure_binding = {
        "schema_version": (
            "synthetic_confirmatory_v3_publisher_envelope_failure_binding_v1"
        ),
        "root_cause": ROOT_CAUSE,
        "failure_candidate_commit": FAILED_CANDIDATE_COMMIT,
        "failure_candidate_tag": FAILED_CANDIDATE_TAG,
        "failure_qualification_root": str(FAILED_QUALIFICATION_ROOT),
        "publisher_exception_type": "ValueError",
        "qualifier_source": {
            "path": "scripts/qualify_synthetic_confirmatory_v3_bootstrap_repair.py",
            "line_start": 456,
            "line_end": 472,
            "sha256": _sha256(
                repository
                / "scripts/qualify_synthetic_confirmatory_v3_bootstrap_repair.py"
            ),
        },
        "publisher_contract_source": {
            "path": "src/phase_a_harness/synthetic_confirmatory_v2_publisher.py",
            "line_start": 523,
            "line_end": 556,
            "sha256": protected[
                "src/phase_a_harness/synthetic_confirmatory_v2_publisher.py"
            ]["actual_sha256"],
        },
        "passed_before_failure": [
            "FORMAL_BOOTSTRAP_STATE_MACHINE_IMPLEMENTATION",
            "FRESH_FIXTURE_EXECUTION_PASS",
            "RESUME_FIXTURE_EXECUTION_PASS",
            "PRIMARY_INDEPENDENT_DIFFERENCE_COUNT",
        ],
        "not_reached": ["PUBLISHER_INVENTORY_PASS", "ARTIFACT_VERIFIER_PASS"],
        "PUBLISHER_INPUT_CONTRACT_PASS": False,
        "PUBLISHER_INVENTORY_PASS": False,
        "ARTIFACT_VERIFIER_PASS": False,
        "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": False,
        "SYNTHETIC_CONFIRMATORY_V3_BOOTSTRAP_REPAIR_PRE_RUN_QUALIFICATION_PASS": False,
        "CONFIRMATORY_V3_RUN_AUTHORIZED": False,
        "V3_SEED_ACCESS_COUNT": 0,
    }
    implementation_manifest = {
        "schema_version": (
            "synthetic_confirmatory_v3_publisher_envelope_repair_implementation_v1"
        ),
        "candidate_branch": REPAIR_BRANCH,
        "candidate_commit": candidate_commit,
        "candidate_tag": candidate_tag,
        "base_failure_candidate_commit": FAILED_CANDIDATE_COMMIT,
        "changed_files": changed,
        "changed_file_count": len(changed),
        "protected_changed_files": forbidden_changed,
        "implementation_file_sha256": {
            name: _sha256(repository / name) for name in changed
        },
    }
    final_binding = {
        "schema_version": "synthetic_confirmatory_v3_r2_final_git_binding_v1",
        "FINAL_GIT_BINDING_PASS": True,
        "candidate_commit": candidate_commit,
        "candidate_tag": candidate_tag,
        "candidate_worktree_clean_before_publication": True,
        "required_final_tag": FINAL_TAG,
        "final_transition_scope": [DESTINATION_RELATIVE.as_posix()],
        "final_commit_and_tag_require_post_import_read_only_confirmation": True,
    }
    decision = {
        "schema_version": (
            "synthetic_confirmatory_v3_bootstrap_repair_r2_final_decision_v1"
        ),
        "PREVIOUS_PUBLISHER_FAILURE_PRESERVED": True,
        "PREVIOUS_CANDIDATE_TAG_PRESERVED": True,
        "PREVIOUS_QUALIFICATION_ROOT_PRESERVED": True,
        "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": True,
        "FIXTURE_ENVELOPE_COMPATIBILITY_PASS": True,
        "SYNTHETIC_CONFIRMATORY_V3_PRE_RUN_QUALIFICATION_PASS": True,
        "SYNTHETIC_CONFIRMATORY_V3_BOOTSTRAP_REPAIR_PRE_RUN_QUALIFICATION_PASS": True,
        "V3_SEED_SET_REUSE_AUTHORIZED": True,
        "CONFIRMATORY_V3_RUN_AUTHORIZED": True,
        "SYNTHETIC_CONFIRMATORY_V3_EXECUTED": False,
        "SYNTHETIC_CONFIRMATORY_V3_COMPLETE": False,
        "SYNTHETIC_CONFIRMATORY_V3_PASS": "NOT_EVALUATED",
        "REAL_DATA_RUN_AUTHORIZED": False,
        "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED": False,
        "V4_CREATED": False,
    }
    run_manifest = {
        "schema_version": (
            "synthetic_confirmatory_v3_bootstrap_repair_r2_prerun_manifest_v1"
        ),
        "candidate_commit": candidate_commit,
        "candidate_tag": candidate_tag,
        "qualification_root": str(QUALIFICATION_ROOT),
        "qualification_report_path": str(qualification_path),
        "qualification_report_sha256": _sha256(qualification_path),
        "test_report_path": str(tests_path),
        "test_report_sha256": _sha256(tests_path),
        "formal_manifest_path": MANIFEST_RELATIVE.as_posix(),
        "formal_manifest_sha256": _sha256(manifest_path),
        "formal_manifest_payload_sha256": manifest["manifest_payload_sha256"],
        "planned_snapshot_count": 595,
        "planned_trial_count": 1190,
        "formal_seed_access_count": 0,
        "formal_rng_instantiation_count": 0,
        "formal_snapshot_construction_count": 0,
        "formal_backend_execution_count": 0,
        "formal_trial_result_count": 0,
        "formal_runtime_root_created": False,
    }
    payload: dict[str, Any | str] = {
        "previous_candidate_failure_binding.json": {
            "schema_version": (
                "synthetic_confirmatory_v3_previous_candidate_failure_binding_v1"
            ),
            "PREVIOUS_PUBLISHER_FAILURE_PRESERVED": True,
            "candidate_commit": FAILED_CANDIDATE_COMMIT,
            "candidate_tag": FAILED_CANDIDATE_TAG,
            "qualification_root": str(FAILED_QUALIFICATION_ROOT),
            "historical_decision": "FAIL",
        },
        "previous_candidate_tag_binding.json": {
            "schema_version": (
                "synthetic_confirmatory_v3_previous_candidate_tag_binding_v1"
            ),
            "PREVIOUS_CANDIDATE_TAG_PRESERVED": True,
            "tag": FAILED_CANDIDATE_TAG,
            "tag_commit": git["failed_candidate_tag_commit"],
            "tag_moved": False,
        },
        "previous_qualification_root_binding.json": previous_binding,
        "publisher_envelope_failure_binding.json": failure_binding,
        "publisher_envelope_root_cause.json": {
            "schema_version": (
                "synthetic_confirmatory_v3_publisher_envelope_root_cause_v1"
            ),
            "root_cause": ROOT_CAUSE,
            "raw_schema": "synthetic_confirmatory_v3_bootstrap_fixture_run_v1",
            "frozen_schema": "synthetic_confirmatory_v2_fixture_run_v1",
            "raw_seed_reference_field": "formal_v3_seed_reference_count",
            "frozen_seed_reference_field": "formal_v2_seed_reference_count",
        },
        "frozen_publisher_contract_inventory.json": {
            "schema_version": (
                "synthetic_confirmatory_v3_frozen_publisher_contract_inventory_v1"
            ),
            "FROZEN_PUBLISHER_CHANGE_COUNT": 0,
            "ARTIFACT_VERIFIER_CORE_CHANGE_COUNT": 0,
            "fixture_run_schema": "synthetic_confirmatory_v2_fixture_run_v1",
            "required_field_count": 8,
            "allowed_field_count": 8,
            "required_fields": list(PUBLISHER_FIELDS),
            "optional_fields": [],
            "extra_fields_allowed": False,
            "table_count": 7,
            "figure_count": 3,
            "root_file_count": 7,
            "publisher_sha256": protected[
                "src/phase_a_harness/synthetic_confirmatory_v2_publisher.py"
            ]["actual_sha256"],
            "artifact_verifier_sha256": protected[
                "src/phase_a_harness/synthetic_confirmatory_v2_artifact_verifier.py"
            ]["actual_sha256"],
        },
        "fixture_envelope_adapter_contract.json": {
            "schema_version": (
                "synthetic_confirmatory_v3_fixture_envelope_adapter_contract_v1"
            ),
            "FIXTURE_ENVELOPE_COMPATIBILITY_PASS": True,
            "input_schema": raw["schema_version"],
            "output_schema": adapted["schema_version"],
            "input_fields": sorted(raw),
            "output_fields": sorted(adapted),
            "added_fields": ["formal_v2_seed_reference_count"],
            "removed_fields": ["formal_v3_seed_reference_count"],
            "renamed_fields": {
                "formal_v3_seed_reference_count": (
                    "formal_v2_seed_reference_count"
                )
            },
            "adapter_provenance": input_validation["adapter_provenance"],
            "qualification_only": True,
            "formal_v3_result_adapter": False,
        },
        "fixture_envelope_scientific_equivalence.json": equivalence,
        "fixture_seed_reference_audit.json": seed_audit,
        "bootstrap_state_machine_binding.json": {
            "schema_version": (
                "synthetic_confirmatory_v3_bootstrap_state_machine_binding_r2"
            ),
            "BOOTSTRAP_STATE_MACHINE_CORE_CHANGE_COUNT": 0,
            "RUNTIME_LIFECYCLE_CORE_CHANGE_COUNT": 0,
            "ABSENT_STATE_PASS": qualification["ABSENT_STATE_PASS"],
            "BOOTSTRAP_ONLY_STATE_PASS": qualification[
                "BOOTSTRAP_ONLY_STATE_PASS"
            ],
            "RESUMABLE_STATE_PASS": qualification["RESUMABLE_STATE_PASS"],
            "INVALID_STATE_PASS": qualification["INVALID_STATE_PASS"],
            "state_machine_sha256": protected[
                "src/phase_a_harness/formal_runtime_state_machine.py"
            ]["actual_sha256"],
            "runtime_io_sha256": protected[
                "src/phase_a_harness/runtime_lifecycle_io.py"
            ]["actual_sha256"],
            "runtime_fixture_sha256": protected[
                "src/phase_a_harness/runtime_lifecycle_fixture.py"
            ]["actual_sha256"],
        },
        "command_log_prelock_interruption_report.json": {
            "schema_version": (
                "synthetic_confirmatory_v3_command_log_interruption_r2"
            ),
            "COMMAND_LOG_PRELOCK_INTERRUPTION_PASS": qualification[
                "COMMAND_LOG_PRELOCK_INTERRUPTION_PASS"
            ],
            "BOOTSTRAP_ONLY_RECOVERY_PASS": qualification[
                "BOOTSTRAP_ONLY_RECOVERY_PASS"
            ],
            "command_log_change_after_resume": qualification[
                "command_log_change_after_resume"
            ],
        },
        "lock_atomic_interruption_report.json": {
            "schema_version": (
                "synthetic_confirmatory_v3_lock_atomic_interruption_r2"
            ),
            "LOCK_ATOMIC_INTERRUPTION_PASS": qualification[
                "LOCK_ATOMIC_INTERRUPTION_PASS"
            ],
            "PARTIAL_LOCK_ACCEPTED_COUNT": qualification[
                "PARTIAL_LOCK_ACCEPTED_COUNT"
            ],
            "observation": qualification["interruption_observation"],
        },
        "invalid_state_rejection_report.json": qualification[
            "invalid_state_rejection"
        ],
        "fresh_fixture_report.json": {
            **qualification["fresh"],
            "FRESH_FIXTURE_EXECUTION_PASS": qualification[
                "FRESH_FIXTURE_EXECUTION_PASS"
            ],
        },
        "resume_fixture_report.json": {
            **qualification["resume"],
            "RESUME_FIXTURE_EXECUTION_PASS": qualification[
                "RESUME_FIXTURE_EXECUTION_PASS"
            ],
            "VALID_SNAPSHOT_REEXECUTION_COUNT": 0,
            "VALID_TRIAL_REEXECUTION_COUNT": 0,
            "SNAPSHOT_CHECKSUM_CHANGE_AFTER_RESUME": 0,
            "TRIAL_CHECKSUM_CHANGE_AFTER_RESUME": 0,
        },
        "primary_independent_difference.json": {
            **qualification["primary_independent_difference"],
            "PRIMARY_INDEPENDENT_DIFFERENCE_COUNT": 0,
        },
        "publisher_input_validation.json": input_validation,
        "publisher_inventory.json": publisher_inventory,
        "artifact_verification.json": artifact_verification,
        "git_gate_report.json": git_gate_report,
        "scientific_core_binding.json": {
            "schema_version": (
                "synthetic_confirmatory_v3_scientific_core_binding_r2"
            ),
            "SCIENTIFIC_CORE_FILE_CHANGE_COUNT": 0,
            "PRIMARY_ANALYSIS_CORE_CHANGE_COUNT": 0,
            "INDEPENDENT_VERIFIER_CORE_CHANGE_COUNT": 0,
            "protected_files": protected,
        },
        "h1_h6_semantics_binding.json": {
            "schema_version": (
                "synthetic_confirmatory_v3_h1_h6_semantics_binding_r2"
            ),
            "H1_H6_SEMANTICS_CHANGE_COUNT": 0,
            "gate_contract_sha256": PROTECTED_SHA256[
                "protocols/synthetic_confirmatory_gate_contract_v3.json"
            ],
        },
        "frozen_model_binding.json": {
            "schema_version": "synthetic_confirmatory_v3_frozen_model_binding_r2",
            "FROZEN_MODEL_CHANGE_COUNT": 0,
            "sha256": PROTECTED_SHA256[
                "frozen_assets/confirmatory_development_trained_models_v1.json"
            ],
        },
        "backend_binding.json": {
            "schema_version": "synthetic_confirmatory_v3_backend_binding_r2",
            "BACKEND_BINDING_CHANGE_COUNT": 0,
            "bindings": manifest["backend_bindings"],
            "pcl_cli_sha256": PROTECTED_SHA256["bin/pcl_point_to_plane_cli"],
            "native_trial_count": 0,
        },
        "v3_seed_binding.json": {
            "schema_version": "synthetic_confirmatory_v3_seed_binding_r2",
            "V3_SEED_VALUE_CHANGE_COUNT": 0,
            "V3_SEED_ACCESS_COUNT": 0,
            "V3_RNG_INSTANTIATION_COUNT": 0,
            "V3_SNAPSHOT_CONSTRUCTION_COUNT": 0,
            "V3_BACKEND_EXECUTION_COUNT": 0,
            "V3_TRIAL_RESULT_COUNT": 0,
            "namespace": manifest["seed_namespace"],
            "geometry_seeds": manifest["geometry_seeds"],
            "measurement_seeds": manifest["measurement_seeds"],
            "bootstrap_seed": manifest["bootstrap_seed"],
        },
        "protocol_byte_binding.json": {
            "PROTOCOL_BYTE_CHANGE_COUNT": 0,
            "path": "protocols/synthetic_confirmatory_protocol_v3.json",
            "sha256": PROTECTED_SHA256[
                "protocols/synthetic_confirmatory_protocol_v3.json"
            ],
        },
        "gate_contract_byte_binding.json": {
            "GATE_CONTRACT_BYTE_CHANGE_COUNT": 0,
            "path": "protocols/synthetic_confirmatory_gate_contract_v3.json",
            "sha256": PROTECTED_SHA256[
                "protocols/synthetic_confirmatory_gate_contract_v3.json"
            ],
        },
        "plan_byte_binding.json": {
            "PLAN_BYTE_CHANGE_COUNT": 0,
            "snapshot_plan_sha256": PROTECTED_SHA256[
                "protocols/synthetic_confirmatory_planned_snapshots_v3.csv"
            ],
            "trial_plan_sha256": PROTECTED_SHA256[
                "protocols/synthetic_confirmatory_planned_trials_v3.csv"
            ],
        },
        "seed_schedule_byte_binding.json": {
            "SEED_SCHEDULE_BYTE_CHANGE_COUNT": 0,
            "sha256": PROTECTED_SHA256[
                "frozen_assets/synthetic_confirmatory_v3_seed_schedule.json"
            ],
        },
        "synthetic_confirmatory_v3_publisher_envelope_repair_scientific_diff.json": (
            scientific_diff
        ),
        "formal_manifest_binding.json": {
            "schema_version": "synthetic_confirmatory_v3_r2_manifest_binding_v1",
            "FORMAL_MANIFEST_BINDING_PASS": True,
            "path": MANIFEST_RELATIVE.as_posix(),
            "sha256": _sha256(manifest_path),
            "payload_sha256": manifest["manifest_payload_sha256"],
            "profile_path": PROFILE_RELATIVE.as_posix(),
            "profile_sha256": _sha256(profile_path),
            "profile_payload_sha256": profile[
                "execution_profile_payload_sha256"
            ],
        },
        "formal_plan_audit.json": {
            **dry["plan_audit"],
            "V3_FORMAL_PLAN_PASS": dry["plan_audit"]["V3_PLAN_AUDIT_PASS"],
        },
        "formal_dry_run_report.json": dry,
        "test_report.json": tests,
        "implementation_manifest.json": implementation_manifest,
        "formal_execution_profile.json": profile,
        "formal_run_commands.sh": (
            "#!/usr/bin/env bash\n"
            "# Frozen commands only. No command in this file was executed by publication.\n"
            + "\n".join(str(value) for value in profile["commands"].values())
            + "\n"
        ),
        "final_binding_audit.json": final_binding,
        "final_decision.json": decision,
        "run_manifest.json": run_manifest,
        "pre_run_report.md": (
            "# Synthetic Confirmatory v3 Bootstrap Repair r2\n\n"
            "Seed-free fixture requalification, frozen-publisher compatibility, "
            "and formal 595/1190 dry-run passed.\n\n"
            "CONFIRMATORY_V3_RUN_AUTHORIZED = true\n\n"
            "SYNTHETIC_CONFIRMATORY_V3_EXECUTED = false\n"
        ),
    }
    if set(payload) != set(PAYLOAD_FILES):
        raise AssertionError(
            "payload inventory differs; "
            f"missing={sorted(set(PAYLOAD_FILES) - set(payload))}, "
            f"extra={sorted(set(payload) - set(PAYLOAD_FILES))}"
        )
    verification = _write_package(
        destination, payload, verify_bootstrap_repair_r2_prerun_artifact
    )
    previous_after = _tree_binding(FAILED_QUALIFICATION_ROOT)
    if previous_after != previous_before:
        raise RuntimeError("publication modified the previous qualification root")
    if FORMAL_RUNTIME_ROOT.exists() or FORMAL_RUNTIME_ROOT.is_symlink():
        raise RuntimeError("publication created the formal runtime root")
    status = _git(repository, "status", "--porcelain=v1", "--untracked-files=all")
    changed_after = {
        line[3:] for line in status.splitlines() if len(line) >= 4
    }
    if not changed_after or not all(
        path.startswith(DESTINATION_RELATIVE.as_posix())
        for path in changed_after
    ):
        raise RuntimeError(
            f"publication changed an unexpected path: {sorted(changed_after)}"
        )
    return {
        "PRE_RUN_ARTIFACT_VERIFICATION_PASS": True,
        "artifact_path": str(destination),
        "artifact_file_count": verification["actual_file_count"],
        "artifact_sha256sums_sha256": _sha256(destination / "SHA256SUMS"),
        "candidate_commit": candidate_commit,
        "candidate_tag": candidate_tag,
        "verification": verification,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-candidate-commit", required=True)
    parser.add_argument("--expected-candidate-tag", required=True)
    parser.add_argument(
        "--qualification-report",
        type=Path,
        default=DEFAULT_QUALIFICATION_REPORT,
    )
    parser.add_argument("--test-report", type=Path, default=DEFAULT_TEST_REPORT)
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[1]
    report = build_artifact(
        repository=repository,
        candidate_commit=args.expected_candidate_commit,
        candidate_tag=args.expected_candidate_tag,
        qualification_report_path=args.qualification_report,
        test_report_path=args.test_report,
    )
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
