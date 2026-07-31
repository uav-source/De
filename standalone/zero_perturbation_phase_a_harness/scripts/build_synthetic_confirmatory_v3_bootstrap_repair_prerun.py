#!/usr/bin/env python3
"""Build the compact v3 bootstrap-repair pre-run evidence package.

This is a publication-only command.  It consumes the completed, seed-free
qualification report plus dry-run and test evidence.  It never imports a
snapshot builder, initializes an RNG, executes a backend, or creates the
formal Synthetic Confirmatory runtime root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


FROZEN_MAMBA_ROOT_PREFIX = "/home/lj/.local/share/degen-lio-micromamba"
SOURCE_REPOSITORY = Path("/home/lj/Degen-LIO")
FORMAL_RUNTIME_ROOT = Path(
    "/home/lj/zero_perturbation_runtime/confirmatory/synthetic_confirmatory_v3"
)
QUALIFICATION_ROOT = Path(
    "/home/lj/zero_perturbation_runtime/qualification/v3_bootstrap_state_machine_v1"
)
OLD_COMMIT = "38d3dcddd818eb9ae243f73837d863f52bd1e233"
OLD_BRANCH = "feature/zero-perturbation-synthetic-confirmatory-v3-prerun"
OLD_TAG = "archive/zero-perturbation-synthetic-confirmatory-v3-pre-run-pass"
OLD_BUNDLE = Path("/tmp/zero-perturbation-synthetic-confirmatory-v3-pre-run.bundle")
OLD_BUNDLE_SHA256 = (
    "c78dcc8b9177256b1ed11dfe4e9dcfd24a1f586035e211e3514ba63d7ba246f7"
)
FAILURE_TAG = (
    "archive/zero-perturbation-synthetic-confirmatory-v3-bootstrap-contract-fail"
)
FAILURE_BUNDLE = Path(
    "/tmp/zero-perturbation-synthetic-confirmatory-v3-bootstrap-contract-fail.bundle"
)
FAILURE_BUNDLE_SHA256 = (
    "754c0492ea3feceeb8547470b78cd3162ad957fa88552c27434950686782f363"
)
REPAIR_BRANCH = "fix/zero-perturbation-v3-formal-bootstrap-state-machine"
FINAL_TAG = (
    "archive/zero-perturbation-synthetic-confirmatory-v3-"
    "bootstrap-repair-pre-run-pass"
)
FORMAL_MANIFEST_RELATIVE = Path(
    "frozen_assets/synthetic_confirmatory_formal_manifest_v3_bootstrap_repair.json"
)
EXECUTION_PROFILE_RELATIVE = Path(
    "frozen_assets/synthetic_confirmatory_v3_execution_profile_bootstrap_repair.json"
)
INVALIDATION_RELATIVE = Path(
    "artifacts/synthetic_confirmatory_v3_bootstrap_contract_invalidation"
)
DESTINATION_RELATIVE = Path(
    "artifacts/synthetic_confirmatory_v3_bootstrap_repair_prerun"
)
QUALIFICATION_REPORT_RELATIVE = Path(
    "working_inventory/bootstrap_repair_qualification.json"
)
DEFAULT_DRY_RUN_REPORT = QUALIFICATION_ROOT / "working_inventory/v3_dry_run_report.json"
DEFAULT_TEST_REPORT = QUALIFICATION_ROOT / "test_logs/combined_test_report.json"

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
}

SCIENTIFIC_ZERO_FIELDS = (
    "scene_difference_count",
    "condition_difference_count",
    "planned_snapshot_count_difference",
    "planned_trial_count_difference",
    "seed_namespace_difference_count",
    "seed_value_difference_count",
    "seed_schedule_payload_difference_count",
    "snapshot_scientific_schema_difference_count",
    "trial_scientific_field_difference_count",
    "backend_algorithm_difference_count",
    "backend_parameter_difference_count",
    "lineage_semantics_difference_count",
    "phase_a_closure_difference_count",
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

REQUIRED_GIT_CHECKPOINTS = (
    "PRE_BOOTSTRAP_GIT_GATE",
    "POST_COMMAND_LOG_GIT_GATE",
    "POST_LOCK_GIT_GATE",
    "MID_SNAPSHOT_GIT_GATE",
    "MID_TRIAL_GIT_GATE",
    "RESUME_GIT_GATE",
    "POST_ANALYSIS_GIT_GATE",
    "POST_PUBLISHER_GIT_GATE",
    "FINAL_GIT_GATE",
)


def _unique_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_object(path: str | Path) -> dict[str, Any]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise ValueError(f"required regular JSON file is absent or linked: {candidate}")
    value = json.loads(
        candidate.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if type(value) is not dict:
        raise ValueError(f"JSON root must be an object: {candidate}")
    return value


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=repository, text=True, stderr=subprocess.STDOUT
    ).strip()


def _git_bytes(repository: Path, revision: str, relative: str) -> bytes:
    return subprocess.check_output(
        ["git", "show", f"{revision}:{relative}"], cwd=repository
    )


def _assert_environment(repository: Path) -> None:
    if os.environ.get("PYTHONNOUSERSITE") != "1":
        raise PermissionError("publication requires PYTHONNOUSERSITE=1")
    if os.environ.get("MAMBA_ROOT_PREFIX") != FROZEN_MAMBA_ROOT_PREFIX:
        raise PermissionError("publication requires the frozen MAMBA_ROOT_PREFIX")
    source = SOURCE_REPOSITORY.resolve()
    if repository == source or source in repository.parents:
        raise PermissionError("publication must run in the standalone harness")
    for entry in [
        *sys.path,
        *(item for item in os.environ.get("PYTHONPATH", "").split(os.pathsep) if item),
    ]:
        candidate = (Path.cwd() if not entry else Path(entry)).resolve()
        if candidate == source or source in candidate.parents or candidate in source.parents:
            raise PermissionError("source Degen-LIO appears on the Python search path")
    if FORMAL_RUNTIME_ROOT.exists() or FORMAL_RUNTIME_ROOT.is_symlink():
        raise PermissionError("formal v3 runtime root exists during pre-run publication")


def _assert_under_qualification(path: str | Path) -> Path:
    candidate = Path(path).resolve()
    if QUALIFICATION_ROOT.resolve() not in candidate.parents:
        raise ValueError(f"evidence is outside the frozen qualification root: {candidate}")
    cursor = candidate
    while cursor != QUALIFICATION_ROOT.parent:
        if cursor.is_symlink():
            raise ValueError(f"qualification evidence has a symlink component: {cursor}")
        cursor = cursor.parent
    if not candidate.is_file() or candidate.is_symlink():
        raise ValueError(f"qualification evidence is absent or linked: {candidate}")
    return candidate


def _verify_bundle(repository: Path, path: Path, expected_sha256: str) -> bool:
    if path.is_symlink() or not path.is_file() or _sha256(path) != expected_sha256:
        return False
    completed = subprocess.run(
        ["git", "bundle", "verify", str(path)],
        cwd=repository,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed.returncode == 0


def _verify_invalidation_archive(repository: Path) -> dict[str, Any]:
    root = repository / INVALIDATION_RELATIVE
    expected = {
        "bootstrap_failure_report.md",
        "failure_code_binding.json",
        "old_prerun_binding.json",
        "v3_seed_status.json",
        "formal_contract_conflict.json",
        "final_decision.json",
        "run_manifest.json",
        "MANIFEST.csv",
        "SHA256SUMS",
    }
    actual = {
        path.name
        for path in root.iterdir()
        if path.is_file() and not path.is_symlink()
    }
    unsafe = [path.name for path in root.iterdir() if path.is_symlink() or not path.is_file()]
    sums: dict[str, str] = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if len(line) < 67 or line[64:66] != "  ":
            raise ValueError("invalidation SHA256SUMS contains a malformed row")
        digest, relative = line[:64], line[66:]
        if relative in sums or relative not in expected - {"SHA256SUMS"}:
            raise ValueError("invalidation SHA256SUMS contains an unsafe path")
        sums[relative] = digest
    checksum_pass = bool(
        set(sums) == expected - {"SHA256SUMS"}
        and all(_sha256(root / name) == digest for name, digest in sums.items())
    )
    decision = _strict_object(root / "final_decision.json")
    passed = bool(
        actual == expected
        and not unsafe
        and checksum_pass
        and decision.get("V3_OLD_PRERUN_INVALIDATION_ARCHIVE_PASS") is True
        and decision.get("OLD_V3_PRERUN_FREEZE_VALID") is False
        and decision.get("OLD_V3_PRERUN_TAG_PRESERVED") is True
        and decision.get("OLD_V3_SCIENTIFIC_PROTOCOL_INVALIDATED") is False
    )
    if not passed:
        raise PermissionError("old v3 pre-run invalidation archive did not verify")
    return {
        "V3_OLD_PRERUN_INVALIDATION_ARCHIVE_PASS": True,
        "archive_file_count": len(actual),
        "archive_path": INVALIDATION_RELATIVE.as_posix(),
        "archive_sha256sums_sha256": _sha256(root / "SHA256SUMS"),
        "decision": decision,
        "old_prerun_binding": _strict_object(root / "old_prerun_binding.json"),
    }


def _candidate_git_binding(
    repository: Path, candidate_commit: str, candidate_tag: str
) -> dict[str, Any]:
    head = _git(repository, "rev-parse", "HEAD")
    branch = _git(repository, "branch", "--show-current")
    status = _git(repository, "status", "--porcelain=v1", "--untracked-files=all")
    candidate_tag_commit = _git(repository, "rev-parse", f"{candidate_tag}^{{commit}}")
    old_tag_commit = _git(repository, "rev-parse", f"{OLD_TAG}^{{commit}}")
    failure_tag_commit = _git(repository, "rev-parse", f"{FAILURE_TAG}^{{commit}}")
    old_bundle_pass = _verify_bundle(repository, OLD_BUNDLE, OLD_BUNDLE_SHA256)
    failure_bundle_pass = _verify_bundle(
        repository, FAILURE_BUNDLE, FAILURE_BUNDLE_SHA256
    )
    passed = bool(
        head == candidate_commit
        and branch == REPAIR_BRANCH
        and not status
        and candidate_tag_commit == candidate_commit
        and old_tag_commit == OLD_COMMIT
        and failure_tag_commit == OLD_COMMIT
        and old_bundle_pass
        and failure_bundle_pass
    )
    if not passed:
        raise PermissionError("candidate Git/archive identity is not fully bound")
    return {
        "ALL_CANDIDATE_GIT_BINDINGS_PASS": True,
        "branch": branch,
        "candidate_commit": candidate_commit,
        "candidate_tag": candidate_tag,
        "candidate_tag_commit": candidate_tag_commit,
        "candidate_worktree_clean_before_publication": True,
        "failure_bundle_sha256": FAILURE_BUNDLE_SHA256,
        "failure_bundle_verification_pass": failure_bundle_pass,
        "failure_tag": FAILURE_TAG,
        "failure_tag_commit": failure_tag_commit,
        "head_commit": head,
        "old_bundle_sha256": OLD_BUNDLE_SHA256,
        "old_bundle_verification_pass": old_bundle_pass,
        "old_tag": OLD_TAG,
        "old_tag_commit": old_tag_commit,
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_candidate_git_binding_v1",
    }


def _pick(source: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in source:
            return source[name]
    raise ValueError(f"required evidence field is absent: {names}")


def _normalize_dry_run(raw: Mapping[str, Any], manifest_sha256: str) -> dict[str, Any]:
    plan = raw.get("plan_audit")
    if type(plan) is not dict:
        plan = raw
    conditions_raw = _pick(plan, "condition_snapshot_counts", "condition_counts")
    backends_raw = _pick(plan, "backend_trial_counts")
    if type(conditions_raw) is not dict or type(backends_raw) is not dict:
        raise ValueError("dry-run condition/backend counts are not objects")
    conditions = {
        "FULL_NOISE": conditions_raw.get("FULL_NOISE", 0),
        "IDEAL_MATCHED": conditions_raw.get("IDEAL_MATCHED", 0),
        "INDEPENDENT_NOISE_FREE": conditions_raw.get("INDEPENDENT_NOISE_FREE", 0),
    }
    backends = {
        "Open3D": backends_raw.get("Open3D", backends_raw.get("open3d_point_to_plane", 0)),
        "PCL": backends_raw.get("PCL", backends_raw.get("pcl_point_to_plane", 0)),
        "Native": backends_raw.get("Native", plan.get("native_trial_count", 0)),
    }
    values = {
        "planned_snapshot_count": _pick(plan, "planned_snapshot_count"),
        "unique_snapshot_count": _pick(
            plan, "unique_snapshot_count", "planned_snapshot_unique_count"
        ),
        "planned_trial_count": _pick(plan, "planned_trial_count"),
        "unique_trial_count": _pick(
            plan, "unique_trial_count", "planned_trial_unique_count"
        ),
        "duplicate_snapshot_count": _pick(plan, "duplicate_snapshot_count"),
        "duplicate_trial_count": _pick(plan, "duplicate_trial_count"),
        "pairing_violation_count": _pick(plan, "pairing_violation_count"),
        "independent_pseudoreplication_count": _pick(
            plan,
            "independent_pseudoreplication_count",
            "independent_pseudoreplication_plan_count",
        ),
    }
    counters = {
        "V3_SEED_ACCESS_COUNT": _pick(
            raw, "V3_SEED_ACCESS_COUNT", "FORMAL_SEED_ACCESS_COUNT"
        ),
        "V3_RNG_INSTANTIATION_COUNT": _pick(
            raw, "V3_RNG_INSTANTIATION_COUNT", "FORMAL_RNG_INSTANTIATION_COUNT"
        ),
        "V3_SNAPSHOT_CONSTRUCTION_COUNT": _pick(
            raw, "V3_SNAPSHOT_CONSTRUCTION_COUNT", "FORMAL_SNAPSHOT_CONSTRUCTION_COUNT"
        ),
        "V3_BACKEND_EXECUTION_COUNT": _pick(
            raw, "V3_BACKEND_EXECUTION_COUNT", "FORMAL_BACKEND_EXECUTION_COUNT"
        ),
        "V3_TRIAL_RESULT_COUNT": _pick(
            raw, "V3_TRIAL_RESULT_COUNT", "FORMAL_TRIAL_RESULT_COUNT"
        ),
        "V3_STARTED_EVENT_COUNT": _pick(
            raw, "V3_STARTED_EVENT_COUNT", "FORMAL_ATTEMPT_EVENT_COUNT"
        ),
    }
    report_manifest_sha = raw.get("formal_manifest_sha256", raw.get("manifest_sha256"))
    root_absent = bool(
        raw.get("V3_FORMAL_RUNTIME_ROOT_NOT_CREATED") is True
        and raw.get("formal_root_created", False) is False
        and not FORMAL_RUNTIME_ROOT.exists()
    )
    plan_pass = bool(
        values
        == {
            "planned_snapshot_count": 595,
            "unique_snapshot_count": 595,
            "planned_trial_count": 1190,
            "unique_trial_count": 1190,
            "duplicate_snapshot_count": 0,
            "duplicate_trial_count": 0,
            "pairing_violation_count": 0,
            "independent_pseudoreplication_count": 0,
        }
        and conditions
        == {"FULL_NOISE": 525, "IDEAL_MATCHED": 35, "INDEPENDENT_NOISE_FREE": 35}
        and backends == {"Open3D": 595, "PCL": 595, "Native": 0}
    )
    passed = bool(
        raw.get("V3_DRY_RUN_PASS", raw.get("SYNTHETIC_CONFIRMATORY_V3_DRY_RUN_PASS"))
        is True
        and plan_pass
        and all(value == 0 for value in counters.values())
        and root_absent
        and report_manifest_sha == manifest_sha256
    )
    if not passed:
        raise PermissionError("formal v3 dry-run evidence did not pass exact validation")
    return {
        "V3_DRY_RUN_PASS": True,
        "V3_FORMAL_RUNTIME_ROOT_NOT_CREATED": True,
        "condition_counts": conditions,
        "backend_trial_counts": backends,
        "formal_manifest_sha256": report_manifest_sha,
        "formal_runtime_root": str(FORMAL_RUNTIME_ROOT),
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_dry_run_v1",
        **values,
        **counters,
    }


def _normalize_test_report(raw: Mapping[str, Any], candidate_commit: str) -> tuple[dict[str, Any], list[str]]:
    aliases = {
        "bootstrap_state_machine": ("bootstrap_state_machine", "bootstrap_state_machine_specialized"),
        "runtime_lifecycle_specialized": ("runtime_lifecycle_specialized", "runtime_lifecycle"),
        "v3_specialized": ("v3_specialized",),
        "v2_scientific_chain_regression": (
            "v2_scientific_chain_regression",
            "v2_scientific_chain",
            "v2_specialized",
        ),
        "full_harness": ("full_harness",),
        "pcl_fixture": ("pcl_fixture", "pcl_backend_v3"),
    }
    source = raw.get("suites", raw)
    if type(source) is not dict:
        raise ValueError("test evidence lacks a suite object")
    suites: dict[str, Any] = {}
    invalid_cases: list[str] = []
    for canonical, candidates in aliases.items():
        value = next((source[name] for name in candidates if name in source), None)
        if type(value) is not dict:
            raise ValueError(f"test evidence lacks suite: {canonical}")
        failures = value.get("failure_count", value.get("failures"))
        errors = value.get("error_count", value.get("errors"))
        skips = value.get("unexpected_skip_count", value.get("skipped"))
        junit_path = _assert_under_qualification(value.get("junit_path"))
        junit_sha = _sha256(junit_path)
        if value.get("junit_sha256") != junit_sha:
            raise ValueError(f"JUnit checksum differs for {canonical}")
        normalized = {
            "error_count": errors,
            "failure_count": failures,
            "junit_path": str(junit_path),
            "junit_sha256": junit_sha,
            "pass": value.get("pass") is True,
            "passed_count": value.get("passed_count", value.get("passed")),
            "test_count": value.get("test_count", value.get("tests")),
            "unexpected_skip_count": skips,
        }
        if not (
            normalized["pass"]
            and failures == 0
            and errors == 0
            and skips == 0
            and isinstance(normalized["test_count"], int)
            and normalized["test_count"] > 0
        ):
            raise PermissionError(f"test suite failed or was incomplete: {canonical}")
        suites[canonical] = normalized
        if canonical == "bootstrap_state_machine":
            xml = ET.parse(junit_path).getroot()
            for case in xml.iter("testcase"):
                name = str(case.attrib.get("name", ""))
                if "test_exact_twenty_invalid_runtime_states_fail_closed" in name:
                    if any(case.find(kind) is not None for kind in ("failure", "error", "skipped")):
                        raise PermissionError("an INVALID-state test did not pass")
                    invalid_cases.append(name)
    if (
        raw.get("TEST_SUITE_PASS", raw.get("V3_TEST_SUITE_PASS", raw.get("pass")))
        is not True
        or raw.get("source_degen_lio_pytest_executed", False) is not False
        or raw.get("candidate_commit", candidate_commit) != candidate_commit
        or len(invalid_cases) != 20
        or len(set(invalid_cases)) != 20
    ):
        raise PermissionError("combined test evidence did not pass exact validation")
    return (
        {
            "TEST_SUITE_PASS": True,
            "candidate_commit": candidate_commit,
            "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_test_report_v1",
            "source_degen_lio_pytest_executed": False,
            "suites": suites,
            "total_error_count": 0,
            "total_failure_count": 0,
            "total_unexpected_skip_count": 0,
        },
        sorted(invalid_cases),
    )


def _qualification_evidence(
    raw: Mapping[str, Any], invalid_cases: Sequence[str]
) -> dict[str, Any]:
    states = raw.get("states")
    fresh = raw.get("fresh")
    resume = raw.get("resume")
    difference = raw.get("primary_independent_difference")
    publication = raw.get("publication")
    artifact = raw.get("artifact_verification")
    gates = raw.get("git_gate_reports")
    if not all(
        type(value) is dict
        for value in (states, fresh, resume, difference, publication, artifact)
    ) or type(gates) is not list:
        raise ValueError("qualification report lacks complete lifecycle evidence")
    state_names = {
        "absent": "FORMAL_RUNTIME_ABSENT",
        "bootstrap_only": "FORMAL_RUNTIME_BOOTSTRAP_ONLY",
        "resumable": "FORMAL_RUNTIME_RESUMABLE",
    }
    state_pass = all(
        type(states.get(name)) is dict
        and states[name].get("state") == expected
        for name, expected in state_names.items()
    )
    checkpoints: dict[str, list[Mapping[str, Any]]] = {}
    for row in gates:
        if type(row) is not dict:
            raise ValueError("Git Gate evidence row is not an object")
        checkpoints.setdefault(str(row.get("checkpoint")), []).append(row)
    missing_checkpoints = [name for name in REQUIRED_GIT_CHECKPOINTS if name not in checkpoints]
    git_pass = bool(
        not missing_checkpoints
        and all(row.get("RUNTIME_GIT_GATE_PASS") is True for row in gates)
        and raw.get("git_gate_failure_count") == 0
    )
    fresh_pass = bool(
        fresh.get("fixture_snapshot_count") == 3
        and fresh.get("fixture_trial_count") == 6
        and fresh.get("backend_trial_counts")
        == {"open3d_point_to_plane": 3, "pcl_point_to_plane": 3}
        and fresh.get("native_execution_count") == 0
        and fresh.get("pairing_mismatch_count") == 0
        and fresh.get("outcome_mismatch_count") == 0
    )
    resume_pass = bool(
        resume.get("generated_snapshot_count") == 0
        and resume.get("backend_execution_count_this_invocation") == 0
        and resume.get("resume_skipped_valid_snapshot_count") == 3
        and resume.get("resume_skipped_valid_result_count") == 6
        and raw.get("valid_snapshot_reexecution_count") == 0
        and raw.get("valid_trial_reexecution_count") == 0
        and raw.get("snapshot_checksum_change_after_resume") == 0
        and raw.get("trial_checksum_change_after_resume") == 0
    )
    publisher_verification = publication.get("artifact_staging_verification", {})
    fixture_artifact_pass = bool(
        artifact.get("FIXTURE_ARTIFACT_VERIFICATION_PASS") is True
        and publisher_verification.get("FIXTURE_ARTIFACT_VERIFICATION_PASS") is True
    )
    difference_pass = bool(
        difference.get("exact_match_pass") is True
        and difference.get("leaf_difference_count") == 0
        and difference.get("section_difference_count") == 0
    )
    counters_pass = all(
        raw.get(name) == 0
        for name in (
            "source_repository_runtime_file_read_count",
            "source_repository_runtime_import_count",
            "v3_seed_access_count",
            "v3_rng_instantiation_count",
            "v3_snapshot_construction_count",
            "v3_backend_execution_count",
        )
    )
    passed = bool(
        raw.get("FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS") is True
        and state_pass
        and raw.get("command_log_prelock_interruption_pass") is True
        and raw.get("bootstrap_only_recovery_pass") is True
        and raw.get("lock_atomic_interruption_pass") is True
        and raw.get("partial_lock_accepted_count") == 0
        and len(invalid_cases) == 20
        and fresh_pass
        and resume_pass
        and difference_pass
        and fixture_artifact_pass
        and git_pass
        and counters_pass
        and raw.get("formal_runtime_root_created") is False
        and not FORMAL_RUNTIME_ROOT.exists()
    )
    if not passed:
        raise PermissionError("seed-free bootstrap qualification evidence did not pass")
    return {
        "states": states,
        "fresh": fresh,
        "resume": resume,
        "difference": difference,
        "publication": publication,
        "artifact": artifact,
        "gates": gates,
        "missing_git_checkpoints": missing_checkpoints,
    }


def _science_bindings(repository: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    baseline = _strict_object(
        repository / "artifacts/synthetic_confirmatory_v3_prerun/scientific_core_binding.json"
    )
    file_rows = baseline.get("file_bindings")
    if type(file_rows) is not list or not file_rows:
        raise ValueError("old v3 scientific binding lacks file inventory")
    verified: list[dict[str, Any]] = []
    for row in file_rows:
        if type(row) is not dict:
            raise ValueError("scientific file binding row is not an object")
        relative = str(row.get("path"))
        expected = str(row.get("expected_sha256"))
        actual = _sha256(repository / relative)
        old = hashlib.sha256(_git_bytes(repository, OLD_COMMIT, relative)).hexdigest()
        verified.append(
            {
                "actual_sha256": actual,
                "binding": row.get("binding"),
                "expected_sha256": expected,
                "old_commit_sha256": old,
                "path": relative,
                "unchanged": actual == expected == old,
            }
        )
    protected = []
    for relative, expected in PROTECTED_SHA256.items():
        actual = _sha256(repository / relative)
        old = hashlib.sha256(_git_bytes(repository, OLD_COMMIT, relative)).hexdigest()
        protected.append(
            {
                "actual_sha256": actual,
                "expected_sha256": expected,
                "old_commit_sha256": old,
                "path": relative,
                "unchanged": actual == expected == old,
            }
        )
    scientific_count = sum(not row["unchanged"] for row in verified)
    protocol_gate = {
        row["path"]: row["unchanged"] for row in protected
    }
    h1_h6_count = int(
        not protocol_gate["protocols/synthetic_confirmatory_gate_contract_v3.json"]
        or not all(
            row["unchanged"]
            for row in verified
            if row["binding"]
            in {
                "primary_h1_h6_core",
                "independent_h1_h6_core",
                "primary_scientific_core",
                "independent_scientific_core",
            }
        )
    )
    model_count = int(
        not protocol_gate[
            "frozen_assets/confirmatory_development_trained_models_v1.json"
        ]
    )
    backend_names = {
        "backend_parameter_contract",
        "backend_metrics",
        "open3d_adapter",
        "pcl_adapter",
        "pcl_cli",
    }
    backend_count = sum(
        not row["unchanged"] for row in verified if row["binding"] in backend_names
    )
    schedule_unchanged = protocol_gate[
        "frozen_assets/synthetic_confirmatory_v3_seed_schedule.json"
    ]
    seed_change = int(
        not schedule_unchanged
        or manifest.get("seed_schedule_sha256")
        != PROTECTED_SHA256[
            "frozen_assets/synthetic_confirmatory_v3_seed_schedule.json"
        ]
    )
    if scientific_count or h1_h6_count or model_count or backend_count or seed_change:
        raise PermissionError("a protected scientific, model, backend, or seed binding changed")
    scientific = {
        "SCIENTIFIC_CORE_FILE_CHANGE_COUNT": scientific_count,
        "binding_count": len(verified),
        "bindings": verified,
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_scientific_core_binding_v1",
    }
    h1_h6 = {
        "H1_H6_SEMANTICS_CHANGE_COUNT": h1_h6_count,
        "gate_contract_sha256": PROTECTED_SHA256[
            "protocols/synthetic_confirmatory_gate_contract_v3.json"
        ],
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_h1_h6_binding_v1",
    }
    model = {
        "FROZEN_MODEL_CHANGE_COUNT": model_count,
        "frozen_model_sha256": PROTECTED_SHA256[
            "frozen_assets/confirmatory_development_trained_models_v1.json"
        ],
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_model_binding_v1",
    }
    backend = {
        "BACKEND_BINDING_CHANGE_COUNT": backend_count,
        "native_authorized": False,
        "pcl_cli_sha256": PROTECTED_SHA256["bin/pcl_point_to_plane_cli"],
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_backend_binding_v1",
    }
    seed = {
        "V3_BACKEND_EXECUTION_COUNT": 0,
        "V3_RNG_INSTANTIATION_COUNT": 0,
        "V3_SEED_ACCESS_COUNT": 0,
        "V3_SEED_VALUE_CHANGE_COUNT": seed_change,
        "V3_SNAPSHOT_CONSTRUCTION_COUNT": 0,
        "seed_schedule_sha256": PROTECTED_SHA256[
            "frozen_assets/synthetic_confirmatory_v3_seed_schedule.json"
        ],
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_seed_binding_v1",
    }
    diff = {
        "SCIENTIFIC_DIFF_PASS": True,
        **{name: 0 for name in SCIENTIFIC_ZERO_FIELDS},
        "allowed_differences": {
            "bootstrap_state_machine_difference_count": 1,
            "runtime_lock_schema_difference_count": 1,
            "formal_command_binding_difference_count": 1,
            "implementation_binding_difference_count": 1,
            "manifest_binding_difference_count": 1,
            "pre_run_artifact_difference_count": 1,
            "expected_tag_difference_count": 1,
        },
        "protected_bindings": protected,
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_scientific_diff_v1",
    }
    scientific["synthetic_confirmatory_v3_bootstrap_repair_scientific_diff"] = diff
    return {
        "scientific": scientific,
        "h1_h6": h1_h6,
        "model": model,
        "backend": backend,
        "seed": seed,
        "diff": diff,
    }


def _formal_commands(profile: Mapping[str, Any]) -> str:
    commands = profile.get("commands")
    if type(commands) is not dict:
        raise ValueError("formal profile lacks the command map")
    required = {
        "step_01_preflight_fresh",
        "step_01_preflight_resume",
        "step_02_bootstrap_fresh",
        "step_02_bootstrap_resume",
        "step_03_runner_fresh",
        "step_03_runner_resume",
        "step_04_completeness",
        "step_05_primary",
        "step_06_independent",
        "step_07_difference",
        "step_08_publisher",
        "step_09_artifact_verifier",
        "step_10_final_sha",
    }
    if set(commands) != required or any(
        not isinstance(commands[name], str) or not commands[name]
        for name in required
    ):
        raise ValueError("formal profile command inventory is not exact")
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "# Frozen formal commands. This script was not executed during qualification.",
            "cd /home/lj/zero_perturbation_phase_a_harness_20260729_1407",
            "case \"${1:-fresh}\" in",
            "  fresh)",
            "    # STEP 1: formal preflight",
            f"    {commands['step_01_preflight_fresh']}",
            "    # STEP 2: bootstrap command record",
            f"    {commands['step_02_bootstrap_fresh']}",
            "    # STEP 3: formal fresh runner",
            f"    {commands['step_03_runner_fresh']}",
            "    ;;",
            "  resume)",
            "    # STEP 1: formal preflight",
            f"    {commands['step_01_preflight_resume']}",
            "    # STEP 2: authenticate bootstrap command record",
            f"    {commands['step_02_bootstrap_resume']}",
            "    # STEP 3: formal resume runner",
            f"    {commands['step_03_runner_resume']}",
            "    ;;",
            "  *) echo 'usage: formal_run_commands.sh [fresh|resume]' >&2; exit 2 ;;",
            "esac",
            "# STEP 4: inventory completeness check",
            str(commands["step_04_completeness"]),
            "# STEP 5: primary analysis",
            str(commands["step_05_primary"]),
            "# STEP 6: independent verification",
            str(commands["step_06_independent"]),
            "# STEP 7: difference audit",
            str(commands["step_07_difference"]),
            "# STEP 8: publisher",
            str(commands["step_08_publisher"]),
            "# STEP 9: artifact verifier",
            str(commands["step_09_artifact_verifier"]),
            "# STEP 10: final SHA",
            str(commands["step_10_final_sha"]),
            "",
        ]
    )


def _implementation_manifest(
    repository: Path, candidate_commit: str, candidate_tag: str
) -> dict[str, Any]:
    names = [
        line
        for line in _git(repository, "diff", "--name-only", f"{OLD_COMMIT}..{candidate_commit}").splitlines()
        if line
    ]
    files = {
        name: hashlib.sha256(_git_bytes(repository, candidate_commit, name)).hexdigest()
        for name in sorted(names)
        if subprocess.run(
            ["git", "cat-file", "-e", f"{candidate_commit}:{name}"],
            cwd=repository,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    }
    if not files:
        raise ValueError("candidate implementation diff is empty")
    return {
        "IMPLEMENTATION_BINDING_PASS": True,
        "baseline_commit": OLD_COMMIT,
        "candidate_branch": REPAIR_BRANCH,
        "candidate_commit": candidate_commit,
        "candidate_tag": candidate_tag,
        "file_count": len(files),
        "files": files,
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_implementation_manifest_v1",
    }


def _write_package(staging: Path, payload: Mapping[str, Any | str | bytes]) -> None:
    repository = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository / "src"))
    from phase_a_harness.runtime_lifecycle_io import atomic_create_bytes, canonical_json_bytes
    from phase_a_harness.synthetic_confirmatory_v3_bootstrap_repair_artifact_verifier import (
        PAYLOAD_FILES,
    )

    if set(payload) != set(PAYLOAD_FILES):
        raise ValueError("bootstrap-repair payload inventory differs from the 33-file contract")
    for name in PAYLOAD_FILES:
        value = payload[name]
        if isinstance(value, bytes):
            data = value
        elif isinstance(value, str):
            data = value.encode("utf-8")
        else:
            data = canonical_json_bytes(value)
        atomic_create_bytes(staging / name, data)
    rows = []
    for name in PAYLOAD_FILES:
        path = staging / name
        rows.append((name, path.stat().st_size, _sha256(path)))
    manifest = ["path,size_bytes,sha256\n"]
    manifest.extend(f"{name},{size},{digest}\n" for name, size, digest in rows)
    atomic_create_bytes(staging / "MANIFEST.csv", "".join(manifest).encode("utf-8"))
    checksum_names = sorted({*PAYLOAD_FILES, "MANIFEST.csv"})
    checksums = "".join(
        f"{_sha256(staging / name)}  {name}\n" for name in checksum_names
    )
    atomic_create_bytes(staging / "SHA256SUMS", checksums.encode("utf-8"))


def _report(decision: Mapping[str, Any], plan: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "# Synthetic Confirmatory v3 Bootstrap Repair — Pre-Run Qualification",
            "",
            "This package contains seed-free lifecycle qualification and dry-run evidence only.",
            "No formal v3 seed was consumed, no formal snapshot was constructed, and no formal backend trial was executed.",
            "",
            "- `FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS = true`",
            "- `SYNTHETIC_CONFIRMATORY_V3_BOOTSTRAP_REPAIR_PRE_RUN_QUALIFICATION_PASS = true`",
            "- `V3_SEED_SET_REUSE_AUTHORIZED = true`",
            "- `CONFIRMATORY_V3_RUN_AUTHORIZED = true`",
            "- `SYNTHETIC_CONFIRMATORY_V3_EXECUTED = false`",
            "- `SYNTHETIC_CONFIRMATORY_V3_COMPLETE = false`",
            "- `SYNTHETIC_CONFIRMATORY_V3_PASS = NOT_EVALUATED`",
            "",
            f"- Formal plan: `{plan['planned_snapshot_count']} snapshots / {plan['planned_trial_count']} trials`",
            f"- Formal runtime root: `{FORMAL_RUNTIME_ROOT}` (absent)",
            f"- Authorization state: `{decision['CONFIRMATORY_V3_RUN_AUTHORIZED']}`",
            "",
        ]
    )


def build_artifact(
    repository: Path,
    *,
    candidate_commit: str,
    candidate_tag: str,
    qualification_report_path: Path,
    dry_run_report_path: Path,
    test_report_path: Path,
    destination: Path,
) -> dict[str, Any]:
    _assert_environment(repository)
    if destination.resolve() != (repository / DESTINATION_RELATIVE).resolve():
        raise ValueError("publication destination is not the exact compact artifact path")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"refusing to overwrite compact artifact: {destination}")
    git = _candidate_git_binding(repository, candidate_commit, candidate_tag)
    invalidation = _verify_invalidation_archive(repository)
    qualification_path = _assert_under_qualification(qualification_report_path)
    dry_path = _assert_under_qualification(dry_run_report_path)
    tests_path = _assert_under_qualification(test_report_path)

    sys.path.insert(0, str(repository / "src"))
    from phase_a_harness.synthetic_confirmatory_v3_contract import load_v3_contract
    from phase_a_harness.runtime_lifecycle_io import atomic_publish_directory
    from phase_a_harness.synthetic_confirmatory_v3_bootstrap_repair_artifact_verifier import (
        verify_bootstrap_repair_prerun_artifact,
    )

    manifest_path = repository / FORMAL_MANIFEST_RELATIVE
    profile_path = repository / EXECUTION_PROFILE_RELATIVE
    manifest = load_v3_contract(manifest_path)
    profile = _strict_object(profile_path)
    manifest_sha = _sha256(manifest_path)
    profile_sha = _sha256(profile_path)
    if (
        manifest.get("run_id") != "synthetic-confirmatory-v3"
        or manifest.get("runtime_root") != str(FORMAL_RUNTIME_ROOT)
        or manifest.get("workers") != 2
        or manifest.get("expected_branch") != REPAIR_BRANCH
        or manifest.get("expected_release_tag") != FINAL_TAG
        or manifest.get("planned_snapshot_count") != 595
        or manifest.get("planned_trial_count") != 1190
        or manifest.get("bound_files", {}).get("execution_profile", {}).get("sha256")
        != profile_sha
        or profile.get("expected_branch") != REPAIR_BRANCH
        or profile.get("expected_release_tag") != FINAL_TAG
    ):
        raise PermissionError("formal manifest/profile identity is not the frozen repair contract")
    dry = _normalize_dry_run(_strict_object(dry_path), manifest_sha)
    tests, invalid_cases = _normalize_test_report(
        _strict_object(tests_path), candidate_commit
    )
    qualification_raw = _strict_object(qualification_path)
    qualification = _qualification_evidence(qualification_raw, invalid_cases)
    science = _science_bindings(repository, manifest)
    seed_status_source = _strict_object(
        repository / INVALIDATION_RELATIVE / "v3_seed_status.json"
    )
    seed_status = {
        **_copy(seed_status_source),
        "V3_BACKEND_EXECUTION_COUNT": 0,
        "V3_RNG_INSTANTIATED": False,
        "V3_RNG_INSTANTIATION_COUNT": 0,
        "V3_SEEDS_ACCESSED": False,
        "V3_SEED_ACCESS_COUNT": 0,
        "V3_SEED_SET_REUSE_AUTHORIZED": True,
        "V3_SEED_VALUE_CHANGE_COUNT": 0,
        "V3_SNAPSHOT_CONSTRUCTION_COUNT": 0,
        "V3_TRIAL_RESULT_COUNT": 0,
        "new_v4_namespace_created": False,
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_seed_status_v1",
    }
    formal_commands = _formal_commands(profile)
    bootstrap = manifest["formal_bootstrap_contract"]
    command_binding = qualification_raw["lock_transition"]["command_binding"]
    lock = qualification_raw["lock_transition"]["lock"]
    state_contract = {
        "FORMAL_BOOTSTRAP_STATE_MACHINE_IMPLEMENTED": True,
        "ABSENT_STATE_PASS": True,
        "BOOTSTRAP_ONLY_STATE_PASS": True,
        "RESUMABLE_STATE_PASS": True,
        "INVALID_STATE_PASS": True,
        "allowed_bootstrap_files": bootstrap["allowed_bootstrap_files"],
        "states": bootstrap["states"],
        "qualification_states": qualification["states"],
        "schema_version": "synthetic_confirmatory_v3_bootstrap_state_machine_contract_v1",
    }
    transitions = [
        ("FORMAL_RUNTIME_ABSENT", "bootstrap fresh", "FORMAL_RUNTIME_BOOTSTRAP_ONLY", "PASS"),
        ("FORMAL_RUNTIME_BOOTSTRAP_ONLY", "runner fresh / atomic lock", "FORMAL_RUNTIME_RESUMABLE", "PASS"),
        ("FORMAL_RUNTIME_RESUMABLE", "runner resume", "FORMAL_RUNTIME_RESUMABLE", "PASS"),
        ("FORMAL_RUNTIME_INVALID", "fail closed", "FORMAL_RUNTIME_INVALID", "PASS"),
    ]
    transition_csv = ["classification,allowed_action,resulting_state,result\n"]
    transition_csv.extend(
        f"{classification},{action},{resulting},{result}\n"
        for classification, action, resulting, result in transitions
    )
    command_contract = {
        "FORMAL_COMMAND_CONTRACT_PASS": True,
        "allowed_bootstrap_files": bootstrap["allowed_bootstrap_files"],
        "canonicalization": "UTF-8; normalized LF; exactly one trailing LF",
        "formal_command_log_path": bootstrap["command_log_path"],
        "formal_command_log_sha256": command_binding["command_log_sha256"],
        "formal_command_log_size_bytes": command_binding["command_log_size_bytes"],
        "profile_fresh_runner_command": profile["commands"]["step_03_runner_fresh"],
        "profile_resume_runner_command": profile["commands"]["step_03_runner_resume"],
        "schema_version": "synthetic_confirmatory_v3_formal_command_contract_v1",
    }
    lock_contract = {
        "IMMUTABLE_RUN_LOCK_CONTRACT_PASS": True,
        "atomic_method": "same-directory temporary; write; flush; fsync file; rename-no-replace; fsync parent; reread and verify",
        "creation_mode": lock["contract"]["creation_mode"],
        "lock_path": bootstrap["immutable_run_lock_path"],
        "payload_sha256": lock["payload_sha256"],
        "required_contract_fields": sorted(lock["contract"]),
        "schema_version": "synthetic_confirmatory_v3_immutable_run_lock_contract_v1",
    }
    prelock = {
        "COMMAND_LOG_PRELOCK_INTERRUPTION_PASS": True,
        "BOOTSTRAP_ONLY_RECOVERY_PASS": True,
        "command_log_change_after_resume": qualification_raw.get(
            "command_log_change_after_resume"
        ),
        "state_after_command_log": "FORMAL_RUNTIME_BOOTSTRAP_ONLY",
        "state_after_recovery": "FORMAL_RUNTIME_RESUMABLE",
        "schema_version": "synthetic_confirmatory_v3_command_log_prelock_interruption_v1",
    }
    lock_interruption = {
        "LOCK_ATOMIC_INTERRUPTION_PASS": True,
        "PARTIAL_LOCK_ACCEPTED_COUNT": 0,
        "interruption_observation": qualification_raw.get("interruption_observation"),
        "state_after_interruption": "FORMAL_RUNTIME_BOOTSTRAP_ONLY",
        "state_after_recovery": "FORMAL_RUNTIME_RESUMABLE",
        "schema_version": "synthetic_confirmatory_v3_lock_atomic_interruption_v1",
    }
    invalid = {
        "INVALID_RUNTIME_STATE_FALSE_ACCEPT_COUNT": 0,
        "INVALID_RUNTIME_STATE_REJECTION_COUNT": len(invalid_cases),
        "junit_test_cases": list(invalid_cases),
        "schema_version": "synthetic_confirmatory_v3_invalid_state_rejection_v1",
    }
    fresh = {
        "FRESH_FIXTURE_EXECUTION_PASS": True,
        **_copy(qualification["fresh"]),
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_fresh_fixture_v1",
    }
    resume = {
        "RESUME_FIXTURE_EXECUTION_PASS": True,
        "SNAPSHOT_CHECKSUM_CHANGE_AFTER_RESUME": 0,
        "TRIAL_CHECKSUM_CHANGE_AFTER_RESUME": 0,
        "VALID_SNAPSHOT_REEXECUTION_COUNT": 0,
        "VALID_TRIAL_REEXECUTION_COUNT": 0,
        **_copy(qualification["resume"]),
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_resume_fixture_v1",
    }
    git_gates = {
        "ALL_GIT_GATES_PASS": True,
        "gate_failure_count": 0,
        "gate_report_count": len(qualification["gates"]),
        "required_checkpoints": list(REQUIRED_GIT_CHECKPOINTS),
        "reports": _copy(qualification["gates"]),
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_git_gate_report_v1",
    }
    difference = {
        **_copy(qualification["difference"]),
        "PRIMARY_INDEPENDENT_DIFFERENCE_COUNT": 0,
    }
    inventory = profile["publisher_inventory"]
    publisher = {
        "PUBLISHER_INVENTORY_PASS": True,
        "figure_count": inventory["figure_count"],
        "publication": _copy(qualification["publication"]),
        "root_file_count": inventory["root_file_count"],
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_publisher_inventory_v1",
        "table_count": inventory["table_count"],
    }
    fixture_artifact = {
        "ARTIFACT_VERIFIER_PASS": True,
        "qualification_artifact_verification": _copy(qualification["artifact"]),
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_fixture_artifact_verification_v1",
    }
    manifest_binding = {
        "FORMAL_MANIFEST_BINDING_PASS": True,
        "manifest_path": FORMAL_MANIFEST_RELATIVE.as_posix(),
        "manifest_payload_sha256": manifest["manifest_payload_sha256"],
        "manifest_sha256": manifest_sha,
        "profile_path": EXECUTION_PROFILE_RELATIVE.as_posix(),
        "profile_sha256": profile_sha,
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_formal_manifest_binding_v1",
    }
    plan = {
        **_copy(dry),
        "V3_FORMAL_PLAN_PASS": True,
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_formal_plan_audit_v1",
    }
    implementation = _implementation_manifest(
        repository, candidate_commit, candidate_tag
    )
    final_binding = {
        "FINAL_GIT_BINDING_PASS": True,
        "allowed_final_diff_prefix": DESTINATION_RELATIVE.as_posix() + "/",
        "candidate_commit": candidate_commit,
        "candidate_tag": candidate_tag,
        "candidate_worktree_clean_before_publication": True,
        "final_commit_and_final_tag_require_post_import_read_only_audit": True,
        "required_final_tag": FINAL_TAG,
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_final_binding_audit_v1",
        "stage": "CANDIDATE_QUALIFIED_ARTIFACT_ONLY_FINAL_TRANSITION",
    }
    decision = {
        "ALL_GIT_GATES_PASS": True,
        "ARTIFACT_VERIFIER_PASS": True,
        "BOOTSTRAP_ONLY_RECOVERY_PASS": True,
        "COMMAND_LOG_PRELOCK_INTERRUPTION_PASS": True,
        "CONFIRMATORY_V3_RUN_AUTHORIZED": True,
        "FINAL_GIT_BINDING_PASS": True,
        "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": True,
        "FRESH_FIXTURE_EXECUTION_PASS": True,
        "INVALID_RUNTIME_STATE_FALSE_ACCEPT_COUNT": 0,
        "LOCK_ATOMIC_INTERRUPTION_PASS": True,
        "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED": False,
        "OLD_V3_PRERUN_TAG_PRESERVED": True,
        "PARTIAL_LOCK_ACCEPTED_COUNT": 0,
        "PUBLISHER_INVENTORY_PASS": True,
        "REAL_DATA_RUN_AUTHORIZED": False,
        "RESUME_FIXTURE_EXECUTION_PASS": True,
        "SYNTHETIC_CONFIRMATORY_V3_BOOTSTRAP_REPAIR_PRE_RUN_QUALIFICATION_PASS": True,
        "SYNTHETIC_CONFIRMATORY_V3_COMPLETE": False,
        "SYNTHETIC_CONFIRMATORY_V3_EXECUTED": False,
        "SYNTHETIC_CONFIRMATORY_V3_PASS": "NOT_EVALUATED",
        "SYNTHETIC_CONFIRMATORY_V3_PRE_RUN_QUALIFICATION_PASS": True,
        "TEST_SUITE_PASS": True,
        "V3_DRY_RUN_PASS": True,
        "V3_FORMAL_PLAN_PASS": True,
        "V3_OLD_PRERUN_INVALIDATION_ARCHIVE_PASS": True,
        "V3_SEED_SET_REUSE_AUTHORIZED": True,
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_prerun_decision_v1",
    }
    run_manifest = {
        "artifact_payload_file_count": 33,
        "candidate_commit": candidate_commit,
        "candidate_tag": candidate_tag,
        "formal_backend_execution_count": 0,
        "formal_manifest_path": FORMAL_MANIFEST_RELATIVE.as_posix(),
        "formal_manifest_sha256": manifest_sha,
        "formal_rng_instantiation_count": 0,
        "formal_run_id": "synthetic-confirmatory-v3",
        "formal_runtime_root": str(FORMAL_RUNTIME_ROOT),
        "formal_runtime_root_created": False,
        "formal_seed_access_count": 0,
        "formal_snapshot_construction_count": 0,
        "formal_trial_result_count": 0,
        "native_execution_count": 0,
        "planned_snapshot_count": 595,
        "planned_trial_count": 1190,
        "qualification_report_path": str(qualification_path),
        "qualification_report_sha256": _sha256(qualification_path),
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_prerun_run_manifest_v1",
        "test_report_path": str(tests_path),
        "test_report_sha256": _sha256(tests_path),
        "dry_run_report_path": str(dry_path),
        "dry_run_report_sha256": _sha256(dry_path),
    }
    root_cause = {
        **_copy(_strict_object(repository / INVALIDATION_RELATIVE / "failure_code_binding.json")),
        "formal_contract_conflict": _copy(
            _strict_object(
                repository / INVALIDATION_RELATIVE / "formal_contract_conflict.json"
            )
        ),
        "repair_qualification_pass": True,
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_root_cause_binding_v1",
    }
    old_tag = {
        "OLD_V3_PRERUN_TAG_PRESERVED": True,
        "failure_tag": FAILURE_TAG,
        "failure_tag_commit": git["failure_tag_commit"],
        "old_tag": OLD_TAG,
        "old_tag_commit": git["old_tag_commit"],
        "old_tag_moved": False,
        "schema_version": "synthetic_confirmatory_v3_old_tag_preservation_v1",
    }
    payload: dict[str, Any | str | bytes] = {
        "old_v3_prerun_invalidation_binding.json": invalidation,
        "old_v3_tag_preservation.json": old_tag,
        "v3_seed_status.json": seed_status,
        "bootstrap_root_cause_binding.json": root_cause,
        "bootstrap_state_machine_contract.json": state_contract,
        "runtime_state_transition_matrix.csv": "".join(transition_csv),
        "formal_command_contract.json": command_contract,
        "immutable_run_lock_contract.json": lock_contract,
        "command_log_prelock_interruption_report.json": prelock,
        "lock_atomic_interruption_report.json": lock_interruption,
        "invalid_state_rejection_report.json": invalid,
        "fresh_fixture_report.json": fresh,
        "resume_fixture_report.json": resume,
        "git_gate_report.json": git_gates,
        "primary_independent_difference.json": difference,
        "publisher_inventory.json": publisher,
        "artifact_verification.json": fixture_artifact,
        "scientific_core_binding.json": science["scientific"],
        "h1_h6_semantics_binding.json": science["h1_h6"],
        "frozen_model_binding.json": science["model"],
        "backend_binding.json": science["backend"],
        "v3_seed_binding.json": science["seed"],
        "formal_manifest_binding.json": manifest_binding,
        "formal_plan_audit.json": plan,
        "formal_dry_run_report.json": dry,
        "test_report.json": tests,
        "implementation_manifest.json": implementation,
        "formal_execution_profile.json": profile_path.read_bytes(),
        "formal_run_commands.sh": formal_commands,
        "final_binding_audit.json": final_binding,
        "final_decision.json": decision,
        "run_manifest.json": run_manifest,
        "pre_run_report.md": _report(decision, plan),
    }

    verification: dict[str, Any] = {}

    def populate(staging: Path) -> None:
        nonlocal verification
        _write_package(staging, payload)
        verification = verify_bootstrap_repair_prerun_artifact(staging)
        if verification.get("PRE_RUN_ARTIFACT_VERIFICATION_PASS") is not True:
            raise ValueError(
                "compact bootstrap-repair artifact failed independent verification"
            )

    atomic_publish_directory(destination, populate)
    read_only = verify_bootstrap_repair_prerun_artifact(destination)
    if read_only != verification:
        raise RuntimeError("published compact artifact differs from staging verification")
    if FORMAL_RUNTIME_ROOT.exists() or FORMAL_RUNTIME_ROOT.is_symlink():
        raise RuntimeError("pre-run publication created the formal runtime root")
    status = _git(repository, "status", "--porcelain=v1", "--untracked-files=all")
    allowed_prefix = f"?? {DESTINATION_RELATIVE.as_posix()}/"
    unexpected = [line for line in status.splitlines() if not line.startswith(allowed_prefix)]
    if unexpected:
        raise RuntimeError(f"publication changed paths outside compact artifact: {unexpected}")
    return {
        **read_only,
        "artifact_path": str(destination),
        "artifact_sha256sums_sha256": _sha256(destination / "SHA256SUMS"),
        "candidate_commit": candidate_commit,
        "candidate_tag": candidate_tag,
        "formal_runtime_root_absent": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-candidate-commit", required=True)
    parser.add_argument("--expected-candidate-tag", required=True)
    parser.add_argument(
        "--qualification-report",
        type=Path,
        default=QUALIFICATION_ROOT / QUALIFICATION_REPORT_RELATIVE,
    )
    parser.add_argument("--dry-run-report", type=Path, default=DEFAULT_DRY_RUN_REPORT)
    parser.add_argument("--test-report", type=Path, default=DEFAULT_TEST_REPORT)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[1]
    destination = args.destination or repository / DESTINATION_RELATIVE
    report = build_artifact(
        repository,
        candidate_commit=args.expected_candidate_commit,
        candidate_tag=args.expected_candidate_tag,
        qualification_report_path=args.qualification_report,
        dry_run_report_path=args.dry_run_report,
        test_report_path=args.test_report,
        destination=destination,
    )
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report.get("PRE_RUN_ARTIFACT_VERIFICATION_PASS") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
