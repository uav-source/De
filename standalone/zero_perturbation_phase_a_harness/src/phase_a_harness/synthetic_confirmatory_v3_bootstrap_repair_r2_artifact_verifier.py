"""Strict verifier for the compact v3 bootstrap-repair r2 pre-run package.

This module is deliberately independent of the execution, publisher, and
scientific-analysis modules.  It only reads a flat compact artifact, verifies
its byte inventories, and checks the frozen pre-run authorization evidence.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Iterable, Mapping


PAYLOAD_FILES = (
    "previous_candidate_failure_binding.json",
    "previous_candidate_tag_binding.json",
    "previous_qualification_root_binding.json",
    "publisher_envelope_failure_binding.json",
    "publisher_envelope_root_cause.json",
    "frozen_publisher_contract_inventory.json",
    "fixture_envelope_adapter_contract.json",
    "fixture_envelope_scientific_equivalence.json",
    "fixture_seed_reference_audit.json",
    "bootstrap_state_machine_binding.json",
    "command_log_prelock_interruption_report.json",
    "lock_atomic_interruption_report.json",
    "invalid_state_rejection_report.json",
    "fresh_fixture_report.json",
    "resume_fixture_report.json",
    "primary_independent_difference.json",
    "publisher_input_validation.json",
    "publisher_inventory.json",
    "artifact_verification.json",
    "git_gate_report.json",
    "scientific_core_binding.json",
    "h1_h6_semantics_binding.json",
    "frozen_model_binding.json",
    "backend_binding.json",
    "v3_seed_binding.json",
    "protocol_byte_binding.json",
    "gate_contract_byte_binding.json",
    "plan_byte_binding.json",
    "seed_schedule_byte_binding.json",
    "synthetic_confirmatory_v3_publisher_envelope_repair_scientific_diff.json",
    "formal_manifest_binding.json",
    "formal_plan_audit.json",
    "formal_dry_run_report.json",
    "test_report.json",
    "implementation_manifest.json",
    "formal_execution_profile.json",
    "formal_run_commands.sh",
    "final_binding_audit.json",
    "final_decision.json",
    "run_manifest.json",
    "pre_run_report.md",
)
INVENTORY_FILES = ("MANIFEST.csv", "SHA256SUMS")
EXPECTED_FILES = frozenset((*PAYLOAD_FILES, *INVENTORY_FILES))
JSON_FILES = tuple(name for name in PAYLOAD_FILES if name.endswith(".json"))

FORMAL_RUNTIME_ROOT = Path(
    "/home/lj/zero_perturbation_runtime/confirmatory/synthetic_confirmatory_v3"
)
FAILED_CANDIDATE_COMMIT = "37a2625365012b0deefb59bbc068fd8283174b5a"
FAILED_CANDIDATE_TAG = (
    "archive/zero-perturbation-synthetic-confirmatory-v3-bootstrap-repair-candidate"
)
FAILED_QUALIFICATION_ROOT = Path(
    "/home/lj/zero_perturbation_runtime/qualification/"
    "v3_bootstrap_state_machine_v1"
)
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

SCIENTIFIC_ZERO_DIFFERENCE_FIELDS = (
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


class BootstrapRepairR2ArtifactError(RuntimeError):
    """The r2 compact package root is absent, linked, or otherwise unsafe."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_sha256(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _strict_object(path: Path) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=pairs,
        parse_constant=lambda token: (_ for _ in ()).throw(
            ValueError(f"non-finite JSON token: {token}")
        ),
    )
    if type(value) is not dict:
        raise ValueError("JSON root must be an object")
    return value


def _symlink_components(path: Path) -> list[str]:
    current = Path(path.anchor)
    linked: list[str] = []
    for part in path.parts[1:]:
        current = current / part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            linked.append(str(current))
    return linked


def _flat_inventory(root: Path) -> tuple[set[str], list[str]]:
    files: set[str] = set()
    unsafe: list[str] = []
    with os.scandir(root) as iterator:
        entries = list(iterator)
    for entry in entries:
        metadata = entry.stat(follow_symlinks=False)
        if stat.S_ISREG(metadata.st_mode):
            files.add(entry.name)
        else:
            unsafe.append(entry.name)
    return files, sorted(unsafe)


