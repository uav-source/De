"""Strict verifier for the compact v3 JSON-native-repair pre-run package.

The verifier is deliberately independent of qualification, execution, publisher,
and scientific-analysis code.  It accepts one exact, flat 44-file envelope,
authenticates both byte inventories, validates every JSON/CSV/text payload, and
then evaluates the complete r3 pre-run authorization contract fail closed.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import stat
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping


PAYLOAD_FILES = (
    "r2_failure_binding.json",
    "r2_candidate_binding.json",
    "r2_qualification_root_binding.json",
    "json_native_root_cause.json",
    "final_aggregate_non_native_type_inventory.csv",
    "qualification_json_native_contract.json",
    "final_aggregate_json_conversion_audit.csv",
    "final_aggregate_roundtrip_report.json",
    "previous_bootstrap_binding.json",
    "previous_envelope_adapter_binding.json",
    "bootstrap_state_machine_report.json",
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
    "synthetic_confirmatory_v3_r3_qualification_serialization_scientific_diff.json",
)
INVENTORY_FILES = ("MANIFEST.csv", "SHA256SUMS")
EXPECTED_FILES = frozenset((*PAYLOAD_FILES, *INVENTORY_FILES))
JSON_FILES = tuple(name for name in PAYLOAD_FILES if name.endswith(".json"))
CSV_PAYLOAD_FILES = (
    "final_aggregate_non_native_type_inventory.csv",
    "final_aggregate_json_conversion_audit.csv",
)
TEXT_PAYLOAD_FILES = ("formal_run_commands.sh", "pre_run_report.md")

FORMAL_RUNTIME_ROOT = Path(
    "/home/lj/zero_perturbation_runtime/confirmatory/synthetic_confirmatory_v3"
)
HARNESS_REPOSITORY = Path(__file__).resolve().parents[2]
REPAIR_BRANCH = "fix/zero-perturbation-v3-qualification-json-native-r3"
CANDIDATE_TAG = (
    "archive/zero-perturbation-synthetic-confirmatory-v3-"
    "qualification-json-native-r3-candidate"
)
FINAL_TAG = (
    "archive/zero-perturbation-synthetic-confirmatory-v3-"
    "bootstrap-repair-r3-pre-run-pass"
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
SOURCE_REPOSITORY = Path("/home/lj/Degen-LIO")
SOURCE_BRANCH = "feature/zero-perturbation-phase-a-lock-v2-regression-repair"
SOURCE_COMMIT = "89f46dda68e9ff5c71f078f6d13fc9050d58f0f5"
R2_QUALIFICATION_ROOT = Path(
    "/home/lj/zero_perturbation_runtime/qualification/"
    "v3_bootstrap_state_machine_requalification_v2"
)
R2_CANDIDATE_COMMIT = "767e79fe4e518fbef290a43018c29581f028d6cd"
R2_FAILURE_TAG = (
    "archive/zero-perturbation-synthetic-confirmatory-v3-"
    "bootstrap-repair-r2-json-native-fail"
)
R2_FAILURE_BUNDLE_SHA256 = (
    "dac9210de93c182ab57c3a322ea89fd7f878fe2f90625395ae0150ceb8c3490c"
)
R2_ROOT_FILE_COUNT = 76
R2_ROOT_SIZE_BYTES = 705331
R2_ROOT_INVENTORY_SHA256 = (
    "dd9ba5ea28b3538584425f7246be23707ed5ec540f97d30c1049d7b227b900eb"
)
ROOT_CAUSE = "QUALIFICATION_FINAL_AGGREGATE_NON_JSON_NATIVE_ENUM"
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

NON_NATIVE_INVENTORY_HEADER = (
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
CONVERSION_AUDIT_HEADER = (
    "json_path",
    "source_type",
    "target_type",
    "source_summary",
    "target_value",
    "conversion_rule",
)

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


class BootstrapRepairR3ArtifactError(RuntimeError):
    """The r3 compact artifact root is absent, linked, or otherwise unsafe."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_sha256(value: Any) -> bool:
    return bool(
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _parse_finite_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"non-finite JSON number: {token}")
    return value


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
        parse_float=_parse_finite_float,
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


