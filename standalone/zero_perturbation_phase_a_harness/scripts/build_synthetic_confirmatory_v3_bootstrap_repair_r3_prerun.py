#!/usr/bin/env python3
"""Publish the compact, seed-free v3 JSON-native-repair pre-run package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


FROZEN_MAMBA_ROOT_PREFIX = "/home/lj/.local/share/degen-lio-micromamba"
SOURCE_REPOSITORY = Path("/home/lj/Degen-LIO")
SOURCE_BRANCH = "feature/zero-perturbation-phase-a-lock-v2-regression-repair"
SOURCE_COMMIT = "89f46dda68e9ff5c71f078f6d13fc9050d58f0f5"
FORMAL_RUNTIME_ROOT = Path(
    "/home/lj/zero_perturbation_runtime/confirmatory/synthetic_confirmatory_v3"
)
R2_QUALIFICATION_ROOT = Path(
    "/home/lj/zero_perturbation_runtime/qualification/"
    "v3_bootstrap_state_machine_requalification_v2"
)
QUALIFICATION_ROOT = Path(
    "/home/lj/zero_perturbation_runtime/qualification/"
    "v3_bootstrap_state_machine_requalification_v3"
)
R2_FAILURE_ARTIFACT_RELATIVE = Path(
    "artifacts/synthetic_confirmatory_v3_bootstrap_repair_r2_json_failure"
)
DESTINATION_RELATIVE = Path(
    "artifacts/synthetic_confirmatory_v3_bootstrap_repair_r3_prerun"
)
MANIFEST_RELATIVE = Path(
    "frozen_assets/synthetic_confirmatory_formal_manifest_v3_bootstrap_repair_r3.json"
)
PROFILE_RELATIVE = Path(
    "frozen_assets/"
    "synthetic_confirmatory_v3_execution_profile_bootstrap_repair_r3.json"
)
DEFAULT_QUALIFICATION_REPORT = (
    QUALIFICATION_ROOT
    / "working_inventory/bootstrap_repair_requalification_v3.json"
)
DEFAULT_TEST_REPORT = QUALIFICATION_ROOT / "test_logs/combined_test_report.json"

REPAIR_BRANCH = "fix/zero-perturbation-v3-qualification-json-native-r3"
CANDIDATE_TAG = (
    "archive/zero-perturbation-synthetic-confirmatory-v3-"
    "qualification-json-native-r3-candidate"
)
FINAL_TAG = (
    "archive/zero-perturbation-synthetic-confirmatory-v3-"
    "bootstrap-repair-r3-pre-run-pass"
)
R2_CANDIDATE_COMMIT = "767e79fe4e518fbef290a43018c29581f028d6cd"
R2_CANDIDATE_TAG = (
    "archive/zero-perturbation-synthetic-confirmatory-v3-"
    "publisher-envelope-repair-candidate"
)
R2_FAILURE_TAG = (
    "archive/zero-perturbation-synthetic-confirmatory-v3-"
    "bootstrap-repair-r2-json-native-fail"
)
R2_FAILURE_BUNDLE = Path(
    "/tmp/zero-perturbation-synthetic-confirmatory-v3-"
    "bootstrap-repair-r2-json-native-fail.bundle"
)
R2_FAILURE_BUNDLE_SHA256 = (
    "dac9210de93c182ab57c3a322ea89fd7f878fe2f90625395ae0150ceb8c3490c"
)
R2_ROOT_FILE_COUNT = 76
R2_ROOT_SIZE_BYTES = 705331
R2_ROOT_INVENTORY_SHA256 = (
    "dd9ba5ea28b3538584425f7246be23707ed5ec540f97d30c1049d7b227b900eb"
)
R2_FAILURE_ARTIFACT_INVENTORY_SHA256 = (
    "688ae4ad21960451dbb3182fc0e6175b34719e41d39d39516b08009b3a33a4a2"
)
ROOT_CAUSE = "QUALIFICATION_FINAL_AGGREGATE_NON_JSON_NATIVE_ENUM"

INVENTORY_RELATIVE = Path(
    "working_inventory/final_aggregate_non_native_type_inventory.csv"
)
CONVERSION_AUDIT_RELATIVE = Path(
    "working_inventory/final_aggregate_json_conversion_audit.csv"
)
ROUNDTRIP_RELATIVE = Path(
    "working_inventory/final_aggregate_roundtrip_report.json"
)
NON_NATIVE_HEADER = (
    "json_path",
    "python_type",
    "module",
    "class_name",
    "representative_value",
    "conversion_required",
    "proposed_conversion",
    "scientific_field",
    "notes",
)
CONVERSION_HEADER = (
    "json_path",
    "source_type",
    "target_type",
    "source_summary",
    "target_value",
    "conversion_rule",
)
FORMAL_RUNTIME_STATE_TYPE = (
    "phase_a_harness.formal_runtime_state_machine.FormalRuntimeState"
)
FORMAL_RUNTIME_STATE_CONVERSION_RULE = (
    "EXACT_FORMAL_RUNTIME_STATE_TO_FROZEN_VALUE_V1"
)
FORMAL_RUNTIME_STATE_VALUES = (
    "FORMAL_RUNTIME_ABSENT",
    "FORMAL_RUNTIME_BOOTSTRAP_ONLY",
    "FORMAL_RUNTIME_RESUMABLE",
    "FORMAL_RUNTIME_INVALID",
)
NON_NATIVE_PATH_VALUES = {
    "$.states.absent.state": "FORMAL_RUNTIME_ABSENT",
    "$.states.bootstrap_only.state": "FORMAL_RUNTIME_BOOTSTRAP_ONLY",
    "$.states.resumable.state": "FORMAL_RUNTIME_RESUMABLE",
    "$.bootstrap.state_before": "FORMAL_RUNTIME_ABSENT",
    "$.bootstrap.state_after": "FORMAL_RUNTIME_BOOTSTRAP_ONLY",
    "$.bootstrap_resume.state_before": "FORMAL_RUNTIME_RESUMABLE",
    "$.bootstrap_resume.state_after": "FORMAL_RUNTIME_RESUMABLE",
    "$.lock_transition.state_before": "FORMAL_RUNTIME_BOOTSTRAP_ONLY",
    "$.lock_transition.state_after": "FORMAL_RUNTIME_RESUMABLE",
    "$.lock_resume.state_before": "FORMAL_RUNTIME_RESUMABLE",
    "$.lock_resume.state_after": "FORMAL_RUNTIME_RESUMABLE",
}

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
REQUIRED_TEST_GROUPS = frozenset(
    {
        "json_native_specialized",
        "final_aggregate_roundtrip",
        "envelope_compatibility",
        "bootstrap_state_machine",
        "runtime_lifecycle_specialized",
        "v3_specialized",
        "v2_scientific_chain_regression",
        "full_harness",
        "pcl_fixture",
    }
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
        "3f4c9a84865c3085e7c31928a73fd76ce31e139035dd56b608cf299b9d425310"
    ),
    "src/phase_a_harness/runtime_lifecycle_io.py": (
        "62c69842f67f9da9fd5a6af917a7951995c6dba3b2fd2ca6ab4f6143d56a9b76"
    ),
    "src/phase_a_harness/runtime_lifecycle_fixture.py": (
        "14bc9be9d3c6c6ace54d06140b0179e250ffaf32b0c7bf466c8210bbce47d394"
    ),
    "src/phase_a_harness/runtime_git_gate.py": (
        "acd6818ee229adff259e8b86d7ef2cd3a6febea9ce996aaa332d1680cbdd9dd3"
    ),
    "src/phase_a_harness/synthetic_confirmatory_v3_fixture_publisher_envelope_adapter.py": (
        "e753a0162219dd215131e5811eca182e5440f02d8131fe32715715433d9d2ae9"
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

ALLOWED_CANDIDATE_PATHS = frozenset(
    {
        "src/phase_a_harness/qualification_json_native.py",
        "src/phase_a_harness/synthetic_confirmatory_v3_contract.py",
        "src/phase_a_harness/synthetic_confirmatory_v3_prerun.py",
        (
            "src/phase_a_harness/"
            "synthetic_confirmatory_v3_bootstrap_repair_r3_artifact_verifier.py"
        ),
        "scripts/build_synthetic_confirmatory_v3_bootstrap_repair_r3_prerun.py",
        "scripts/freeze_synthetic_confirmatory_v3_bootstrap_repair_r3.py",
        "scripts/qualify_synthetic_confirmatory_v3_bootstrap_repair_r3.py",
        "scripts/verify_synthetic_confirmatory_v3_bootstrap_repair_r3_artifact.py",
        "tests/test_qualification_json_native.py",
        "tests/test_qualification_final_aggregate.py",
        MANIFEST_RELATIVE.as_posix(),
        PROFILE_RELATIVE.as_posix(),
        *(
            (R2_FAILURE_ARTIFACT_RELATIVE / name).as_posix()
            for name in (
                "final_decision.json",
                "json_serialization_failure.json",
                "non_native_leaf_evidence.json",
                "publisher_subchain_status.json",
                "r2_candidate_binding.json",
                "r2_qualification_root_binding.json",
                "run_manifest.json",
                "v3_seed_status.json",
                "MANIFEST.csv",
                "SHA256SUMS",
            )
        ),
    }
)


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _assert_json_native(value: Any, path: str = "$") -> None:
    value_type = type(value)
    if value is None or value_type in {str, bool, int}:
        return
    if value_type is float:
        if not math.isfinite(value):
            raise ValueError(f"non-finite number at {path}")
        return
    if value_type is list:
        for index, item in enumerate(value):
            _assert_json_native(item, f"{path}[{index}]")
        return
    if value_type is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError(f"non-string JSON key at {path}")
            _assert_json_native(item, f"{path}.{key}")
        return
    raise TypeError(f"non-native JSON value at {path}: {value_type.__name__}")


def _json_bytes(value: Any) -> bytes:
    _assert_json_native(value)
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
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise FileNotFoundError(f"required JSON is absent or linked: {candidate}")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key in {candidate}: {key}")
            result[key] = value
        return result

    def finite_float(token: str) -> float:
        value = float(token)
        if not math.isfinite(value):
            raise ValueError(f"non-finite JSON number in {candidate}")
        return value

    value = json.loads(
        candidate.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_float=finite_float,
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if type(value) is not dict:
        raise ValueError(f"JSON root is not an object: {candidate}")
    _assert_json_native(value)
    return value


def _read_csv(path: Path, expected_header: Sequence[str]) -> tuple[str, list[dict[str, str]]]:
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(f"required CSV is absent or linked: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n") or "\x00" in text:
        raise ValueError(f"CSV is non-canonical: {path}")
    with io.StringIO(text, newline="") as stream:
        reader = csv.DictReader(stream)
        header = tuple(reader.fieldnames or ())
        rows = list(reader)
    if header != tuple(expected_header):
        raise ValueError(f"CSV header mismatch: {path}")
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f"CSV row width mismatch: {path}")
    return text, rows


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments],
        cwd=repository,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def _bundle_pass(repository: Path) -> bool:
    if (
        R2_FAILURE_BUNDLE.is_symlink()
        or not R2_FAILURE_BUNDLE.is_file()
        or _sha256(R2_FAILURE_BUNDLE) != R2_FAILURE_BUNDLE_SHA256
    ):
        return False
    return (
        subprocess.run(
            ["git", "bundle", "verify", str(R2_FAILURE_BUNDLE)],
            cwd=repository,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        ).returncode
        == 0
    )


def _r2_tree_binding() -> dict[str, Any]:
    root = R2_QUALIFICATION_ROOT
    if root.is_symlink() or not root.is_dir():
        raise FileNotFoundError("preserved r2 qualification root is absent or linked")
    files: list[tuple[str, Path]] = []
    unsafe: list[str] = []
    total_size = os.lstat(root).st_size
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in sorted((*dirnames, *filenames)):
            path = base / name
            metadata = os.lstat(path)
            total_size += metadata.st_size
            relative = path.relative_to(root).as_posix()
            if stat.S_ISLNK(metadata.st_mode):
                unsafe.append(relative)
            elif stat.S_ISREG(metadata.st_mode):
                files.append((relative, path))
            elif not stat.S_ISDIR(metadata.st_mode):
                unsafe.append(relative)
    rows = "".join(
        f"{_sha256(path)}  {relative}\n" for relative, path in sorted(files)
    ).encode("utf-8")
    binding = {
        "file_count": len(files),
        "total_size_bytes": total_size,
        "file_content_inventory_sha256": hashlib.sha256(rows).hexdigest(),
        "unsafe_paths": sorted(unsafe),
    }
    if binding != {
        "file_count": R2_ROOT_FILE_COUNT,
        "total_size_bytes": R2_ROOT_SIZE_BYTES,
        "file_content_inventory_sha256": R2_ROOT_INVENTORY_SHA256,
        "unsafe_paths": [],
    }:
        raise PermissionError(f"r2 qualification root preservation failed: {binding}")
    return binding


def _assert_environment(repository: Path) -> None:
    if os.environ.get("PYTHONNOUSERSITE") != "1":
        raise PermissionError("publication requires PYTHONNOUSERSITE=1")
    if os.environ.get("MAMBA_ROOT_PREFIX") != FROZEN_MAMBA_ROOT_PREFIX:
        raise PermissionError("publication requires frozen MAMBA_ROOT_PREFIX")
    if repository == SOURCE_REPOSITORY.resolve() or SOURCE_REPOSITORY.resolve() in repository.parents:
        raise PermissionError("publication must run in the standalone harness")
    if FORMAL_RUNTIME_ROOT.exists() or FORMAL_RUNTIME_ROOT.is_symlink():
        raise PermissionError("formal v3 runtime root exists")
    source = SOURCE_REPOSITORY.resolve()
    for entry in [
        *sys.path,
        *(item for item in os.environ.get("PYTHONPATH", "").split(os.pathsep) if item),
    ]:
        candidate = (Path.cwd() if not entry else Path(entry)).resolve()
        if candidate == source or source in candidate.parents or candidate in source.parents:
            raise PermissionError("source repository is on the Python search path")


def _assert_external_file(path: Path) -> Path:
    candidate = Path(os.path.abspath(os.fspath(path)))
    if QUALIFICATION_ROOT not in candidate.parents:
        raise ValueError(f"evidence is outside the r3 qualification root: {candidate}")
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
        raise PermissionError("candidate tag differs from the frozen r3 tag")
    values = {
        "head": _git(repository, "rev-parse", "HEAD^{commit}"),
        "branch": _git(repository, "branch", "--show-current"),
        "candidate_tag_commit": _git(
            repository, "rev-parse", f"{candidate_tag}^{{commit}}"
        ),
        "r2_candidate_tag_commit": _git(
            repository, "rev-parse", f"{R2_CANDIDATE_TAG}^{{commit}}"
        ),
        "r2_failure_tag_commit": _git(
            repository, "rev-parse", f"{R2_FAILURE_TAG}^{{commit}}"
        ),
        "status": _git(
            repository, "status", "--porcelain=v1", "--untracked-files=all"
        ),
    }
    if not (
        values["head"] == candidate_commit
        and values["branch"] == REPAIR_BRANCH
        and values["candidate_tag_commit"] == candidate_commit
        and values["r2_candidate_tag_commit"] == R2_CANDIDATE_COMMIT
        and values["r2_failure_tag_commit"] == R2_CANDIDATE_COMMIT
        and values["status"] == ""
        and _bundle_pass(repository)
    ):
        raise PermissionError("candidate or preserved r2 Git binding failed")
    return values


def _protected_bindings(repository: Path) -> dict[str, dict[str, str]]:
    bindings: dict[str, dict[str, str]] = {}
    for relative, expected in PROTECTED_SHA256.items():
        actual = _sha256(repository / relative)
        if actual != expected:
            raise PermissionError(f"protected file changed: {relative}")
        bindings[relative] = {
            "expected_sha256": expected,
            "actual_sha256": actual,
        }
    return bindings


def _source_repository_binding() -> dict[str, Any]:
    def source_git(*arguments: str) -> str:
        return subprocess.check_output(
            ["git", *arguments],
            cwd=SOURCE_REPOSITORY,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()

    branch = source_git("branch", "--show-current")
    commit = source_git("rev-parse", "HEAD^{commit}")
    status = source_git("status", "--porcelain=v1", "--untracked-files=all")
    if not (branch == SOURCE_BRANCH and commit == SOURCE_COMMIT and status == ""):
        raise PermissionError("source Degen-LIO repository binding changed")
    return {
        "SOURCE_REPOSITORY_UNMODIFIED": True,
        "branch": branch,
        "commit": commit,
        "status_porcelain": status,
    }


def _normalize_tests(value: Mapping[str, Any], candidate_commit: str) -> dict[str, Any]:
    groups = value.get("groups")
    if type(groups) is not dict or set(groups) != set(REQUIRED_TEST_GROUPS):
        raise ValueError("test report group inventory differs from the frozen nine groups")
    normalized_groups: dict[str, Any] = {}
    for name in sorted(REQUIRED_TEST_GROUPS):
        row = groups[name]
        if type(row) is not dict:
            raise ValueError(f"test group is not an object: {name}")
        tests = row.get("tests", row.get("test_count"))
        passed = row.get("passed", row.get("passed_count"))
        failures = row.get("failures", row.get("failure_count"))
        errors = row.get("errors", row.get("error_count"))
        unexpected = row.get(
            "unexpected_skips",
            row.get("unexpected_skip_count", row.get("skipped")),
        )
        group_pass = row.get("pass", row.get("status") == "PASS")
        junit_value = row.get("junit_path")
        junit_sha256 = row.get("junit_sha256")
        if type(junit_value) is not str or type(junit_sha256) is not str:
            raise ValueError(f"test group omits JUnit binding: {name}")
        junit_path = _assert_external_file(Path(junit_value))
        if _sha256(junit_path) != junit_sha256:
            raise PermissionError(f"test group JUnit SHA changed: {name}")
        try:
            cases = list(ET.parse(junit_path).iter("testcase"))
        except (ET.ParseError, OSError) as error:
            raise ValueError(f"test group JUnit is invalid: {name}: {error}") from error
        junit_failures = sum(
            any(child.tag == "failure" for child in case) for case in cases
        )
        junit_errors = sum(
            any(child.tag == "error" for child in case) for case in cases
        )
        junit_skips = sum(
            any(child.tag == "skipped" for child in case) for case in cases
        )
        junit_passed = len(cases) - junit_failures - junit_errors - junit_skips
        if not (
            type(tests) is int
            and tests > 0
            and type(passed) is int
            and passed == tests
            and type(failures) is int
            and failures == 0
            and type(errors) is int
            and errors == 0
            and type(unexpected) is int
            and unexpected == 0
            and group_pass is True
            and len(cases) == tests
            and junit_passed == passed
            and junit_failures == failures
            and junit_errors == errors
            and junit_skips == unexpected
        ):
            raise PermissionError(f"test group did not pass exactly: {name}")
        normalized_groups[name] = {
            **row,
            "tests": tests,
            "passed": passed,
            "failures": 0,
            "errors": 0,
            "unexpected_skips": 0,
            "pass": True,
        }
    if not (
        value.get("TEST_SUITE_PASS") is True
        and value.get("candidate_commit") == candidate_commit
        and value.get("formal_runtime_root_created") is False
        and value.get("source_degen_lio_pytest_executed") is False
    ):
        raise PermissionError("combined test report binding failed")
    return {**value, "groups": normalized_groups}


def _require_qualification(value: Mapping[str, Any]) -> None:
    required = {
        "QUALIFICATION_JSON_NATIVE_CONTRACT_PASS": True,
        "QUALIFICATION_FINAL_AGGREGATE_JSON_NATIVE_REPAIR_PASS": True,
        "FINAL_AGGREGATE_JSON_NATIVE_PASS": True,
        "FINAL_AGGREGATE_ATOMIC_WRITE_PASS": True,
        "FINAL_AGGREGATE_RELOAD_EQUALITY_PASS": True,
        "NON_JSON_NATIVE_LEAF_COUNT_BEFORE": 11,
        "NON_JSON_NATIVE_LEAF_COUNT_AFTER": 0,
        "FORMAL_RUNTIME_STATE_CONVERSION_COUNT": 11,
        "FORMAL_RUNTIME_STATE_CONVERSION_PASS": True,
        "PATH_CONVERSION_COUNT": 0,
        "TUPLE_CONVERSION_COUNT": 0,
        "NUMPY_SCALAR_CONVERSION_COUNT": 0,
        "UNKNOWN_TYPE_COERCION_COUNT": 0,
        "NONFINITE_JSON_NUMBER_COUNT": 0,
        "NONFINITE_NUMBER_REJECTION_COUNT": 0,
        "INPUT_OBJECT_MUTATION_COUNT": 0,
        "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": True,
        "FIXTURE_ENVELOPE_COMPATIBILITY_PASS": True,
        "PUBLISHER_INPUT_SCHEMA_PASS": True,
        "PUBLISHER_INVENTORY_PASS": True,
        "ARTIFACT_VERIFIER_PASS": True,
        "FRESH_FIXTURE_EXECUTION_PASS": True,
        "RESUME_FIXTURE_EXECUTION_PASS": True,
        "PRIMARY_INDEPENDENT_DIFFERENCE_COUNT": 0,
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
        "ALL_GIT_GATES_PASS": True,
        "V3_SEED_ACCESS_COUNT": 0,
        "V3_RNG_INSTANTIATION_COUNT": 0,
        "V3_SNAPSHOT_CONSTRUCTION_COUNT": 0,
        "V3_BACKEND_EXECUTION_COUNT": 0,
        "V3_TRIAL_RESULT_COUNT": 0,
        "V3_STARTED_EVENT_COUNT": 0,
        "source_repository_runtime_file_read_count": 0,
        "source_repository_runtime_import_count": 0,
        "v3_seed_capable_module_import_count": 0,
        "formal_v1_seed_reference_count": 0,
        "formal_v2_seed_reference_count": 0,
        "formal_v3_seed_reference_count": 0,
        "confirmatory_seed_access_count": 0,
        "confirmatory_rng_instantiation_count": 0,
        "confirmatory_snapshot_construction_count": 0,
        "confirmatory_backend_execution_count": 0,
        "git_gate_failure_count": 0,
        "formal_runtime_root_created": False,
    }
    failures = [
        f"{name}={value.get(name)!r}"
        for name, expected in required.items()
        if type(value.get(name)) is not type(expected) or value.get(name) != expected
    ]
    invalid = value.get("invalid_state_rejection")
    fresh = value.get("fresh")
    resume = value.get("resume")
    dry = value.get("formal_dry_run")
    if not (
        type(invalid) is dict
        and invalid.get("INVALID_RUNTIME_STATE_REJECTION_COUNT") == 20
        and invalid.get("INVALID_RUNTIME_STATE_FALSE_ACCEPT_COUNT") == 0
    ):
        failures.append("invalid-state rejection is not 20/0")
    if not (
        type(fresh) is dict
        and fresh.get("FIXTURE_EXECUTION_CHAIN_PASS") is True
        and fresh.get("fixture_snapshot_count") == 3
        and fresh.get("fixture_trial_count") == 6
        and fresh.get("backend_trial_counts")
        == {"open3d_point_to_plane": 3, "pcl_point_to_plane": 3}
        and fresh.get("native_execution_count") == 0
        and fresh.get("pairing_mismatch_count") == 0
        and fresh.get("outcome_mismatch_count") == 0
        and fresh.get("formal_confirmatory_seed_access_count") == 0
        and fresh.get("fixture_generation_rng_count") == 0
        and fresh.get("new_confirmatory_namespace_generation_count") == 0
    ):
        failures.append("fresh fixture inventory is not 3/6/3+3/0")
    if not (
        type(resume) is dict
        and resume.get("FIXTURE_EXECUTION_CHAIN_PASS") is True
        and resume.get("generated_snapshot_count") == 0
        and resume.get("backend_execution_count_this_invocation") == 0
        and resume.get("resume_skipped_valid_snapshot_count") == 3
        and resume.get("resume_skipped_valid_result_count") == 6
        and resume.get("pairing_mismatch_count") == 0
        and resume.get("outcome_mismatch_count") == 0
        and resume.get("formal_confirmatory_seed_access_count") == 0
        and resume.get("fixture_generation_rng_count") == 0
        and resume.get("new_confirmatory_namespace_generation_count") == 0
    ):
        failures.append("resume re-executed scientific work")
    dry_required = {
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
        "V3_SEED_ACCESS_COUNT": 0,
        "V3_RNG_INSTANTIATION_COUNT": 0,
        "V3_SNAPSHOT_CONSTRUCTION_COUNT": 0,
        "V3_BACKEND_EXECUTION_COUNT": 0,
        "V3_TRIAL_RESULT_COUNT": 0,
        "V3_STARTED_EVENT_COUNT": 0,
    }
    if type(dry) is not dict or any(
        dry.get(name) != expected for name, expected in dry_required.items()
    ):
        failures.append("formal dry-run gate failed")
    states = value.get("states")
    expected_states = {
        "absent": "FORMAL_RUNTIME_ABSENT",
        "bootstrap_only": "FORMAL_RUNTIME_BOOTSTRAP_ONLY",
        "resumable": "FORMAL_RUNTIME_RESUMABLE",
    }
    if type(states) is not dict or any(
        type(states.get(name)) is not dict
        or states[name].get("state") != expected
        for name, expected in expected_states.items()
    ):
        failures.append("normalized runtime-state identity changed")
    if value.get("schema_version") != (
        "synthetic_confirmatory_v3_bootstrap_repair_requalification_v3"
    ):
        failures.append("qualification schema identity changed")
    if value.get("qualification_runtime_root") != str(QUALIFICATION_ROOT):
        failures.append("qualification runtime-root binding changed")
    if value.get("formal_runtime_root") != str(FORMAL_RUNTIME_ROOT):
        failures.append("formal runtime-root binding changed")
    if value.get("source_repository_runtime_import_paths") != []:
        failures.append("source repository runtime import paths are nonempty")
    if value.get("v3_seed_capable_module_imports") != []:
        failures.append("v3 seed-capable modules were imported")
    expected_checkpoints = {
        "PRE_BOOTSTRAP_GIT_GATE",
        "POST_COMMAND_LOG_GIT_GATE",
        "POST_LOCK_GIT_GATE",
        "MID_SNAPSHOT_GIT_GATE",
        "MID_TRIAL_GIT_GATE",
        "RESUME_GIT_GATE",
        "POST_ANALYSIS_GIT_GATE",
        "POST_PUBLISHER_GIT_GATE",
        "FINAL_GIT_GATE",
    }
    git_reports = value.get("git_gate_reports")
    if not (
        type(git_reports) is list
        and len(git_reports) == 9
        and {row.get("checkpoint") for row in git_reports if type(row) is dict}
        == expected_checkpoints
        and all(
            type(row) is dict
            and row.get("RUNTIME_GIT_GATE_PASS") is True
            and row.get("tracked_diff_count") == 0
            and row.get("index_diff_count") == 0
            and row.get("untracked_file_count") == 0
            for row in git_reports
        )
    ):
        failures.append("nine exact Git-gate reports did not pass")
    difference = value.get("primary_independent_difference")
    if not (
        type(difference) is dict
        and difference.get("exact_match_pass") is True
        and difference.get("leaf_difference_count") == 0
        and difference.get("maximum_absolute_numeric_difference") == 0.0
    ):
        failures.append("primary/independent detailed difference is nonzero")
    publication = value.get("publication")
    artifact = value.get("artifact_verification")
    if not (
        type(publication) is dict
        and publication.get("FIXTURE_ARTIFACT_VERIFICATION_PASS") is True
        and publication.get("published_file_count") == 17
        and publication.get("sha256_mismatch_count") == 0
    ):
        failures.append("fixture publisher evidence failed")
    if not (
        type(artifact) is dict
        and artifact.get("FIXTURE_ARTIFACT_VERIFICATION_PASS") is True
        and artifact.get("actual_file_count") == 17
        and artifact.get("required_file_count") == 17
        and artifact.get("sha256_verification_pass") is True
        and all(
            artifact.get(name) == []
            for name in (
                "missing_required_files",
                "extra_files",
                "directory_inventory_errors",
                "invalid_json_files",
                "invalid_png_files",
                "invalid_or_mismatched_csv_files",
                "symlink_paths",
                "sha256_mismatch_files",
                "sha256_missing_files",
                "sha256_unexpected_files",
            )
        )
    ):
        failures.append("fixture artifact-verifier evidence failed")
    if failures:
        raise PermissionError("qualification evidence failed: " + ", ".join(failures))


def _validate_conversion_evidence(
    inventory_path: Path, audit_path: Path, roundtrip_path: Path
) -> tuple[str, str, dict[str, Any]]:
    inventory_text, inventory = _read_csv(inventory_path, NON_NATIVE_HEADER)
    audit_text, audit = _read_csv(audit_path, CONVERSION_HEADER)
    if len(inventory) != 11 or {row["json_path"] for row in inventory} != set(
        NON_NATIVE_PATH_VALUES
    ):
        raise PermissionError("non-native inventory is not the frozen eleven leaves")
    if any(
        row["python_type"] != FORMAL_RUNTIME_STATE_TYPE
        or row["module"] != "phase_a_harness.formal_runtime_state_machine"
        or row["class_name"] != "FormalRuntimeState"
        or row["conversion_required"].lower() != "true"
        or row["proposed_conversion"] != "value.value"
        or row["scientific_field"].lower() != "false"
        for row in inventory
    ):
        raise PermissionError("non-native inventory contains an unapproved type")
    if len(audit) != 11 or {row["json_path"] for row in audit} != set(
        NON_NATIVE_PATH_VALUES
    ):
        raise PermissionError("conversion audit is not the frozen eleven leaves")
    if any(
        row["source_type"] != FORMAL_RUNTIME_STATE_TYPE
        or row["target_type"] != "builtins.str"
        or row["target_value"] != NON_NATIVE_PATH_VALUES[row["json_path"]]
        or row["conversion_rule"] != FORMAL_RUNTIME_STATE_CONVERSION_RULE
        for row in audit
    ):
        raise PermissionError("conversion audit contains an unapproved coercion")
    roundtrip = _strict_object(roundtrip_path)
    required = {
        "QUALIFICATION_JSON_NATIVE_CONTRACT_PASS": True,
        "FINAL_AGGREGATE_JSON_NATIVE_PASS": True,
        "FINAL_AGGREGATE_ATOMIC_WRITE_PASS": True,
        "FINAL_AGGREGATE_RELOAD_EQUALITY_PASS": True,
        "NON_JSON_NATIVE_LEAF_COUNT_BEFORE": 11,
        "NON_JSON_NATIVE_LEAF_COUNT_AFTER": 0,
        "FORMAL_RUNTIME_STATE_CONVERSION_COUNT": 11,
        "FORMAL_RUNTIME_STATE_CONVERSION_PASS": True,
        "PATH_CONVERSION_COUNT": 0,
        "TUPLE_CONVERSION_COUNT": 0,
        "NUMPY_SCALAR_CONVERSION_COUNT": 0,
        "UNKNOWN_TYPE_COERCION_COUNT": 0,
        "NONFINITE_JSON_NUMBER_COUNT": 0,
        "NONFINITE_NUMBER_REJECTION_COUNT": 0,
        "INPUT_OBJECT_MUTATION_COUNT": 0,
    }
    prefixture = roundtrip.get("prefixture_production_shape_roundtrip")
    final_actual = roundtrip.get("final_actual_aggregate_roundtrip")
    if not (
        roundtrip.get("PREFIXTURE_ROUNDTRIP_PASS") is True
        and roundtrip.get("FINAL_ACTUAL_ROUNDTRIP_PASS") is True
        and type(prefixture) is dict
        and type(final_actual) is dict
        and all(roundtrip.get(name) == expected for name, expected in required.items())
        and all(prefixture.get(name) == expected for name, expected in required.items())
        and all(final_actual.get(name) == expected for name, expected in required.items())
        and prefixture.get("PRODUCTION_AGGREGATE_SHAPE_MATCH") is True
        and type(prefixture.get("PRODUCTION_AGGREGATE_SHAPE_SHA256")) is str
    ):
        raise PermissionError("final aggregate round-trip evidence failed")
    return inventory_text, audit_text, {
        **roundtrip,
        "PREFIXTURE_ROUNDTRIP_PASS": True,
        "FINAL_ACTUAL_ROUNDTRIP_PASS": True,
    }


def _verify_r2_failure_artifact(repository: Path) -> dict[str, dict[str, Any]]:
    root = repository / R2_FAILURE_ARTIFACT_RELATIVE
    if root.is_symlink() or not root.is_dir():
        raise FileNotFoundError("r2 JSON failure artifact is absent or linked")
    expected_payload = {
        "final_decision.json",
        "json_serialization_failure.json",
        "non_native_leaf_evidence.json",
        "publisher_subchain_status.json",
        "r2_candidate_binding.json",
        "r2_qualification_root_binding.json",
        "run_manifest.json",
        "v3_seed_status.json",
    }
    entries = list(root.iterdir())
    if any(entry.is_symlink() or not entry.is_file() for entry in entries):
        raise PermissionError("r2 JSON failure artifact has a non-regular entry")
    actual = {entry.name for entry in entries}
    if actual != {*expected_payload, "MANIFEST.csv", "SHA256SUMS"}:
        raise PermissionError("r2 JSON failure artifact inventory changed")
    inventory_bytes = "".join(
        f"{_sha256(root / name)}  {name}\n" for name in sorted(actual)
    ).encode("utf-8")
    if hashlib.sha256(inventory_bytes).hexdigest() != (
        R2_FAILURE_ARTIFACT_INVENTORY_SHA256
    ):
        raise PermissionError("r2 JSON failure artifact byte inventory changed")
    checksums: dict[str, str] = {}
    checksum_order: list[str] = []
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if len(line) < 67 or line[64:66] != "  ":
            raise ValueError("invalid r2 failure SHA256SUMS")
        digest, name = line[:64], line[66:]
        if (
            len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or name in checksums
        ):
            raise ValueError("invalid or duplicate r2 failure SHA256SUMS row")
        checksums[name] = digest
        checksum_order.append(name)
    expected_checksums = {*expected_payload, "MANIFEST.csv"}
    if checksum_order != sorted(expected_checksums) or any(
        _sha256(root / name) != digest for name, digest in checksums.items()
    ):
        raise PermissionError("r2 JSON failure checksums changed")
    manifest_text, manifest_rows = _read_csv(
        root / "MANIFEST.csv", ("path", "sha256", "size_bytes")
    )
    del manifest_text
    if not (
        len(manifest_rows) == len(expected_payload)
        and [row["path"] for row in manifest_rows] == sorted(expected_payload)
        and all(
            row["sha256"] == _sha256(root / row["path"])
            and row["size_bytes"] == str((root / row["path"]).stat().st_size)
            for row in manifest_rows
        )
    ):
        raise PermissionError("r2 JSON failure MANIFEST changed")
    return {name: _strict_object(root / name) for name in expected_payload}


def _write_package(
    destination: Path,
    payload: Mapping[str, Any | str],
    verifier: Any,
) -> dict[str, Any]:
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"refusing to replace pre-run artifact: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.staging-", dir=destination.parent
        )
    )
    staging = temporary / "artifact"
    staging.mkdir()
    try:
        for name, value in payload.items():
            data = value.encode("utf-8") if type(value) is str else _json_bytes(value)
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
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    git = _candidate_binding(repository, candidate_commit, candidate_tag)
    r2_tree_before = _r2_tree_binding()
    r2_archive = _verify_r2_failure_artifact(repository)
    qualification_path = _assert_external_file(qualification_report_path)
    test_path = _assert_external_file(test_report_path)
    if qualification_path != DEFAULT_QUALIFICATION_REPORT or test_path != DEFAULT_TEST_REPORT:
        raise PermissionError("publication requires the two exact qualification evidence paths")
    qualification = _strict_object(qualification_path)
    tests = _normalize_tests(_strict_object(test_path), candidate_commit)
    _require_qualification(qualification)
    protected = _protected_bindings(repository)
    source_binding = _source_repository_binding()

    inventory_path = _assert_external_file(QUALIFICATION_ROOT / INVENTORY_RELATIVE)
    audit_path = _assert_external_file(QUALIFICATION_ROOT / CONVERSION_AUDIT_RELATIVE)
    roundtrip_path = _assert_external_file(QUALIFICATION_ROOT / ROUNDTRIP_RELATIVE)
    inventory_text, audit_text, roundtrip = _validate_conversion_evidence(
        inventory_path, audit_path, roundtrip_path
    )

    sys.path.insert(0, str(repository / "src"))
    from phase_a_harness.synthetic_confirmatory_v3_bootstrap_repair_r3_artifact_verifier import (
        PAYLOAD_FILES,
        verify_bootstrap_repair_r3_prerun_artifact,
    )
    from phase_a_harness.synthetic_confirmatory_v3_contract import load_v3_contract

    manifest_path = repository / MANIFEST_RELATIVE
    profile_path = repository / PROFILE_RELATIVE
    manifest = load_v3_contract(manifest_path)
    profile = _strict_object(profile_path)
    if not (
        manifest.get("expected_release_tag") == FINAL_TAG
        and manifest.get("expected_branch") == REPAIR_BRANCH
        and manifest.get("run_id") == "synthetic-confirmatory-v3"
        and manifest.get("planned_snapshot_count") == 595
        and manifest.get("planned_trial_count") == 1190
        and profile.get("expected_release_tag") == FINAL_TAG
        and profile.get("formal_execution_state") == "NOT_EXECUTED"
    ):
        raise PermissionError("r3 manifest/profile formal identity failed")

    dry = qualification["formal_dry_run"]
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

    changed = sorted(
        name
        for name in _git(
            repository,
            "diff",
            "--name-only",
            f"{R2_CANDIDATE_COMMIT}..{candidate_commit}",
        ).splitlines()
        if name
    )
    protected_changed = sorted(set(changed) & set(PROTECTED_SHA256))
    if protected_changed:
        raise PermissionError(f"candidate changed protected files: {protected_changed}")
    disallowed_changed = sorted(set(changed) - set(ALLOWED_CANDIDATE_PATHS))
    if disallowed_changed:
        raise PermissionError(
            f"candidate changed files outside the r3 repair scope: {disallowed_changed}"
        )

    r2_failure_decision = r2_archive["final_decision.json"]
    r2_serialization = r2_archive["json_serialization_failure.json"]
    r2_candidate = r2_archive["r2_candidate_binding.json"]
    r2_root = r2_archive["r2_qualification_root_binding.json"]
    r2_failure_binding = {
        "schema_version": "synthetic_confirmatory_v3_r2_failure_binding_r3_v1",
        "PREVIOUS_R2_FAILURE_PRESERVED": True,
        "failure_classification": ROOT_CAUSE,
        "failure_json_path": r2_serialization["failure_json_path"],
        "failure_python_type": r2_serialization["first_rejected_python_type"],
        "QUALIFICATION_FINAL_AGGREGATE_WRITE_PASS": False,
        "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": False,
        "CONFIRMATORY_V3_RUN_AUTHORIZED": False,
        "historical_final_decision": r2_failure_decision,
        "failure_archive_tag": R2_FAILURE_TAG,
        "failure_bundle_path": str(R2_FAILURE_BUNDLE),
        "failure_bundle_sha256": R2_FAILURE_BUNDLE_SHA256,
        "failure_artifact_path": R2_FAILURE_ARTIFACT_RELATIVE.as_posix(),
        "failure_artifact_manifest_sha256": _sha256(
            repository / R2_FAILURE_ARTIFACT_RELATIVE / "MANIFEST.csv"
        ),
        "failure_artifact_sha256sums_sha256": _sha256(
            repository / R2_FAILURE_ARTIFACT_RELATIVE / "SHA256SUMS"
        ),
    }
    r2_candidate_binding = {
        **r2_candidate,
        "PREVIOUS_R2_CANDIDATE_PRESERVED": True,
        "R2_CANDIDATE_COMMIT_MODIFIED": False,
        "R2_CANDIDATE_TAG_MOVED": False,
        "live_r2_candidate_tag_commit": git["r2_candidate_tag_commit"],
        "live_r2_failure_tag_commit": git["r2_failure_tag_commit"],
    }
    r2_root_binding = {
        **r2_root,
        **r2_tree_before,
        "PREVIOUS_R2_QUALIFICATION_ROOT_PRESERVED": True,
        "R2_QUALIFICATION_ROOT_MODIFIED": False,
        "qualification_root": str(R2_QUALIFICATION_ROOT),
        "continued_or_reused": False,
    }

    artifact_live = qualification["artifact_verification"]
    publication = qualification["publication"]
    artifact_verification = {
        **artifact_live,
        "ARTIFACT_VERIFIER_PASS": (
            artifact_live.get("FIXTURE_ARTIFACT_VERIFICATION_PASS") is True
        ),
    }
    publisher_inventory = {
        "schema_version": "synthetic_confirmatory_v3_r3_publisher_inventory_v1",
        "PUBLISHER_INVENTORY_PASS": bool(
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
        "publication": publication,
    }
    git_reports = qualification["git_gate_reports"]
    git_gate_report = {
        "schema_version": "synthetic_confirmatory_v3_r3_git_gate_report_v1",
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
    if not (
        len(git_reports) == 9
        and git_gate_report["POST_PUBLISHER_GIT_GATE_PASS"] is True
        and git_gate_report["FINAL_GIT_GATE_PASS"] is True
    ):
        raise PermissionError("nine Git Gate evidence is incomplete")

    previous_bootstrap = {
        "schema_version": "synthetic_confirmatory_v3_r3_previous_bootstrap_binding_v1",
        "FROZEN_ATOMIC_JSON_WRITER_CHANGE_COUNT": 0,
        "BOOTSTRAP_STATE_MACHINE_CORE_CHANGE_COUNT": 0,
        "RUNTIME_LIFECYCLE_CORE_CHANGE_COUNT": 0,
        "state_machine_sha256": PROTECTED_SHA256[
            "src/phase_a_harness/formal_runtime_state_machine.py"
        ],
        "runtime_lifecycle_io_sha256": PROTECTED_SHA256[
            "src/phase_a_harness/runtime_lifecycle_io.py"
        ],
        "runtime_lifecycle_fixture_sha256": PROTECTED_SHA256[
            "src/phase_a_harness/runtime_lifecycle_fixture.py"
        ],
    }
    previous_adapter = {
        "schema_version": "synthetic_confirmatory_v3_r3_previous_envelope_binding_v1",
        "FIXTURE_ENVELOPE_ADAPTER_SCIENTIFIC_CHANGE_COUNT": 0,
        "FROZEN_PUBLISHER_CHANGE_COUNT": 0,
        "ARTIFACT_VERIFIER_CORE_CHANGE_COUNT": 0,
        "PRIMARY_ANALYSIS_CORE_CHANGE_COUNT": 0,
        "INDEPENDENT_VERIFIER_CORE_CHANGE_COUNT": 0,
        "adapter_sha256": PROTECTED_SHA256[
            "src/phase_a_harness/synthetic_confirmatory_v3_fixture_publisher_envelope_adapter.py"
        ],
        "publisher_sha256": PROTECTED_SHA256[
            "src/phase_a_harness/synthetic_confirmatory_v2_publisher.py"
        ],
        "artifact_verifier_sha256": PROTECTED_SHA256[
            "src/phase_a_harness/synthetic_confirmatory_v2_artifact_verifier.py"
        ],
        "primary_sha256": PROTECTED_SHA256[
            "src/phase_a_harness/synthetic_confirmatory_v2_analysis.py"
        ],
        "independent_sha256": PROTECTED_SHA256[
            "src/phase_a_harness/synthetic_confirmatory_v2_independent_verifier.py"
        ],
    }
    bootstrap_report = {
        "schema_version": "synthetic_confirmatory_v3_r3_bootstrap_state_machine_report_v1",
        "QUALIFICATION_FINAL_AGGREGATE_JSON_NATIVE_REPAIR_PASS": True,
        "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": qualification[
            "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS"
        ],
        "ABSENT_STATE_PASS": qualification["ABSENT_STATE_PASS"],
        "BOOTSTRAP_ONLY_STATE_PASS": qualification["BOOTSTRAP_ONLY_STATE_PASS"],
        "RESUMABLE_STATE_PASS": qualification["RESUMABLE_STATE_PASS"],
        "INVALID_STATE_PASS": qualification["INVALID_STATE_PASS"],
        "states": qualification["states"],
    }
    command_report = {
        "schema_version": "synthetic_confirmatory_v3_r3_command_log_interruption_v1",
        "COMMAND_LOG_PRELOCK_INTERRUPTION_PASS": qualification[
            "COMMAND_LOG_PRELOCK_INTERRUPTION_PASS"
        ],
        "BOOTSTRAP_ONLY_RECOVERY_PASS": qualification[
            "BOOTSTRAP_ONLY_RECOVERY_PASS"
        ],
        "command_log_change_after_resume": qualification[
            "command_log_change_after_resume"
        ],
    }
    lock_report = {
        "schema_version": "synthetic_confirmatory_v3_r3_lock_atomic_interruption_v1",
        "LOCK_ATOMIC_INTERRUPTION_PASS": qualification[
            "LOCK_ATOMIC_INTERRUPTION_PASS"
        ],
        "PARTIAL_LOCK_ACCEPTED_COUNT": qualification[
            "PARTIAL_LOCK_ACCEPTED_COUNT"
        ],
        "observation": qualification["interruption_observation"],
    }
    fresh_report = {
        **qualification["fresh"],
        "FRESH_FIXTURE_EXECUTION_PASS": qualification[
            "FRESH_FIXTURE_EXECUTION_PASS"
        ],
    }
    resume_report = {
        **qualification["resume"],
        "RESUME_FIXTURE_EXECUTION_PASS": qualification[
            "RESUME_FIXTURE_EXECUTION_PASS"
        ],
        "VALID_SNAPSHOT_REEXECUTION_COUNT": 0,
        "VALID_TRIAL_REEXECUTION_COUNT": 0,
        "SNAPSHOT_CHECKSUM_CHANGE_AFTER_RESUME": 0,
        "TRIAL_CHECKSUM_CHANGE_AFTER_RESUME": 0,
    }
    difference = {
        **qualification["primary_independent_difference"],
        "PRIMARY_INDEPENDENT_DIFFERENCE_COUNT": 0,
    }
    scientific_diff = {
        "schema_version": (
            "synthetic_confirmatory_v3_r3_qualification_serialization_"
            "scientific_diff_v1"
        ),
        **{name: 0 for name in SCIENTIFIC_ZERO_FIELDS},
        "allowed_differences": {
            "qualification_json_native_helper_difference_count": 1,
            "qualifier_difference_count": 1,
            "qualification_version_metadata_difference_count": 1,
            "formal_manifest_binding_difference_count": 1,
            "pre_run_artifact_difference_count": 1,
            "expected_tag_difference_count": 1,
        },
    }
    implementation_manifest = {
        "schema_version": "synthetic_confirmatory_v3_r3_json_native_implementation_v1",
        "candidate_branch": REPAIR_BRANCH,
        "candidate_commit": candidate_commit,
        "candidate_tag": candidate_tag,
        "base_r2_candidate_commit": R2_CANDIDATE_COMMIT,
        "changed_files": changed,
        "changed_file_count": len(changed),
        "protected_changed_files": protected_changed,
        "implementation_file_sha256": {
            name: _sha256(repository / name) for name in changed
        },
        "FROZEN_ATOMIC_JSON_WRITER_CHANGE_COUNT": 0,
        "V4_CREATED": False,
    }
    final_binding = {
        "schema_version": "synthetic_confirmatory_v3_r3_final_git_binding_v1",
        "FINAL_GIT_BINDING_PASS": True,
        "candidate_commit": candidate_commit,
        "candidate_tag": candidate_tag,
        "candidate_worktree_clean_before_publication": True,
        "required_final_tag": FINAL_TAG,
        "final_transition_scope": [DESTINATION_RELATIVE.as_posix()],
        "final_commit_and_tag_require_post_import_read_only_confirmation": True,
    }
    decision = {
        "schema_version": "synthetic_confirmatory_v3_r3_final_decision_v1",
        "PREVIOUS_R2_FAILURE_PRESERVED": True,
        "PREVIOUS_R2_QUALIFICATION_ROOT_PRESERVED": True,
        "QUALIFICATION_JSON_NATIVE_CONTRACT_PASS": True,
        "FINAL_AGGREGATE_JSON_NATIVE_PASS": True,
        "FINAL_AGGREGATE_ATOMIC_WRITE_PASS": True,
        "FINAL_AGGREGATE_RELOAD_EQUALITY_PASS": True,
        "NON_JSON_NATIVE_LEAF_COUNT_AFTER": 0,
        "UNKNOWN_TYPE_COERCION_COUNT": 0,
        "NONFINITE_JSON_NUMBER_COUNT": 0,
        "NONFINITE_NUMBER_REJECTION_COUNT": 0,
        "FORMAL_RUNTIME_STATE_CONVERSION_COUNT": 11,
        "FORMAL_RUNTIME_STATE_CONVERSION_PASS": True,
        "PATH_CONVERSION_COUNT": 0,
        "TUPLE_CONVERSION_COUNT": 0,
        "NUMPY_SCALAR_CONVERSION_COUNT": 0,
        "INPUT_OBJECT_MUTATION_COUNT": 0,
        "BOOTSTRAP_STATE_MACHINE_CORE_CHANGE_COUNT": 0,
        "RUNTIME_LIFECYCLE_CORE_CHANGE_COUNT": 0,
        "FIXTURE_ENVELOPE_ADAPTER_SCIENTIFIC_CHANGE_COUNT": 0,
        "FROZEN_PUBLISHER_CHANGE_COUNT": 0,
        "ARTIFACT_VERIFIER_CORE_CHANGE_COUNT": 0,
        "PRIMARY_ANALYSIS_CORE_CHANGE_COUNT": 0,
        "INDEPENDENT_VERIFIER_CORE_CHANGE_COUNT": 0,
        "FIXTURE_ENVELOPE_COMPATIBILITY_PASS": True,
        "ABSENT_STATE_PASS": True,
        "BOOTSTRAP_ONLY_STATE_PASS": True,
        "RESUMABLE_STATE_PASS": True,
        "INVALID_STATE_PASS": True,
        "COMMAND_LOG_PRELOCK_INTERRUPTION_PASS": True,
        "BOOTSTRAP_ONLY_RECOVERY_PASS": True,
        "LOCK_ATOMIC_INTERRUPTION_PASS": True,
        "PARTIAL_LOCK_ACCEPTED_COUNT": 0,
        "INVALID_RUNTIME_STATE_FALSE_ACCEPT_COUNT": 0,
        "FRESH_FIXTURE_EXECUTION_PASS": True,
        "RESUME_FIXTURE_EXECUTION_PASS": True,
        "VALID_SNAPSHOT_REEXECUTION_COUNT": 0,
        "VALID_TRIAL_REEXECUTION_COUNT": 0,
        "SNAPSHOT_CHECKSUM_CHANGE_AFTER_RESUME": 0,
        "TRIAL_CHECKSUM_CHANGE_AFTER_RESUME": 0,
        "PRIMARY_INDEPENDENT_DIFFERENCE_COUNT": 0,
        "PUBLISHER_INPUT_SCHEMA_PASS": True,
        "PUBLISHER_INVENTORY_PASS": True,
        "ARTIFACT_VERIFIER_PASS": True,
        "ALL_GIT_GATES_PASS": True,
        "PROTOCOL_BYTE_CHANGE_COUNT": 0,
        "GATE_CONTRACT_BYTE_CHANGE_COUNT": 0,
        "PLAN_BYTE_CHANGE_COUNT": 0,
        "SEED_SCHEDULE_BYTE_CHANGE_COUNT": 0,
        "V3_SEED_VALUE_CHANGE_COUNT": 0,
        "SCIENTIFIC_CORE_FILE_CHANGE_COUNT": 0,
        "H1_H6_SEMANTICS_CHANGE_COUNT": 0,
        "FROZEN_MODEL_CHANGE_COUNT": 0,
        "BACKEND_BINDING_CHANGE_COUNT": 0,
        "V3_SEED_ACCESS_COUNT": 0,
        "V3_RNG_INSTANTIATION_COUNT": 0,
        "V3_SNAPSHOT_CONSTRUCTION_COUNT": 0,
        "V3_BACKEND_EXECUTION_COUNT": 0,
        "V3_TRIAL_RESULT_COUNT": 0,
        "V3_FORMAL_PLAN_PASS": True,
        "V3_DRY_RUN_PASS": True,
        "V3_FORMAL_RUNTIME_ROOT_NOT_CREATED": True,
        "TEST_SUITE_PASS": True,
        "PRE_RUN_ARTIFACT_VERIFICATION_PASS": True,
        "FINAL_GIT_BINDING_PASS": True,
        "QUALIFICATION_FINAL_AGGREGATE_JSON_NATIVE_REPAIR_PASS": True,
        "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": True,
        "SYNTHETIC_CONFIRMATORY_V3_BOOTSTRAP_REPAIR_R3_PRE_RUN_QUALIFICATION_PASS": True,
        "SYNTHETIC_CONFIRMATORY_V3_PRE_RUN_QUALIFICATION_PASS": True,
        "V3_SEED_SET_REUSE_AUTHORIZED": True,
        "CONFIRMATORY_V3_RUN_AUTHORIZED": True,
        "SYNTHETIC_CONFIRMATORY_V3_EXECUTED": False,
        "SYNTHETIC_CONFIRMATORY_V3_COMPLETE": False,
        "SYNTHETIC_CONFIRMATORY_V3_PASS": "NOT_EVALUATED",
        "REAL_DATA_RUN_AUTHORIZED": False,
        "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED": False,
    }
    run_manifest = {
        "schema_version": "synthetic_confirmatory_v3_r3_prerun_manifest_v1",
        "candidate_commit": candidate_commit,
        "candidate_tag": candidate_tag,
        "qualification_root": str(QUALIFICATION_ROOT),
        "qualification_report_path": str(qualification_path),
        "qualification_report_sha256": _sha256(qualification_path),
        "test_report_path": str(test_path),
        "test_report_sha256": _sha256(test_path),
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
        "source_repository": source_binding,
    }
    contract = {
        "schema_version": "qualification_json_native_contract_v1",
        "QUALIFICATION_JSON_NATIVE_CONTRACT_PASS": True,
        "strict_json_native_python_types": [
            "NoneType",
            "str",
            "bool",
            "int",
            "finite_float",
            "list",
            "dict[str,...]",
        ],
        "allowed_formal_runtime_state_values": list(FORMAL_RUNTIME_STATE_VALUES),
        "formal_runtime_state_source_type": FORMAL_RUNTIME_STATE_TYPE,
        "formal_runtime_state_conversion_rule": FORMAL_RUNTIME_STATE_CONVERSION_RULE,
        "path_conversion_enabled": False,
        "tuple_conversion_enabled": False,
        "numpy_scalar_conversion_enabled": False,
        "unknown_type_coercion_enabled": False,
        "json_default_conversion_enabled": False,
        "inventory_counts": {
            "FormalRuntimeState": 11,
            "Path": 0,
            "tuple": 0,
            "NumPy_scalar": 0,
            "other": 0,
            "non_string_dict_key": 0,
            "non_finite_float": 0,
        },
    }
    profile_commands = profile.get("commands")
    if type(profile_commands) is not dict or any(
        type(value) is not str for value in profile_commands.values()
    ):
        raise ValueError("r3 execution profile commands are invalid")

    payload: dict[str, Any | str] = {
        "r2_failure_binding.json": r2_failure_binding,
        "r2_candidate_binding.json": r2_candidate_binding,
        "r2_qualification_root_binding.json": r2_root_binding,
        "json_native_root_cause.json": {
            "schema_version": "synthetic_confirmatory_v3_r3_json_native_root_cause_v1",
            "root_cause": ROOT_CAUSE,
            "failure_json_path": "$.states.absent.state",
            "failure_python_type": "FormalRuntimeState",
            "NON_JSON_NATIVE_LEAF_COUNT_BEFORE": 11,
            "non_native_leaf_type_counts": {"FormalRuntimeState": 11},
            "repair_scope": "qualification final aggregate only",
            "frozen_atomic_json_writer_modified": False,
        },
        "final_aggregate_non_native_type_inventory.csv": inventory_text,
        "qualification_json_native_contract.json": contract,
        "final_aggregate_json_conversion_audit.csv": audit_text,
        "final_aggregate_roundtrip_report.json": roundtrip,
        "previous_bootstrap_binding.json": previous_bootstrap,
        "previous_envelope_adapter_binding.json": previous_adapter,
        "bootstrap_state_machine_report.json": bootstrap_report,
        "command_log_prelock_interruption_report.json": command_report,
        "lock_atomic_interruption_report.json": lock_report,
        "invalid_state_rejection_report.json": qualification[
            "invalid_state_rejection"
        ],
        "fresh_fixture_report.json": fresh_report,
        "resume_fixture_report.json": resume_report,
        "primary_independent_difference.json": difference,
        "publisher_input_validation.json": qualification[
            "publisher_input_validation"
        ],
        "publisher_inventory.json": publisher_inventory,
        "artifact_verification.json": artifact_verification,
        "git_gate_report.json": git_gate_report,
        "scientific_core_binding.json": {
            "schema_version": "synthetic_confirmatory_v3_r3_scientific_core_binding_v1",
            "SCIENTIFIC_CORE_FILE_CHANGE_COUNT": 0,
            "protected_files": protected,
            "source_repository": source_binding,
        },
        "h1_h6_semantics_binding.json": {
            "schema_version": "synthetic_confirmatory_v3_r3_h1_h6_binding_v1",
            "H1_H6_SEMANTICS_CHANGE_COUNT": 0,
            "gate_contract_sha256": PROTECTED_SHA256[
                "protocols/synthetic_confirmatory_gate_contract_v3.json"
            ],
        },
        "frozen_model_binding.json": {
            "schema_version": "synthetic_confirmatory_v3_r3_frozen_model_binding_v1",
            "FROZEN_MODEL_CHANGE_COUNT": 0,
            "sha256": PROTECTED_SHA256[
                "frozen_assets/confirmatory_development_trained_models_v1.json"
            ],
        },
        "backend_binding.json": {
            "schema_version": "synthetic_confirmatory_v3_r3_backend_binding_v1",
            "BACKEND_BINDING_CHANGE_COUNT": 0,
            "bindings": manifest["backend_bindings"],
            "pcl_cli_sha256": PROTECTED_SHA256["bin/pcl_point_to_plane_cli"],
            "native_trial_count": 0,
        },
        "v3_seed_binding.json": {
            "schema_version": "synthetic_confirmatory_v3_r3_seed_binding_v1",
            "V3_SEED_VALUE_CHANGE_COUNT": 0,
            "V3_SEED_ACCESS_COUNT": 0,
            "V3_RNG_INSTANTIATION_COUNT": 0,
            "V3_SNAPSHOT_CONSTRUCTION_COUNT": 0,
            "V3_BACKEND_EXECUTION_COUNT": 0,
            "V3_TRIAL_RESULT_COUNT": 0,
            "seed_schedule_sha256": PROTECTED_SHA256[
                "frozen_assets/synthetic_confirmatory_v3_seed_schedule.json"
            ],
            "seed_values_materialized_by_publication": False,
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
        "formal_manifest_binding.json": {
            "schema_version": "synthetic_confirmatory_v3_r3_manifest_binding_v1",
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
            "# Frozen commands only; publication executed none of them.\n"
            + "\n".join(profile_commands.values())
            + "\n"
        ),
        "final_binding_audit.json": final_binding,
        "final_decision.json": decision,
        "run_manifest.json": run_manifest,
        "pre_run_report.md": (
            "# Synthetic Confirmatory v3 Bootstrap Repair r3\n\n"
            "Strict qualification aggregate normalization, full seed-free "
            "requalification, frozen fixture publication, and formal dry-run passed.\n\n"
            "CONFIRMATORY_V3_RUN_AUTHORIZED = true\n\n"
            "SYNTHETIC_CONFIRMATORY_V3_EXECUTED = false\n"
        ),
        "synthetic_confirmatory_v3_r3_qualification_serialization_scientific_diff.json": (
            scientific_diff
        ),
    }
    if set(payload) != set(PAYLOAD_FILES):
        raise AssertionError(
            "payload inventory differs; "
            f"missing={sorted(set(PAYLOAD_FILES) - set(payload))}, "
            f"extra={sorted(set(payload) - set(PAYLOAD_FILES))}"
        )
    def candidate_stage_verifier(path: Path) -> dict[str, Any]:
        return verify_bootstrap_repair_r3_prerun_artifact(
            path,
            require_final_git_binding=False,
        )

    verification = _write_package(
        destination, payload, candidate_stage_verifier
    )
    if _r2_tree_binding() != r2_tree_before:
        raise RuntimeError("publication modified the r2 qualification root")
    if FORMAL_RUNTIME_ROOT.exists() or FORMAL_RUNTIME_ROOT.is_symlink():
        raise RuntimeError("publication created the formal runtime root")
    status = _git(repository, "status", "--porcelain=v1", "--untracked-files=all")
    changed_after = {line[3:] for line in status.splitlines() if len(line) >= 4}
    if not changed_after or not all(
        path.startswith(DESTINATION_RELATIVE.as_posix()) for path in changed_after
    ):
        raise RuntimeError(f"publication changed unexpected paths: {sorted(changed_after)}")
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
    parser.add_argument(
        "--expected-candidate-tag", default=CANDIDATE_TAG, choices=(CANDIDATE_TAG,)
    )
    parser.add_argument(
        "--qualification-report", type=Path, default=DEFAULT_QUALIFICATION_REPORT
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