def _verify_manifest(root: Path) -> tuple[int, list[str]]:
    path = root / "MANIFEST.csv"
    if not path.is_file() or path.is_symlink():
        return 0, ["MANIFEST.csv is absent or linked"]
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = tuple(reader.fieldnames or ())
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        return 0, [f"MANIFEST.csv is unreadable: {error}"]
    if fields != ("path", "size_bytes", "sha256"):
        return len(rows), ["MANIFEST.csv header mismatch"]

    errors: list[str] = []
    seen: set[str] = set()
    for row in rows:
        relative = row.get("path", "")
        digest = row.get("sha256")
        candidate = root / relative
        if relative in seen or relative not in PAYLOAD_FILES:
            errors.append(f"invalid or duplicate MANIFEST path: {relative}")
            continue
        seen.add(relative)
        try:
            size = int(row.get("size_bytes", ""))
        except (TypeError, ValueError):
            errors.append(f"invalid MANIFEST size: {relative}")
            continue
        if str(size) != row.get("size_bytes") or size < 0:
            errors.append(f"non-canonical MANIFEST size: {relative}")
        if not _is_sha256(digest):
            errors.append(f"invalid MANIFEST SHA-256: {relative}")
        if not candidate.is_file() or candidate.is_symlink():
            errors.append(f"missing or linked MANIFEST payload: {relative}")
        elif (
            candidate.stat().st_size != size
            or not _is_sha256(digest)
            or _sha256(candidate) != digest
        ):
            errors.append(f"MANIFEST payload mismatch: {relative}")
    if seen != set(PAYLOAD_FILES):
        errors.append("MANIFEST payload inventory mismatch")
    return len(rows), errors


def _verify_sha256sums(root: Path) -> tuple[int, list[str]]:
    path = root / "SHA256SUMS"
    expected = EXPECTED_FILES - {"SHA256SUMS"}
    if not path.is_file() or path.is_symlink():
        return 0, ["SHA256SUMS is absent or linked"]
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        return 0, [f"SHA256SUMS is unreadable: {error}"]
    errors: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if len(line) < 67 or line[64:66] != "  ":
            errors.append("malformed SHA256SUMS row")
            continue
        digest, relative = line[:64], line[66:]
        candidate = root / relative
        if (
            relative in seen
            or relative not in expected
            or not _is_sha256(digest)
        ):
            errors.append(f"invalid or duplicate SHA256SUMS row: {relative}")
            continue
        seen.add(relative)
        if (
            not candidate.is_file()
            or candidate.is_symlink()
            or _sha256(candidate) != digest
        ):
            errors.append(f"SHA256SUMS payload mismatch: {relative}")
    if seen != expected:
        errors.append("SHA256SUMS inventory mismatch")
    return len(seen), errors


def _exact(actual: Any, expected: Any) -> bool:
    if type(expected) is bool:
        return type(actual) is bool and actual is expected
    if type(expected) is int:
        return type(actual) is int and actual == expected
    if type(expected) is float:
        return (
            type(actual) in (int, float)
            and type(actual) is not bool
            and actual == expected
        )
    return type(actual) is type(expected) and actual == expected


def _expect(
    objects: Mapping[str, Mapping[str, Any]],
    filename: str,
    expected: Mapping[str, Any],
) -> list[str]:
    value = objects.get(filename, {})
    return [
        f"{filename}: expected {key}={wanted!r}, got {value.get(key)!r}"
        for key, wanted in expected.items()
        if not _exact(value.get(key), wanted)
    ]


def _nested_values(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, Mapping):
        for item in value.values():
            yield from _nested_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _nested_values(item)