def _read_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        header = tuple(reader.fieldnames or ())
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("CSV row width differs from header")
    if any("\x00" in value for row in rows for value in row.values()):
        raise ValueError("CSV contains NUL")
    return header, rows


def _verify_manifest(root: Path) -> tuple[int, list[str]]:
    path = root / "MANIFEST.csv"
    if not path.is_file() or path.is_symlink():
        return 0, ["MANIFEST.csv is absent or linked"]
    try:
        header, rows = _read_csv(path)
    except (OSError, UnicodeError, csv.Error, ValueError) as error:
        return 0, [f"MANIFEST.csv is invalid: {error}"]
    if header != ("path", "size_bytes", "sha256"):
        return len(rows), ["MANIFEST.csv header mismatch"]

    errors: list[str] = []
    seen: set[str] = set()
    order: list[str] = []
    for row in rows:
        relative = row["path"]
        digest = row["sha256"]
        order.append(relative)
        if (
            relative in seen
            or relative not in PAYLOAD_FILES
            or Path(relative).name != relative
        ):
            errors.append(f"invalid or duplicate MANIFEST path: {relative}")
            continue
        seen.add(relative)
        try:
            size = int(row["size_bytes"])
        except ValueError:
            errors.append(f"invalid MANIFEST size: {relative}")
            continue
        if str(size) != row["size_bytes"] or size < 0:
            errors.append(f"non-canonical MANIFEST size: {relative}")
        if not _is_sha256(digest):
            errors.append(f"invalid MANIFEST SHA-256: {relative}")
        candidate = root / relative
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
    if order != sorted(order):
        errors.append("MANIFEST paths are not canonically sorted")
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
    order: list[str] = []
    for line in lines:
        if len(line) < 67 or line[64:66] != "  ":
            errors.append("malformed SHA256SUMS row")
            continue
        digest, relative = line[:64], line[66:]
        order.append(relative)
        if (
            relative in seen
            or relative not in expected
            or Path(relative).name != relative
            or not _is_sha256(digest)
        ):
            errors.append(f"invalid or duplicate SHA256SUMS row: {relative}")
            continue
        seen.add(relative)
        candidate = root / relative
        if (
            not candidate.is_file()
            or candidate.is_symlink()
            or _sha256(candidate) != digest
        ):
            errors.append(f"SHA256SUMS payload mismatch: {relative}")
    if seen != expected:
        errors.append("SHA256SUMS inventory mismatch")
    if order != sorted(order):
        errors.append("SHA256SUMS paths are not canonically sorted")
    return len(seen), errors


def _verify_csv_payloads(root: Path) -> tuple[dict[str, list[dict[str, str]]], list[str]]:
    parsed: dict[str, list[dict[str, str]]] = {}
    errors: list[str] = []
    expected_headers = {
        CSV_PAYLOAD_FILES[0]: NON_NATIVE_INVENTORY_HEADER,
        CSV_PAYLOAD_FILES[1]: CONVERSION_AUDIT_HEADER,
    }
    for name in CSV_PAYLOAD_FILES:
        path = root / name
        if not path.is_file() or path.is_symlink():
            continue
        try:
            header, rows = _read_csv(path)
        except (OSError, UnicodeError, csv.Error, ValueError) as error:
            errors.append(f"{name}: {error}")
            continue
        if header != expected_headers[name]:
            errors.append(f"{name}: header mismatch")
            continue
        parsed[name] = rows

    inventory = parsed.get(CSV_PAYLOAD_FILES[0], [])
    if len(inventory) != 11:
        errors.append("non-native inventory must contain exactly 11 rows")
    inventory_paths = [row.get("json_path") for row in inventory]
    if set(inventory_paths) != set(NON_NATIVE_PATH_VALUES) or len(set(inventory_paths)) != 11:
        errors.append("non-native inventory path set mismatch")
    for row in inventory:
        if not (
            row.get("python_type") == FORMAL_RUNTIME_STATE_TYPE
            and row.get("module") == "phase_a_harness.formal_runtime_state_machine"
            and row.get("class_name") == "FormalRuntimeState"
            and row.get("conversion_required", "").lower() == "true"
            and row.get("proposed_conversion") == "value.value"
            and row.get("scientific_field", "").lower() == "false"
            and bool(row.get("representative_value"))
            and bool(row.get("notes"))
        ):
            errors.append(f"invalid non-native inventory row: {row.get('json_path')}")

    audit = parsed.get(CSV_PAYLOAD_FILES[1], [])
    if len(audit) != 11:
        errors.append("conversion audit must contain exactly 11 rows")
    audit_paths = [row.get("json_path") for row in audit]
    if set(audit_paths) != set(NON_NATIVE_PATH_VALUES) or len(set(audit_paths)) != 11:
        errors.append("conversion audit path set mismatch")
    for row in audit:
        path = row.get("json_path", "")
        if not (
            row.get("source_type") == FORMAL_RUNTIME_STATE_TYPE
            and row.get("target_type") == "builtins.str"
            and row.get("target_value") == NON_NATIVE_PATH_VALUES.get(path)
            and row.get("conversion_rule") == FORMAL_RUNTIME_STATE_CONVERSION_RULE
            and bool(row.get("source_summary"))
        ):
            errors.append(f"invalid conversion audit row: {path}")
    return parsed, errors


def _verify_text_payloads(root: Path) -> list[str]:
    errors: list[str] = []
    values: dict[str, str] = {}
    for name in TEXT_PAYLOAD_FILES:
        path = root / name
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            errors.append(f"{name}: {error}")
            continue
        if not text or "\x00" in text or not text.endswith("\n"):
            errors.append(f"{name}: empty, non-canonical, or contains NUL")
        values[name] = text
    commands = values.get("formal_run_commands.sh", "")
    if commands and not commands.startswith("#!/usr/bin/env bash\n"):
        errors.append("formal_run_commands.sh: missing frozen bash header")
    report = values.get("pre_run_report.md", "")
    for required in (
        "CONFIRMATORY_V3_RUN_AUTHORIZED = true",
        "SYNTHETIC_CONFIRMATORY_V3_EXECUTED = false",
    ):
        if report and required not in report:
            errors.append(f"pre_run_report.md: missing {required}")
    return errors


def _exact(actual: Any, expected: Any) -> bool:
    if type(expected) is bool:
        return type(actual) is bool and actual is expected
    if type(expected) is int:
        return type(actual) is int and actual == expected
    if type(expected) is float:
        return type(actual) in {int, float} and type(actual) is not bool and actual == expected
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