def _semantic_errors(objects: Mapping[str, Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    expected_by_file: dict[str, dict[str, Any]] = {
        "previous_candidate_failure_binding.json": {
            "PREVIOUS_PUBLISHER_FAILURE_PRESERVED": True,
        },
        "previous_candidate_tag_binding.json": {
            "PREVIOUS_CANDIDATE_TAG_PRESERVED": True,
        },
        "previous_qualification_root_binding.json": {
            "PREVIOUS_QUALIFICATION_ROOT_PRESERVED": True,
        },
        "publisher_envelope_failure_binding.json": {
            "PUBLISHER_INPUT_CONTRACT_PASS": False,
            "PUBLISHER_INVENTORY_PASS": False,
            "ARTIFACT_VERIFIER_PASS": False,
            "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": False,
            "SYNTHETIC_CONFIRMATORY_V3_BOOTSTRAP_REPAIR_PRE_RUN_QUALIFICATION_PASS": False,
            "CONFIRMATORY_V3_RUN_AUTHORIZED": False,
            "V3_SEED_ACCESS_COUNT": 0,
        },
        "frozen_publisher_contract_inventory.json": {
            "FROZEN_PUBLISHER_CHANGE_COUNT": 0,
            "ARTIFACT_VERIFIER_CORE_CHANGE_COUNT": 0,
        },
        "fixture_envelope_adapter_contract.json": {
            "FIXTURE_ENVELOPE_COMPATIBILITY_PASS": True,
        },
        "fixture_envelope_scientific_equivalence.json": {
            "FIXTURE_ENVELOPE_SCIENTIFIC_LEAF_DIFFERENCE_COUNT": 0,
            "FIXTURE_ENVELOPE_SCIENTIFIC_MAX_NUMERICAL_DIFFERENCE": 0.0,
            "FIXTURE_ENVELOPE_SCIENTIFIC_EQUIVALENCE_PASS": True,
            "original_input_modified": False,
        },
        "fixture_seed_reference_audit.json": {
            "formal_v1_seed_reference_count": 0,
            "formal_v2_seed_reference_count": 0,
            "formal_v3_seed_reference_count": 0,
            "confirmatory_seed_access_count": 0,
            "confirmatory_rng_instantiation_count": 0,
            "confirmatory_snapshot_construction_count": 0,
            "confirmatory_backend_execution_count": 0,
        },
        "bootstrap_state_machine_binding.json": {
            "BOOTSTRAP_STATE_MACHINE_CORE_CHANGE_COUNT": 0,
            "RUNTIME_LIFECYCLE_CORE_CHANGE_COUNT": 0,
            "ABSENT_STATE_PASS": True,
            "BOOTSTRAP_ONLY_STATE_PASS": True,
            "RESUMABLE_STATE_PASS": True,
            "INVALID_STATE_PASS": True,
        },
        "command_log_prelock_interruption_report.json": {
            "COMMAND_LOG_PRELOCK_INTERRUPTION_PASS": True,
            "BOOTSTRAP_ONLY_RECOVERY_PASS": True,
        },
        "lock_atomic_interruption_report.json": {
            "LOCK_ATOMIC_INTERRUPTION_PASS": True,
            "PARTIAL_LOCK_ACCEPTED_COUNT": 0,
        },
        "invalid_state_rejection_report.json": {
            "INVALID_RUNTIME_STATE_REJECTION_COUNT": 20,
            "INVALID_RUNTIME_STATE_FALSE_ACCEPT_COUNT": 0,
        },
        "fresh_fixture_report.json": {
            "FRESH_FIXTURE_EXECUTION_PASS": True,
        },
        "resume_fixture_report.json": {
            "RESUME_FIXTURE_EXECUTION_PASS": True,
            "VALID_SNAPSHOT_REEXECUTION_COUNT": 0,
            "VALID_TRIAL_REEXECUTION_COUNT": 0,
            "SNAPSHOT_CHECKSUM_CHANGE_AFTER_RESUME": 0,
            "TRIAL_CHECKSUM_CHANGE_AFTER_RESUME": 0,
        },
        "primary_independent_difference.json": {
            "PRIMARY_INDEPENDENT_DIFFERENCE_COUNT": 0,
        },
        "publisher_input_validation.json": {
            "FIXTURE_ENVELOPE_COMPATIBILITY_PASS": True,
            "PUBLISHER_INPUT_SCHEMA_PASS": True,
            "adapter_output_field_count": 8,
            "extra_output_field_count": 0,
            "formal_v2_seed_reference_count": 0,
            "original_input_modified": False,
        },
        "publisher_inventory.json": {
            "PUBLISHER_INVENTORY_PASS": True,
            "table_count": 7,
            "figure_count": 3,
            "root_file_count": 7,
            "published_file_count": 17,
        },
        "artifact_verification.json": {
            "ARTIFACT_VERIFIER_PASS": True,
            "actual_file_count": 17,
            "required_file_count": 17,
            "missing_required_files": [],
            "extra_files": [],
            "directory_inventory_errors": [],
            "invalid_json_files": [],
            "invalid_png_files": [],
            "invalid_or_mismatched_csv_files": [],
            "symlink_paths": [],
            "sha256_mismatch_files": [],
            "sha256_missing_files": [],
            "sha256_unexpected_files": [],
            "sha256_verification_pass": True,
        },
        "git_gate_report.json": {
            "POST_PUBLISHER_GIT_GATE_PASS": True,
            "FINAL_GIT_GATE_PASS": True,
            "ALL_GIT_GATES_PASS": True,
        },
        "scientific_core_binding.json": {
            "SCIENTIFIC_CORE_FILE_CHANGE_COUNT": 0,
            "PRIMARY_ANALYSIS_CORE_CHANGE_COUNT": 0,
            "INDEPENDENT_VERIFIER_CORE_CHANGE_COUNT": 0,
        },
        "h1_h6_semantics_binding.json": {
            "H1_H6_SEMANTICS_CHANGE_COUNT": 0,
        },
        "frozen_model_binding.json": {
            "FROZEN_MODEL_CHANGE_COUNT": 0,
        },
        "backend_binding.json": {
            "BACKEND_BINDING_CHANGE_COUNT": 0,
        },
        "v3_seed_binding.json": {
            "V3_SEED_VALUE_CHANGE_COUNT": 0,
            "V3_SEED_ACCESS_COUNT": 0,
            "V3_RNG_INSTANTIATION_COUNT": 0,
            "V3_SNAPSHOT_CONSTRUCTION_COUNT": 0,
            "V3_BACKEND_EXECUTION_COUNT": 0,
            "V3_TRIAL_RESULT_COUNT": 0,
        },
        "protocol_byte_binding.json": {"PROTOCOL_BYTE_CHANGE_COUNT": 0},
        "gate_contract_byte_binding.json": {"GATE_CONTRACT_BYTE_CHANGE_COUNT": 0},
        "plan_byte_binding.json": {"PLAN_BYTE_CHANGE_COUNT": 0},
        "seed_schedule_byte_binding.json": {"SEED_SCHEDULE_BYTE_CHANGE_COUNT": 0},
        "formal_manifest_binding.json": {"FORMAL_MANIFEST_BINDING_PASS": True},
        "formal_plan_audit.json": {"V3_FORMAL_PLAN_PASS": True},
        "formal_dry_run_report.json": {
            "V3_DRY_RUN_PASS": True,
            "V3_FORMAL_RUNTIME_ROOT_NOT_CREATED": True,
        },
        "test_report.json": {"TEST_SUITE_PASS": True},
        "final_binding_audit.json": {"FINAL_GIT_BINDING_PASS": True},
        "final_decision.json": {
            "PREVIOUS_PUBLISHER_FAILURE_PRESERVED": True,
            "PREVIOUS_CANDIDATE_TAG_PRESERVED": True,
            "PREVIOUS_QUALIFICATION_ROOT_PRESERVED": True,
            "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": True,
            "FIXTURE_ENVELOPE_COMPATIBILITY_PASS": True,
            "SYNTHETIC_CONFIRMATORY_V3_BOOTSTRAP_REPAIR_PRE_RUN_QUALIFICATION_PASS": True,
            "V3_SEED_SET_REUSE_AUTHORIZED": True,
            "CONFIRMATORY_V3_RUN_AUTHORIZED": True,
            "SYNTHETIC_CONFIRMATORY_V3_EXECUTED": False,
            "SYNTHETIC_CONFIRMATORY_V3_COMPLETE": False,
            "SYNTHETIC_CONFIRMATORY_V3_PASS": "NOT_EVALUATED",
            "REAL_DATA_RUN_AUTHORIZED": False,
            "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED": False,
        },
        "run_manifest.json": {
            "formal_backend_execution_count": 0,
            "formal_rng_instantiation_count": 0,
            "formal_seed_access_count": 0,
            "formal_snapshot_construction_count": 0,
            "formal_trial_result_count": 0,
            "formal_runtime_root_created": False,
            "planned_snapshot_count": 595,
            "planned_trial_count": 1190,
        },
    }
    for filename, expected in expected_by_file.items():
        errors.extend(_expect(objects, filename, expected))

    scientific = objects.get(
        "synthetic_confirmatory_v3_publisher_envelope_repair_scientific_diff.json",
        {},
    )
    for field in SCIENTIFIC_ZERO_DIFFERENCE_FIELDS:
        if not _exact(scientific.get(field), 0):
            errors.append(
                "synthetic_confirmatory_v3_publisher_envelope_repair_scientific_diff.json: "
                f"expected {field}=0, got {scientific.get(field)!r}"
            )

    failure_values = {
        value
        for value in _nested_values(
            objects.get("publisher_envelope_failure_binding.json", {})
        )
        if isinstance(value, str)
    }
    for required in (
        ROOT_CAUSE,
        FAILED_CANDIDATE_COMMIT,
        FAILED_CANDIDATE_TAG,
        str(FAILED_QUALIFICATION_ROOT),
    ):
        if required not in failure_values:
            errors.append(
                "publisher_envelope_failure_binding.json: missing frozen failure "
                f"identity {required!r}"
            )

    publisher = objects.get("publisher_inventory.json", {})
    for field, expected in (
        ("tables", FIXTURE_TABLES),
        ("figures", FIXTURE_FIGURES),
        ("root_files", FIXTURE_ROOT_FILES),
    ):
        if publisher.get(field) != list(expected):
            errors.append(
                f"publisher_inventory.json: {field} differs from frozen fixture inventory"
            )
    return errors


def verify_bootstrap_repair_r2_prerun_artifact(
    path: str | Path,
    *,
    require_formal_runtime_absent: bool = True,
) -> dict[str, Any]:
    """Verify one flat compact r2 package without importing execution code."""

    root = Path(os.path.abspath(os.fspath(path)))
    linked_components = _symlink_components(root)
    if linked_components or root.is_symlink() or not root.is_dir():
        raise BootstrapRepairR2ArtifactError(
            "artifact root is absent, linked, or not a directory"
        )

    files, unsafe = _flat_inventory(root)
    missing = sorted(EXPECTED_FILES - files)
    extra = sorted(files - EXPECTED_FILES)
    manifest_count, manifest_errors = _verify_manifest(root)
    sha_count, sha_errors = _verify_sha256sums(root)

    objects: dict[str, dict[str, Any]] = {}
    invalid_json: list[str] = []
    for name in JSON_FILES:
        candidate = root / name
        if not candidate.is_file() or candidate.is_symlink():
            continue
        try:
            objects[name] = _strict_object(candidate)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            invalid_json.append(f"{name}: {error}")

    invalid_text: list[str] = []
    for name in ("formal_run_commands.sh", "pre_run_report.md"):
        candidate = root / name
        if not candidate.is_file() or candidate.is_symlink():
            continue
        try:
            text = candidate.read_text(encoding="utf-8")
            if not text or "\x00" in text:
                invalid_text.append(name)
        except (OSError, UnicodeError):
            invalid_text.append(name)

    semantic_errors = _semantic_errors(objects)
    formal_runtime_absent = not FORMAL_RUNTIME_ROOT.exists()
    previous_qualification_root_exists = FAILED_QUALIFICATION_ROOT.is_dir()
    passed = bool(
        not missing
        and not extra
        and not unsafe
        and not manifest_errors
        and not sha_errors
        and not invalid_json
        and not invalid_text
        and not semantic_errors
        and (formal_runtime_absent or not require_formal_runtime_absent)
        and previous_qualification_root_exists
    )
    return {
        "PRE_RUN_ARTIFACT_VERIFICATION_PASS": passed,
        "actual_file_count": len(files),
        "expected_file_count": len(EXPECTED_FILES),
        "extra_files": extra,
        "formal_runtime_root_absent": formal_runtime_absent,
        "formal_runtime_root_absence_required": require_formal_runtime_absent,
        "invalid_json_files": invalid_json,
        "invalid_text_files": invalid_text,
        "manifest_entry_count": manifest_count,
        "manifest_errors": manifest_errors,
        "missing_files": missing,
        "previous_qualification_root_exists": previous_qualification_root_exists,
        "schema_version": (
            "synthetic_confirmatory_v3_bootstrap_repair_r2_"
            "artifact_verification_v1"
        ),
        "semantic_errors": semantic_errors,
        "semantic_gate_pass": not semantic_errors,
        "sha256_entry_count": sha_count,
        "sha256_errors": sha_errors,
        "symlink_component_paths": linked_components,
        "unsafe_entries": unsafe,
    }


__all__ = [
    "BootstrapRepairR2ArtifactError",
    "EXPECTED_FILES",
    "INVENTORY_FILES",
    "PAYLOAD_FILES",
    "verify_bootstrap_repair_r2_prerun_artifact",
]