def _test_report_errors(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if value.get("TEST_SUITE_PASS") is not True:
        errors.append("test_report.json: TEST_SUITE_PASS is not true")
    if value.get("source_degen_lio_pytest_executed") is not False:
        errors.append("test_report.json: source Degen-LIO pytest was not excluded")
    groups = value.get("groups")
    if type(groups) is not dict or set(groups) != set(REQUIRED_TEST_GROUPS):
        errors.append("test_report.json: required test group inventory mismatch")
        return errors
    for name in sorted(REQUIRED_TEST_GROUPS):
        row = groups.get(name)
        if type(row) is not dict:
            errors.append(f"test_report.json: invalid group {name}")
            continue
        tests = row.get("tests", row.get("test_count"))
        passed = row.get("passed", row.get("passed_count"))
        failures = row.get("failures", row.get("failure_count"))
        error_count = row.get("errors", row.get("error_count"))
        unexpected = row.get(
            "unexpected_skips", row.get("unexpected_skip_count")
        )
        group_pass = row.get("pass", row.get("status") == "PASS")
        if not (
            type(tests) is int
            and type(tests) is not bool
            and tests > 0
            and type(passed) is int
            and type(passed) is not bool
            and passed == tests
            and failures == 0
            and error_count == 0
            and unexpected == 0
            and group_pass is True
        ):
            errors.append(f"test_report.json: test group failed: {name}")
    return errors


def _semantic_errors(objects: Mapping[str, Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    expected_by_file: dict[str, dict[str, Any]] = {
        "r2_failure_binding.json": {
            "PREVIOUS_R2_FAILURE_PRESERVED": True,
            "QUALIFICATION_FINAL_AGGREGATE_WRITE_PASS": False,
            "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": False,
            "CONFIRMATORY_V3_RUN_AUTHORIZED": False,
        },
        "r2_candidate_binding.json": {
            "R2_CANDIDATE_COMMIT_MODIFIED": False,
            "R2_CANDIDATE_TAG_MOVED": False,
        },
        "r2_qualification_root_binding.json": {
            "PREVIOUS_R2_QUALIFICATION_ROOT_PRESERVED": True,
            "R2_QUALIFICATION_ROOT_MODIFIED": False,
            "file_count": R2_ROOT_FILE_COUNT,
            "total_size_bytes": R2_ROOT_SIZE_BYTES,
        },
        "json_native_root_cause.json": {
            "root_cause": ROOT_CAUSE,
            "failure_json_path": "$.states.absent.state",
            "failure_python_type": "FormalRuntimeState",
            "NON_JSON_NATIVE_LEAF_COUNT_BEFORE": 11,
        },
        "qualification_json_native_contract.json": {
            "QUALIFICATION_JSON_NATIVE_CONTRACT_PASS": True,
            "formal_runtime_state_conversion_rule": FORMAL_RUNTIME_STATE_CONVERSION_RULE,
            "path_conversion_enabled": False,
            "tuple_conversion_enabled": False,
            "numpy_scalar_conversion_enabled": False,
            "unknown_type_coercion_enabled": False,
            "json_default_conversion_enabled": False,
        },
        "final_aggregate_roundtrip_report.json": {
            "FINAL_AGGREGATE_JSON_NATIVE_PASS": True,
            "FINAL_AGGREGATE_ATOMIC_WRITE_PASS": True,
            "FINAL_AGGREGATE_RELOAD_EQUALITY_PASS": True,
            "PREFIXTURE_ROUNDTRIP_PASS": True,
            "FINAL_ACTUAL_ROUNDTRIP_PASS": True,
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
        },
        "previous_bootstrap_binding.json": {
            "FROZEN_ATOMIC_JSON_WRITER_CHANGE_COUNT": 0,
            "BOOTSTRAP_STATE_MACHINE_CORE_CHANGE_COUNT": 0,
            "RUNTIME_LIFECYCLE_CORE_CHANGE_COUNT": 0,
        },
        "previous_envelope_adapter_binding.json": {
            "FIXTURE_ENVELOPE_ADAPTER_SCIENTIFIC_CHANGE_COUNT": 0,
            "FROZEN_PUBLISHER_CHANGE_COUNT": 0,
            "ARTIFACT_VERIFIER_CORE_CHANGE_COUNT": 0,
            "PRIMARY_ANALYSIS_CORE_CHANGE_COUNT": 0,
            "INDEPENDENT_VERIFIER_CORE_CHANGE_COUNT": 0,
        },
        "bootstrap_state_machine_report.json": {
            "QUALIFICATION_FINAL_AGGREGATE_JSON_NATIVE_REPAIR_PASS": True,
            "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": True,
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
            "fixture_snapshot_count": 3,
            "fixture_trial_count": 6,
            "native_execution_count": 0,
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
            "maximum_absolute_numeric_difference": 0.0,
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
            "checkpoint_count": 9,
        },
        "scientific_core_binding.json": {"SCIENTIFIC_CORE_FILE_CHANGE_COUNT": 0},
        "h1_h6_semantics_binding.json": {"H1_H6_SEMANTICS_CHANGE_COUNT": 0},
        "frozen_model_binding.json": {"FROZEN_MODEL_CHANGE_COUNT": 0},
        "backend_binding.json": {"BACKEND_BINDING_CHANGE_COUNT": 0},
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
        "formal_plan_audit.json": {
            "V3_FORMAL_PLAN_PASS": True,
            "planned_snapshot_count": 595,
            "planned_trial_count": 1190,
            "duplicate_snapshot_count": 0,
            "duplicate_trial_count": 0,
            "pairing_violation_count": 0,
            "independent_pseudoreplication_plan_count": 0,
            "native_trial_count": 0,
        },
        "formal_dry_run_report.json": {
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
        },
        "implementation_manifest.json": {
            "FROZEN_ATOMIC_JSON_WRITER_CHANGE_COUNT": 0,
            "protected_changed_files": [],
            "V4_CREATED": False,
        },
        "final_binding_audit.json": {"FINAL_GIT_BINDING_PASS": True},
        "run_manifest.json": {
            "formal_seed_access_count": 0,
            "formal_rng_instantiation_count": 0,
            "formal_snapshot_construction_count": 0,
            "formal_backend_execution_count": 0,
            "formal_trial_result_count": 0,
            "formal_runtime_root_created": False,
            "planned_snapshot_count": 595,
            "planned_trial_count": 1190,
        },
    }
    for filename, expected in expected_by_file.items():
        errors.extend(_expect(objects, filename, expected))

    final_expected = {
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
    errors.extend(_expect(objects, "final_decision.json", final_expected))

    contract = objects.get("qualification_json_native_contract.json", {})
    if contract.get("allowed_formal_runtime_state_values") != list(
        FORMAL_RUNTIME_STATE_VALUES
    ):
        errors.append("qualification_json_native_contract.json: frozen state set mismatch")
    if contract.get("strict_json_native_python_types") != [
        "NoneType",
        "str",
        "bool",
        "int",
        "finite_float",
        "list",
        "dict[str,...]",
    ]:
        errors.append("qualification_json_native_contract.json: native type whitelist mismatch")

    fresh = objects.get("fresh_fixture_report.json", {})
    if fresh.get("backend_trial_counts") != {
        "open3d_point_to_plane": 3,
        "pcl_point_to_plane": 3,
    }:
        errors.append("fresh_fixture_report.json: backend 3/3 inventory mismatch")

    publisher = objects.get("publisher_inventory.json", {})
    for field, expected in (
        ("tables", FIXTURE_TABLES),
        ("figures", FIXTURE_FIGURES),
        ("root_files", FIXTURE_ROOT_FILES),
    ):
        if publisher.get(field) != list(expected):
            errors.append(f"publisher_inventory.json: frozen {field} mismatch")

    dry = objects.get("formal_dry_run_report.json", {})
    if dry.get("condition_snapshot_counts") != {
        "FULL_NOISE": 525,
        "IDEAL_MATCHED": 35,
        "INDEPENDENT_NOISE_FREE": 35,
    }:
        errors.append("formal_dry_run_report.json: condition inventory mismatch")
    if dry.get("backend_trial_counts") != {
        "Native": 0,
        "Open3D": 595,
        "PCL": 595,
    }:
        errors.append("formal_dry_run_report.json: backend inventory mismatch")

    errors.extend(_test_report_errors(objects.get("test_report.json", {})))

    scientific = objects.get(
        "synthetic_confirmatory_v3_r3_qualification_serialization_scientific_diff.json",
        {},
    )
    for field in SCIENTIFIC_ZERO_DIFFERENCE_FIELDS:
        if not _exact(scientific.get(field), 0):
            errors.append(
                "synthetic_confirmatory_v3_r3_qualification_serialization_"
                f"scientific_diff.json: expected {field}=0, got {scientific.get(field)!r}"
            )

    r2_values = {
        value
        for filename in (
            "r2_failure_binding.json",
            "r2_candidate_binding.json",
            "r2_qualification_root_binding.json",
        )
        for value in _nested_values(objects.get(filename, {}))
        if type(value) is str
    }
    for required in (
        ROOT_CAUSE,
        R2_CANDIDATE_COMMIT,
        R2_FAILURE_TAG,
        R2_FAILURE_BUNDLE_SHA256,
        str(R2_QUALIFICATION_ROOT),
        R2_ROOT_INVENTORY_SHA256,
    ):
        if required not in r2_values:
            errors.append(f"r2 preservation bindings omit {required!r}")
    return errors


def _r2_root_binding() -> dict[str, Any]:
    root = R2_QUALIFICATION_ROOT
    if root.is_symlink() or not root.is_dir():
        return {
            "preserved": False,
            "file_count": 0,
            "total_size_bytes": 0,
            "inventory_sha256": None,
            "unsafe_paths": [str(root)],
        }
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
    inventory = hashlib.sha256(rows).hexdigest()
    preserved = bool(
        not unsafe
        and len(files) == R2_ROOT_FILE_COUNT
        and total_size == R2_ROOT_SIZE_BYTES
        and inventory == R2_ROOT_INVENTORY_SHA256
    )
    return {
        "preserved": preserved,
        "file_count": len(files),
        "total_size_bytes": total_size,
        "inventory_sha256": inventory,
        "unsafe_paths": sorted(unsafe),
    }


def _canonical_identity_sha256(value: Mapping[str, Any]) -> str:
    payload = (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_manifest_sha256(value: Mapping[str, Any]) -> str:
    """Match contracts.canonical_json_sha256 (which has no final newline)."""

    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _git(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments],
        cwd=HARNESS_REPOSITORY,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def _live_static_binding_errors(
    artifact_root: Path,
    objects: Mapping[str, Mapping[str, Any]],
    *,
    require_final_git_binding: bool,
) -> tuple[list[str], bool]:
    errors: list[str] = []
    manifest_path = HARNESS_REPOSITORY / MANIFEST_RELATIVE
    profile_path = HARNESS_REPOSITORY / PROFILE_RELATIVE
    try:
        manifest = _strict_object(manifest_path)
        profile = _strict_object(profile_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as error:
        return [f"live manifest/profile is invalid: {error}"], False

    manifest_core = {
        key: value
        for key, value in manifest.items()
        if key != "manifest_payload_sha256"
    }
    profile_core = {
        key: value
        for key, value in profile.items()
        if key != "execution_profile_payload_sha256"
    }
    binding = objects.get("formal_manifest_binding.json", {})
    if not (
        binding.get("path") == MANIFEST_RELATIVE.as_posix()
        and binding.get("sha256") == _sha256(manifest_path)
        and binding.get("payload_sha256") == manifest.get("manifest_payload_sha256")
        and binding.get("profile_path") == PROFILE_RELATIVE.as_posix()
        and binding.get("profile_sha256") == _sha256(profile_path)
        and binding.get("profile_payload_sha256")
        == profile.get("execution_profile_payload_sha256")
        and manifest.get("manifest_payload_sha256")
        == _canonical_manifest_sha256(manifest_core)
        and profile.get("execution_profile_payload_sha256")
        == _canonical_identity_sha256(profile_core)
        and manifest.get("expected_branch") == REPAIR_BRANCH
        and manifest.get("expected_release_tag") == FINAL_TAG
        and manifest.get("planned_snapshot_count") == 595
        and manifest.get("planned_trial_count") == 1190
        and profile.get("expected_branch") == REPAIR_BRANCH
        and profile.get("expected_release_tag") == FINAL_TAG
        and profile.get("formal_execution_state") == "NOT_EXECUTED"
    ):
        errors.append("live r3 manifest/profile binding mismatch")

    bound_files = manifest.get("bound_files")
    if type(bound_files) is not dict:
        errors.append("live r3 manifest bound_files is invalid")
    else:
        for name, row in bound_files.items():
            if type(name) is not str or type(row) is not dict:
                errors.append("live r3 manifest has an invalid bound-file row")
                continue
            relative = row.get("path")
            digest = row.get("sha256")
            if type(relative) is not str or type(digest) is not str:
                errors.append(f"live bound-file row is incomplete: {name}")
                continue
            candidate = HARNESS_REPOSITORY / relative
            try:
                resolved = candidate.resolve(strict=True)
            except (OSError, RuntimeError):
                errors.append(f"live bound file is absent: {name}")
                continue
            if not (
                HARNESS_REPOSITORY == resolved
                or HARNESS_REPOSITORY in resolved.parents
            ) or candidate.is_symlink() or not candidate.is_file():
                errors.append(f"live bound file is unsafe: {name}")
            elif _sha256(candidate) != digest:
                errors.append(f"live bound-file SHA mismatch: {name}")

    backend = objects.get("backend_binding.json", {})
    if not (
        backend.get("bindings") == manifest.get("backend_bindings")
        and backend.get("native_trial_count") == 0
        and backend.get("pcl_cli_sha256")
        == "d42ce655df74117f0e6965c9df1326526fabba9f4e65ed10a5644ed911fad7ff"
    ):
        errors.append("backend binding differs from the live formal manifest")

    commands = profile.get("commands")
    expected_commands = ""
    if type(commands) is dict and all(type(value) is str for value in commands.values()):
        expected_commands = (
            "#!/usr/bin/env bash\n"
            "# Frozen commands only; publication executed none of them.\n"
            + "\n".join(commands.values())
            + "\n"
        )
    try:
        actual_commands = (artifact_root / "formal_run_commands.sh").read_text(
            encoding="utf-8"
        )
    except (OSError, UnicodeError):
        actual_commands = ""
    if not expected_commands or actual_commands != expected_commands:
        errors.append("formal run commands differ from the live execution profile")

    source_binding = objects.get("scientific_core_binding.json", {}).get(
        "source_repository"
    )
    run_source_binding = objects.get("run_manifest.json", {}).get(
        "source_repository"
    )
    try:
        source_branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=SOURCE_REPOSITORY,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD^{commit}"],
            cwd=SOURCE_REPOSITORY,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
        source_status = subprocess.check_output(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=SOURCE_REPOSITORY,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
        expected_source = {
            "SOURCE_REPOSITORY_UNMODIFIED": True,
            "branch": SOURCE_BRANCH,
            "commit": SOURCE_COMMIT,
            "status_porcelain": "",
        }
        if not (
            source_branch == SOURCE_BRANCH
            and source_commit == SOURCE_COMMIT
            and source_status == ""
            and source_binding == expected_source
            and run_source_binding == expected_source
        ):
            errors.append("source Degen-LIO repository binding changed")
    except (OSError, subprocess.CalledProcessError):
        errors.append("source Degen-LIO repository binding is unreadable")

    final_git_pass = False
    final_binding = objects.get("final_binding_audit.json", {})
    candidate_commit = final_binding.get("candidate_commit")
    try:
        candidate_tag_commit = _git("rev-parse", f"{CANDIDATE_TAG}^{{commit}}")
        branch = _git("branch", "--show-current")
        if require_final_git_binding:
            head = _git("rev-parse", "HEAD^{commit}")
            final_tag_commit = _git("rev-parse", f"{FINAL_TAG}^{{commit}}")
            parents = _git("rev-list", "--parents", "-n", "1", "HEAD").split()
            changed = {
                name
                for name in _git(
                    "diff", "--name-only", f"{candidate_commit}..{head}"
                ).splitlines()
                if name
            }
            expected_changed = {
                (DESTINATION_RELATIVE / name).as_posix() for name in EXPECTED_FILES
            }
            final_git_pass = bool(
                type(candidate_commit) is str
                and candidate_tag_commit == candidate_commit
                and branch == REPAIR_BRANCH
                and final_tag_commit == head
                and len(parents) == 2
                and parents[1] == candidate_commit
                and changed == expected_changed
                and _git("status", "--porcelain=v1", "--untracked-files=all") == ""
                and _git("log", "-1", "--format=%s")
                == "docs: publish v3 bootstrap repair r3 qualification"
                and artifact_root == HARNESS_REPOSITORY / DESTINATION_RELATIVE
            )
        else:
            final_git_pass = bool(
                type(candidate_commit) is str
                and candidate_tag_commit == candidate_commit
                and branch == REPAIR_BRANCH
            )
    except (OSError, subprocess.CalledProcessError, ValueError, TypeError) as error:
        errors.append(f"live Git binding check failed: {error}")
    if not final_git_pass:
        errors.append(
            "final Git binding is absent or differs"
            if require_final_git_binding
            else "candidate Git binding differs"
        )
    return errors, final_git_pass


def verify_bootstrap_repair_r3_prerun_artifact(
    path: str | Path,
    *,
    require_formal_runtime_absent: bool = True,
    require_final_git_binding: bool = True,
) -> dict[str, Any]:
    """Verify one exact, flat r3 pre-run package without execution imports."""

    root = Path(os.path.abspath(os.fspath(path)))
    linked_components = _symlink_components(root)
    if linked_components or root.is_symlink() or not root.is_dir():
        raise BootstrapRepairR3ArtifactError(
            "artifact root is absent, linked, or not a directory"
        )

    files, unsafe = _flat_inventory(root)
    missing = sorted(EXPECTED_FILES - files)
    extra = sorted(files - EXPECTED_FILES)
    manifest_count, manifest_errors = _verify_manifest(root)
    sha_count, sha_errors = _verify_sha256sums(root)
    _, invalid_csv = _verify_csv_payloads(root)
    invalid_text = _verify_text_payloads(root)

    objects: dict[str, dict[str, Any]] = {}
    invalid_json: list[str] = []
    for name in JSON_FILES:
        candidate = root / name
        if not candidate.is_file() or candidate.is_symlink():
            continue
        try:
            objects[name] = _strict_object(candidate)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as error:
            invalid_json.append(f"{name}: {error}")

    semantic_errors = _semantic_errors(objects)
    live_binding_errors, final_git_binding_pass = _live_static_binding_errors(
        root,
        objects,
        require_final_git_binding=require_final_git_binding,
    )
    formal_runtime_absent = not os.path.lexists(FORMAL_RUNTIME_ROOT)
    r2_root = _r2_root_binding()
    passed = bool(
        not missing
        and not extra
        and not unsafe
        and not manifest_errors
        and not sha_errors
        and not invalid_json
        and not invalid_csv
        and not invalid_text
        and not semantic_errors
        and not live_binding_errors
        and r2_root["preserved"] is True
        and (formal_runtime_absent or not require_formal_runtime_absent)
    )
    return {
        "PRE_RUN_ARTIFACT_VERIFICATION_PASS": passed,
        "actual_file_count": len(files),
        "expected_file_count": len(EXPECTED_FILES),
        "extra_files": extra,
        "formal_runtime_root_absent": formal_runtime_absent,
        "formal_runtime_root_absence_required": require_formal_runtime_absent,
        "FINAL_GIT_BINDING_PASS": final_git_binding_pass,
        "final_git_binding_required": require_final_git_binding,
        "invalid_csv_files": invalid_csv,
        "invalid_json_files": invalid_json,
        "invalid_text_files": invalid_text,
        "manifest_entry_count": manifest_count,
        "manifest_errors": manifest_errors,
        "live_binding_errors": live_binding_errors,
        "missing_files": missing,
        "previous_r2_qualification_root": r2_root,
        "schema_version": (
            "synthetic_confirmatory_v3_bootstrap_repair_r3_"
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
    "BootstrapRepairR3ArtifactError",
    "EXPECTED_FILES",
    "INVENTORY_FILES",
    "PAYLOAD_FILES",
    "verify_bootstrap_repair_r3_prerun_artifact",
]
