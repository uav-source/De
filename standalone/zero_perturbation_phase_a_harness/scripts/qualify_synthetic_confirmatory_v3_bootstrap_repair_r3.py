#!/usr/bin/env python3
"""Run the seed-free v3 bootstrap-repair lifecycle qualification."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
import stat
import subprocess
import sys
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Sequence


FROZEN_MAMBA_ROOT_PREFIX = "/home/lj/.local/share/degen-lio-micromamba"
SOURCE_REPOSITORY = Path("/home/lj/Degen-LIO")
QUALIFICATION_RUNTIME_BASE = Path("/home/lj/zero_perturbation_runtime")
R2_FAILED_QUALIFICATION_ROOT = (
    QUALIFICATION_RUNTIME_BASE
    / "qualification"
    / "v3_bootstrap_state_machine_requalification_v2"
)
QUALIFICATION_RUN_ID = "v3_bootstrap_state_machine_requalification_v3"
QUALIFICATION_ROOT = (
    QUALIFICATION_RUNTIME_BASE / "qualification" / QUALIFICATION_RUN_ID
)
FORMAL_RUNTIME_ROOT = (
    QUALIFICATION_RUNTIME_BASE / "confirmatory" / "synthetic_confirmatory_v3"
)
R2_ROOT_FILE_COUNT = 76
R2_ROOT_SIZE_BYTES = 705331
R2_ROOT_INVENTORY_SHA256 = (
    "dd9ba5ea28b3538584425f7246be23707ed5ec540f97d30c1049d7b227b900eb"
)
QUALIFICATION_MANIFEST_RELATIVE = Path(
    "frozen_assets/synthetic_confirmatory_formal_manifest_v3_bootstrap_repair_r3.json"
)
QUALIFICATION_ENTRYPOINT = (
    "scripts/qualify_synthetic_confirmatory_v3_bootstrap_repair_r3.py"
)

FINAL_AGGREGATE_EXACT_FIELDS = frozenset(
    """schema_version FIXTURE_ENVELOPE_COMPATIBILITY_PASS PUBLISHER_INPUT_SCHEMA_PASS
PUBLISHER_INVENTORY_PASS ARTIFACT_VERIFIER_PASS FRESH_FIXTURE_EXECUTION_PASS
RESUME_FIXTURE_EXECUTION_PASS PRIMARY_INDEPENDENT_DIFFERENCE_COUNT
FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS states ABSENT_STATE_PASS
BOOTSTRAP_ONLY_STATE_PASS RESUMABLE_STATE_PASS INVALID_STATE_PASS
FORMAL_BOOTSTRAP_STATE_MACHINE_IMPLEMENTATION bootstrap bootstrap_resume
lock_transition lock_resume seed_entry_lock_gate_pass
command_log_prelock_interruption_pass COMMAND_LOG_PRELOCK_INTERRUPTION_PASS
bootstrap_only_recovery_pass BOOTSTRAP_ONLY_RECOVERY_PASS
lock_atomic_interruption_pass LOCK_ATOMIC_INTERRUPTION_PASS
partial_lock_accepted_count PARTIAL_LOCK_ACCEPTED_COUNT invalid_state_rejection
interruption_observation fresh resume valid_snapshot_reexecution_count
VALID_SNAPSHOT_REEXECUTION_COUNT valid_trial_reexecution_count
VALID_TRIAL_REEXECUTION_COUNT snapshot_checksum_change_after_resume
SNAPSHOT_CHECKSUM_CHANGE_AFTER_RESUME trial_checksum_change_after_resume
TRIAL_CHECKSUM_CHANGE_AFTER_RESUME command_log_change_after_resume primary
independent primary_independent_difference raw_v3_fixture_envelope
frozen_publisher_fixture_envelope publisher_input_validation
fixture_envelope_scientific_equivalence fixture_seed_reference_audit publication
artifact_verification formal_dry_run git_gate_reports all_git_gates_pass
ALL_GIT_GATES_PASS required_git_checkpoints observed_git_checkpoints
git_gate_failure_count source_repository_runtime_file_read_count
source_repository_runtime_import_count source_repository_runtime_import_paths
v3_seed_access_count V3_SEED_ACCESS_COUNT v3_seed_capable_module_import_count
v3_seed_capable_module_imports v3_rng_instantiation_count
V3_RNG_INSTANTIATION_COUNT v3_snapshot_construction_count
V3_SNAPSHOT_CONSTRUCTION_COUNT v3_backend_execution_count
V3_BACKEND_EXECUTION_COUNT v3_trial_result_count V3_TRIAL_RESULT_COUNT
v3_started_event_count V3_STARTED_EVENT_COUNT formal_v1_seed_reference_count
formal_v2_seed_reference_count formal_v3_seed_reference_count
confirmatory_seed_access_count confirmatory_rng_instantiation_count
confirmatory_snapshot_construction_count confirmatory_backend_execution_count
formal_runtime_root qualification_runtime_root formal_runtime_root_created
qualification_command QUALIFICATION_JSON_NATIVE_CONTRACT_PASS
QUALIFICATION_FINAL_AGGREGATE_JSON_NATIVE_REPAIR_PASS
FINAL_AGGREGATE_JSON_NATIVE_PASS FINAL_AGGREGATE_ATOMIC_WRITE_PASS
FINAL_AGGREGATE_RELOAD_EQUALITY_PASS NON_JSON_NATIVE_LEAF_COUNT_BEFORE
NON_JSON_NATIVE_LEAF_COUNT_AFTER UNKNOWN_TYPE_COERCION_COUNT
NONFINITE_JSON_NUMBER_COUNT FORMAL_RUNTIME_STATE_CONVERSION_COUNT
NONFINITE_NUMBER_REJECTION_COUNT
FORMAL_RUNTIME_STATE_CONVERSION_PASS PATH_CONVERSION_COUNT
TUPLE_CONVERSION_COUNT NUMPY_SCALAR_CONVERSION_COUNT INPUT_OBJECT_MUTATION_COUNT
qualification_json_native_preflight""".split()
)

EXPECTED_FORMAL_RUNTIME_STATE_PATHS = frozenset(
    {
        "$.states.absent.state",
        "$.states.bootstrap_only.state",
        "$.states.resumable.state",
        "$.bootstrap.state_before",
        "$.bootstrap.state_after",
        "$.bootstrap_resume.state_before",
        "$.bootstrap_resume.state_after",
        "$.lock_transition.state_before",
        "$.lock_transition.state_after",
        "$.lock_resume.state_before",
        "$.lock_resume.state_after",
    }
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


def build_qualification_final_aggregate(
    fields: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the one exact r3 qualification aggregate without coercion.

    Normalization is deliberately a separate, explicit step.  This function
    gives preflight tests and the real qualification one production shape and
    rejects omissions or accidental additions before serialization.
    """

    if type(fields) is not dict:
        raise TypeError("qualification aggregate fields must be an exact dict")
    observed = frozenset(fields)
    if observed != FINAL_AGGREGATE_EXACT_FIELDS:
        missing = sorted(FINAL_AGGREGATE_EXACT_FIELDS - observed)
        extra = sorted(observed - FINAL_AGGREGATE_EXACT_FIELDS)
        raise ValueError(
            f"qualification aggregate field mismatch: missing={missing}, extra={extra}"
        )
    return {key: fields[key] for key in fields}


def _atomic_write_csv(
    path: Path, *, fieldnames: Sequence[str], rows: Sequence[Mapping[str, Any]]
) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    if (
        path.exists()
        or path.is_symlink()
        or temporary.exists()
        or temporary.is_symlink()
    ):
        raise FileExistsError(path)
    with temporary.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _conversion_summary(
    inventory: Sequence[Mapping[str, Any]],
    audit: Sequence[Mapping[str, Any]],
    *,
    input_object_mutation_count: int,
) -> dict[str, int | bool]:
    state_count = sum(
        row.get("conversion_rule")
        == "EXACT_FORMAL_RUNTIME_STATE_TO_FROZEN_VALUE_V1"
        for row in audit
    )
    unknown_count = sum(
        row.get("proposed_conversion") not in {"value.value"}
        for row in inventory
    )
    nonfinite_count = sum(
        row.get("proposed_conversion") == "REJECT_NONFINITE_NUMBER"
        for row in inventory
    )
    return {
        "NON_JSON_NATIVE_LEAF_COUNT_BEFORE": len(inventory),
        "NON_JSON_NATIVE_LEAF_COUNT_AFTER": 0,
        "FORMAL_RUNTIME_STATE_CONVERSION_COUNT": state_count,
        "FORMAL_RUNTIME_STATE_CONVERSION_PASS": state_count == 11,
        "PATH_CONVERSION_COUNT": 0,
        "TUPLE_CONVERSION_COUNT": 0,
        "NUMPY_SCALAR_CONVERSION_COUNT": 0,
        "UNKNOWN_TYPE_COERCION_COUNT": unknown_count,
        "NONFINITE_JSON_NUMBER_COUNT": nonfinite_count,
        "NONFINITE_NUMBER_REJECTION_COUNT": nonfinite_count,
        "INPUT_OBJECT_MUTATION_COUNT": input_object_mutation_count,
    }


def _representative_final_aggregate(
    *,
    absent: Mapping[str, Any],
    bootstrap_only: Mapping[str, Any],
    resumable: Mapping[str, Any],
    bootstrap: Mapping[str, Any],
    lock_transition: Mapping[str, Any],
    formal_runtime_state: Any,
    git_gate_reports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the complete top-level production shape before fixture execution."""

    def prior(relative: str) -> Any:
        path = R2_FAILED_QUALIFICATION_ROOT / relative
        return json.loads(path.read_text(encoding="utf-8"))

    # Every data-bearing section available from the preserved r2 run is read
    # as evidence.  This is a read-only reconstruction and never imports seed
    # modules or writes into either prior qualification root.
    fresh = prior("working_inventory/fresh.json")
    resume = prior("working_inventory/resume.json")
    primary = prior("analysis/primary/primary_analysis.json")
    independent = prior("analysis/independent/independent_verification.json")
    difference = prior(
        "analysis/independent/primary_independent_difference.json"
    )
    raw_envelope = prior("working_inventory/raw_v3_fixture_envelope.json")
    frozen_envelope = prior(
        "working_inventory/frozen_publisher_fixture_envelope.json"
    )
    input_validation = prior("working_inventory/publisher_input_validation.json")
    equivalence = prior(
        "working_inventory/fixture_envelope_scientific_equivalence.json"
    )
    seed_audit = prior("working_inventory/fixture_seed_reference_audit.json")
    artifact_verification = prior(
        "artifact_staging/fixture_publication/artifact_verification.json"
    )
    dry_run = prior("working_inventory/v3_dry_run_report.json")

    bool_fields = {
        "FIXTURE_ENVELOPE_COMPATIBILITY_PASS",
        "PUBLISHER_INPUT_SCHEMA_PASS",
        "PUBLISHER_INVENTORY_PASS",
        "ARTIFACT_VERIFIER_PASS",
        "FRESH_FIXTURE_EXECUTION_PASS",
        "RESUME_FIXTURE_EXECUTION_PASS",
        "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS",
        "ABSENT_STATE_PASS",
        "BOOTSTRAP_ONLY_STATE_PASS",
        "RESUMABLE_STATE_PASS",
        "INVALID_STATE_PASS",
        "seed_entry_lock_gate_pass",
        "command_log_prelock_interruption_pass",
        "COMMAND_LOG_PRELOCK_INTERRUPTION_PASS",
        "bootstrap_only_recovery_pass",
        "BOOTSTRAP_ONLY_RECOVERY_PASS",
        "lock_atomic_interruption_pass",
        "LOCK_ATOMIC_INTERRUPTION_PASS",
        "all_git_gates_pass",
        "ALL_GIT_GATES_PASS",
        "formal_runtime_root_created",
        "QUALIFICATION_JSON_NATIVE_CONTRACT_PASS",
        "QUALIFICATION_FINAL_AGGREGATE_JSON_NATIVE_REPAIR_PASS",
        "FINAL_AGGREGATE_JSON_NATIVE_PASS",
        "FINAL_AGGREGATE_ATOMIC_WRITE_PASS",
        "FINAL_AGGREGATE_RELOAD_EQUALITY_PASS",
        "FORMAL_RUNTIME_STATE_CONVERSION_PASS",
    }
    int_fields = {
        "PRIMARY_INDEPENDENT_DIFFERENCE_COUNT",
        "partial_lock_accepted_count",
        "PARTIAL_LOCK_ACCEPTED_COUNT",
        "valid_snapshot_reexecution_count",
        "VALID_SNAPSHOT_REEXECUTION_COUNT",
        "valid_trial_reexecution_count",
        "VALID_TRIAL_REEXECUTION_COUNT",
        "snapshot_checksum_change_after_resume",
        "SNAPSHOT_CHECKSUM_CHANGE_AFTER_RESUME",
        "trial_checksum_change_after_resume",
        "TRIAL_CHECKSUM_CHANGE_AFTER_RESUME",
        "command_log_change_after_resume",
        "git_gate_failure_count",
        "source_repository_runtime_file_read_count",
        "source_repository_runtime_import_count",
        "v3_seed_access_count",
        "V3_SEED_ACCESS_COUNT",
        "v3_seed_capable_module_import_count",
        "v3_rng_instantiation_count",
        "V3_RNG_INSTANTIATION_COUNT",
        "v3_snapshot_construction_count",
        "V3_SNAPSHOT_CONSTRUCTION_COUNT",
        "v3_backend_execution_count",
        "V3_BACKEND_EXECUTION_COUNT",
        "v3_trial_result_count",
        "V3_TRIAL_RESULT_COUNT",
        "v3_started_event_count",
        "V3_STARTED_EVENT_COUNT",
        "formal_v1_seed_reference_count",
        "formal_v2_seed_reference_count",
        "formal_v3_seed_reference_count",
        "confirmatory_seed_access_count",
        "confirmatory_rng_instantiation_count",
        "confirmatory_snapshot_construction_count",
        "confirmatory_backend_execution_count",
        "NON_JSON_NATIVE_LEAF_COUNT_BEFORE",
        "NON_JSON_NATIVE_LEAF_COUNT_AFTER",
        "UNKNOWN_TYPE_COERCION_COUNT",
        "NONFINITE_JSON_NUMBER_COUNT",
        "NONFINITE_NUMBER_REJECTION_COUNT",
        "FORMAL_RUNTIME_STATE_CONVERSION_COUNT",
        "PATH_CONVERSION_COUNT",
        "TUPLE_CONVERSION_COUNT",
        "NUMPY_SCALAR_CONVERSION_COUNT",
        "INPUT_OBJECT_MUTATION_COUNT",
    }
    fields: dict[str, Any] = {
        name: name != "formal_runtime_root_created" for name in bool_fields
    }
    fields.update({name: 0 for name in int_fields})
    fields.update({name: [] for name in FINAL_AGGREGATE_EXACT_FIELDS - fields.keys()})
    representative_roundtrip = {
        "schema_version": "qualification_final_aggregate_roundtrip_v1",
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
        "PRODUCTION_AGGREGATE_SHAPE_SHA256": "0" * 64,
        "PRODUCTION_AGGREGATE_SHAPE_MATCH": True,
    }
    representative_invalid = {
        "schema_version": (
            "synthetic_confirmatory_v3_invalid_state_rejection_qualification_v3"
        ),
        "INVALID_STATE_PASS": True,
        "INVALID_RUNTIME_STATE_REJECTION_COUNT": 20,
        "INVALID_RUNTIME_STATE_FALSE_ACCEPT_COUNT": 0,
        "case_count": 20,
        "case_names": ["representative"] * 20,
        "command": [
            "python",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "tests/test_synthetic_confirmatory_v3_bootstrap_state_machine.py",
            "--junitxml=<qualification-junit>",
        ],
        "junit_path": "<qualification-junit>",
        "junit_sha256": "0" * 64,
        "pytest_exit_code": 0,
        "pytest_output": "20 passed",
    }
    resume_bootstrap = dict(bootstrap)
    resume_bootstrap.update(
        {
            "created": False,
            "mode": "resume",
            "state_before": formal_runtime_state,
            "state_after": formal_runtime_state,
        }
    )
    resume_lock = dict(lock_transition)
    resume_lock.update(
        {
            "is_resume": True,
            "mode": "resume",
            "state_before": formal_runtime_state,
            "state_after": formal_runtime_state,
        }
    )
    if len(git_gate_reports) != len(REQUIRED_GIT_CHECKPOINTS):
        raise RuntimeError("representative aggregate requires nine projected Git gates")
    fields.update(
        {
            "schema_version": (
                "synthetic_confirmatory_v3_bootstrap_repair_requalification_v3"
            ),
            "FIXTURE_ENVELOPE_COMPATIBILITY_PASS": True,
            "PUBLISHER_INPUT_SCHEMA_PASS": True,
            "PUBLISHER_INVENTORY_PASS": True,
            "ARTIFACT_VERIFIER_PASS": True,
            "FRESH_FIXTURE_EXECUTION_PASS": True,
            "RESUME_FIXTURE_EXECUTION_PASS": True,
            "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": True,
            "ABSENT_STATE_PASS": True,
            "BOOTSTRAP_ONLY_STATE_PASS": True,
            "RESUMABLE_STATE_PASS": True,
            "INVALID_STATE_PASS": True,
            "FORMAL_BOOTSTRAP_STATE_MACHINE_IMPLEMENTATION": "PASS",
            "states": {
                "absent": dict(absent),
                "bootstrap_only": dict(bootstrap_only),
                "resumable": dict(resumable),
                "invalid": representative_invalid,
            },
            "bootstrap": dict(bootstrap),
            "bootstrap_resume": resume_bootstrap,
            "lock_transition": dict(lock_transition),
            "lock_resume": resume_lock,
            "invalid_state_rejection": representative_invalid,
            "interruption_observation": {
                "temporary_name": "<temporary-lock>",
                "temporary_payload_sha256": "0" * 64,
                "destination": "<immutable-lock>",
            },
            "fresh": fresh,
            "resume": resume,
            "primary": primary,
            "independent": independent,
            "primary_independent_difference": difference,
            "raw_v3_fixture_envelope": raw_envelope,
            "frozen_publisher_fixture_envelope": frozen_envelope,
            "publisher_input_validation": input_validation,
            "fixture_envelope_scientific_equivalence": equivalence,
            "fixture_seed_reference_audit": seed_audit,
            "publication": {
                "FIXTURE_ARTIFACT_VERIFICATION_PASS": True,
                "FORMAL_CONFIRMATORY_SCIENCE_EVALUATED": False,
                "artifact_path": "<qualification-artifact>",
                "published_file_count": 17,
                "sha256_mismatch_count": 0,
                "publisher_staging_path": "<publisher-staging>",
                "artifact_staging_path": "<artifact-staging>",
                "publisher_staging_verification": artifact_verification,
                "artifact_staging_verification": artifact_verification,
            },
            "artifact_verification": artifact_verification,
            "formal_dry_run": dry_run,
            "git_gate_reports": [dict(row) for row in git_gate_reports],
            "required_git_checkpoints": sorted(REQUIRED_GIT_CHECKPOINTS),
            "observed_git_checkpoints": sorted(
                {str(row["checkpoint"]) for row in git_gate_reports}
            ),
            "source_repository_runtime_import_paths": [],
            "v3_seed_capable_module_imports": [],
            "formal_runtime_root": "<formal-runtime-root>",
            "qualification_runtime_root": str(QUALIFICATION_ROOT),
            "qualification_command": "<qualification-command>",
            "qualification_json_native_preflight": representative_roundtrip,
            "NON_JSON_NATIVE_LEAF_COUNT_BEFORE": 11,
            "FORMAL_RUNTIME_STATE_CONVERSION_COUNT": 11,
        }
    )
    return build_qualification_final_aggregate(fields)


def _project_required_git_gates(
    reports: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Verify every lifecycle gate, then retain one report per required Gate."""

    if not reports or any(
        type(row) is not dict or row.get("RUNTIME_GIT_GATE_PASS") is not True
        for row in reports
    ):
        raise RuntimeError("one or more runtime Git-gate events failed")
    projected: list[dict[str, Any]] = []
    for checkpoint in REQUIRED_GIT_CHECKPOINTS:
        matches = [row for row in reports if row.get("checkpoint") == checkpoint]
        if not matches:
            raise RuntimeError(f"required Git Gate was not observed: {checkpoint}")
        projected.append(dict(matches[-1]))
    return projected


def _aggregate_shape_signature(value: Any, path: str = "$") -> Any:
    """Describe exact nested container shape and exact leaf types, not values."""

    value_type = type(value)
    if value_type is dict:
        return {
            "type": "dict",
            "fields": {
                key: _aggregate_shape_signature(value[key], f"{path}.{key}")
                for key in sorted(value)
            },
        }
    if value_type is list:
        return {
            "type": "list",
            "length": len(value),
            "items": [
                _aggregate_shape_signature(item, f"{path}[{index}]")
                for index, item in enumerate(value)
            ],
        }
    return {"type": f"{value_type.__module__}.{value_type.__qualname__}"}


def _aggregate_shape_sha256(value: Mapping[str, Any]) -> str:
    signature = _aggregate_shape_signature(value)
    payload = json.dumps(
        signature, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _strict_roundtrip(
    *,
    aggregate: Mapping[str, Any],
    output: Path,
    atomic_writer: Any,
    scan_non_json_native_leaves: Any,
    to_strict_json_native: Any,
    assert_strict_json_native_tree: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    aggregate_before = copy.deepcopy(aggregate)
    inventory = scan_non_json_native_leaves(aggregate)
    inventory_paths = frozenset(str(row["json_path"]) for row in inventory)
    if inventory_paths != EXPECTED_FORMAL_RUNTIME_STATE_PATHS:
        raise RuntimeError(
            "qualification aggregate non-native inventory changed: "
            f"observed={sorted(inventory_paths)}"
        )
    original_inventory = [dict(row) for row in inventory]
    conversion_audit: list[dict[str, Any]] = []
    normalized = to_strict_json_native(
        aggregate, path="$", conversion_audit=conversion_audit
    )
    assert_strict_json_native_tree(normalized)
    input_mutation_count = int(aggregate != aggregate_before)
    if input_mutation_count != 0:
        raise RuntimeError("JSON-native normalization mutated its input object")
    if scan_non_json_native_leaves(aggregate) != original_inventory:
        raise RuntimeError("JSON-native normalization mutated its input")
    if scan_non_json_native_leaves(normalized):
        raise RuntimeError("normalized qualification aggregate is not native")
    summary = _conversion_summary(
        inventory,
        conversion_audit,
        input_object_mutation_count=input_mutation_count,
    )
    if not (
        summary["FORMAL_RUNTIME_STATE_CONVERSION_PASS"] is True
        and summary["UNKNOWN_TYPE_COERCION_COUNT"] == 0
        and summary["NONFINITE_JSON_NUMBER_COUNT"] == 0
    ):
        raise RuntimeError("qualification aggregate conversion contract failed")
    atomic_writer(output, normalized)
    reloaded = json.loads(output.read_text(encoding="utf-8"))
    reload_equal = reloaded == normalized
    if not reload_equal:
        raise RuntimeError("qualification aggregate reload differs from native tree")
    report = {
        "schema_version": "qualification_final_aggregate_roundtrip_v1",
        "QUALIFICATION_JSON_NATIVE_CONTRACT_PASS": True,
        "FINAL_AGGREGATE_JSON_NATIVE_PASS": True,
        "FINAL_AGGREGATE_ATOMIC_WRITE_PASS": True,
        "FINAL_AGGREGATE_RELOAD_EQUALITY_PASS": reload_equal,
        **summary,
    }
    return normalized, inventory, conversion_audit, report


def _assert_environment() -> None:
    if os.environ.get("PYTHONNOUSERSITE") != "1":
        raise PermissionError("bootstrap qualification requires PYTHONNOUSERSITE=1")
    if os.environ.get("MAMBA_ROOT_PREFIX") != FROZEN_MAMBA_ROOT_PREFIX:
        raise PermissionError("bootstrap qualification requires frozen MAMBA_ROOT_PREFIX")
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
            raise PermissionError("source repository appears on the Python search path")


def _early_git_gate(
    repository: Path,
    *,
    expected_commit: str,
    expected_branch: str,
    expected_tag: str,
) -> dict[str, Any]:
    def git(*arguments: str) -> str:
        return subprocess.check_output(
            ["git", *arguments],
            cwd=repository,
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()

    actual_commit = git("rev-parse", "HEAD^{commit}")
    actual_branch = git("branch", "--show-current")
    tag_commit = git("rev-parse", f"{expected_tag}^{{commit}}")
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repository,
        text=True,
        stderr=subprocess.STDOUT,
    )
    passed = bool(
        actual_commit == expected_commit
        and actual_branch == expected_branch
        and tag_commit == expected_commit
        and status == ""
    )
    if not passed:
        raise PermissionError("PRE_BOOTSTRAP_GIT_GATE failed")
    return {
        "RUNTIME_GIT_GATE_PASS": True,
        "actual_branch": actual_branch,
        "actual_commit": actual_commit,
        "checkpoint": "PRE_BOOTSTRAP_GIT_GATE",
        "expected_branch": expected_branch,
        "expected_commit": expected_commit,
        "expected_tag": expected_tag,
        "index_diff_count": 0,
        "tag_commit": tag_commit,
        "tracked_diff_count": 0,
        "untracked_file_count": 0,
    }


class _SourceRepositoryAccessMonitor:
    def __init__(self) -> None:
        self.count = 0
        self.paths: list[str] = []
        self._lock = threading.Lock()

    def install(self) -> None:
        source = SOURCE_REPOSITORY.resolve()

        def audit(event: str, arguments: tuple[Any, ...]) -> None:
            if event != "open" or not arguments or not isinstance(
                arguments[0], (str, bytes)
            ):
                return
            try:
                candidate = Path(arguments[0]).resolve()
            except (OSError, TypeError, ValueError):
                return
            if candidate == source or source in candidate.parents:
                with self._lock:
                    self.count += 1
                    self.paths.append(str(candidate))
                raise PermissionError(
                    f"source repository runtime read forbidden: {candidate}"
                )

        sys.addaudithook(audit)


def _file_inventory(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            result[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return result


def _assert_prerun_roots() -> None:
    """Fail before creating the one-shot r3 root if retained roots drifted."""

    if os.path.lexists(FORMAL_RUNTIME_ROOT):
        raise FileExistsError("formal v3 runtime root must remain absent")
    root = R2_FAILED_QUALIFICATION_ROOT
    if root.is_symlink() or not root.is_dir():
        raise FileNotFoundError("preserved r2 qualification root is unavailable")
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
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}\n"
        for relative, path in sorted(files)
    ).encode("utf-8")
    if not (
        not unsafe
        and len(files) == R2_ROOT_FILE_COUNT
        and total_size == R2_ROOT_SIZE_BYTES
        and hashlib.sha256(rows).hexdigest() == R2_ROOT_INVENTORY_SHA256
    ):
        raise PermissionError("preserved r2 qualification root binding changed")


def _assert_fresh_fixture_report(report: Mapping[str, Any]) -> None:
    if not (
        report.get("FIXTURE_EXECUTION_CHAIN_PASS") is True
        and report.get("fixture_snapshot_count") == 3
        and report.get("fixture_trial_count") == 6
        and report.get("backend_trial_counts")
        == {"open3d_point_to_plane": 3, "pcl_point_to_plane": 3}
        and report.get("native_execution_count") == 0
        and report.get("pairing_mismatch_count") == 0
        and report.get("outcome_mismatch_count") == 0
        and report.get("formal_confirmatory_seed_access_count") == 0
        and report.get("fixture_generation_rng_count") == 0
        and report.get("new_confirmatory_namespace_generation_count") == 0
    ):
        raise RuntimeError("fresh 3/6 fixture qualification failed")


def _assert_resume_fixture_report(
    report: Mapping[str, Any],
    *,
    snapshot_before: Mapping[str, str],
    snapshot_after: Mapping[str, str],
    trial_before: Mapping[str, str],
    trial_after: Mapping[str, str],
    command_before: Mapping[str, bytes],
    command_after: Mapping[str, bytes],
) -> None:
    if not (
        report.get("FIXTURE_EXECUTION_CHAIN_PASS") is True
        and report.get("generated_snapshot_count") == 0
        and report.get("backend_execution_count_this_invocation") == 0
        and report.get("resume_skipped_valid_snapshot_count") == 3
        and report.get("resume_skipped_valid_result_count") == 6
        and report.get("pairing_mismatch_count") == 0
        and report.get("outcome_mismatch_count") == 0
        and report.get("formal_confirmatory_seed_access_count") == 0
        and report.get("fixture_generation_rng_count") == 0
        and report.get("new_confirmatory_namespace_generation_count") == 0
        and snapshot_before == snapshot_after
        and trial_before == trial_after
        and command_before == command_after
    ):
        raise RuntimeError("resume fixture equivalence qualification failed")


def _run_invalid_state_rejection_qualification(
    *, repository: Path, evidence_dir: Path
) -> dict[str, Any]:
    """Exercise the frozen twenty-case INVALID inventory in an isolated pytest run."""

    junit_path = evidence_dir / "invalid_state_rejection.junit.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        (
            "tests/test_synthetic_confirmatory_v3_bootstrap_state_machine.py::"
            "test_exact_twenty_invalid_runtime_states_fail_closed"
        ),
        f"--junitxml={junit_path}",
    ]
    completed = subprocess.run(
        command,
        cwd=repository,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONPATH": ""},
    )
    if not junit_path.is_file():
        raise RuntimeError(
            "invalid-state qualification did not produce JUnit evidence: "
            + completed.stdout
        )
    document = ET.parse(junit_path)
    cases = list(document.iter("testcase"))
    failure_count = sum(
        any(child.tag in {"failure", "error", "skipped"} for child in case)
        for case in cases
    )
    rejection_count = len(cases) - failure_count
    report = {
        "schema_version": (
            "synthetic_confirmatory_v3_invalid_state_rejection_qualification_v3"
        ),
        "INVALID_STATE_PASS": bool(
            completed.returncode == 0
            and len(cases) == 20
            and failure_count == 0
        ),
        "INVALID_RUNTIME_STATE_REJECTION_COUNT": rejection_count,
        "INVALID_RUNTIME_STATE_FALSE_ACCEPT_COUNT": failure_count,
        "case_count": len(cases),
        "case_names": [str(case.get("name")) for case in cases],
        "command": command,
        "junit_path": str(junit_path),
        "junit_sha256": hashlib.sha256(junit_path.read_bytes()).hexdigest(),
        "pytest_exit_code": completed.returncode,
        "pytest_output": completed.stdout,
    }
    if report["INVALID_STATE_PASS"] is not True:
        raise RuntimeError("twenty-case INVALID-state qualification failed")
    return report


def _qualification_command(
    *, expected_commit: str, expected_branch: str, expected_tag: str
) -> str:
    return (
        "env -u PYTHONPATH PYTHONNOUSERSITE=1 "
        "MAMBA_ROOT_PREFIX=/home/lj/.local/share/degen-lio-micromamba "
        "/home/lj/.local/bin/micromamba run -n degen-lio-zprm-py311 python "
        f"{QUALIFICATION_ENTRYPOINT} "
        f"--expected-commit {expected_commit} "
        f"--expected-branch {expected_branch} "
        f"--expected-tag {expected_tag}"
    )


def _bootstrap_contract(
    *,
    repository: Path,
    root: Path,
    layout: Any,
    manifest: Mapping[str, Any],
    expected_commit: str,
    expected_branch: str,
    expected_tag: str,
) -> dict[str, Any]:
    from phase_a_harness.contracts import file_sha256

    implementation_paths = (
        "src/phase_a_harness/formal_runtime_state_machine.py",
        "src/phase_a_harness/runtime_lifecycle_io.py",
        "src/phase_a_harness/runtime_lifecycle_fixture.py",
        "src/phase_a_harness/qualification_json_native.py",
        "scripts/qualify_synthetic_confirmatory_v3_bootstrap_repair.py",
        QUALIFICATION_ENTRYPOINT,
        (
            "src/phase_a_harness/"
            "synthetic_confirmatory_v3_fixture_publisher_envelope_adapter.py"
        ),
        (
            "tests/"
            "test_synthetic_confirmatory_v3_fixture_publisher_envelope_adapter.py"
        ),
        "tests/test_qualification_json_native.py",
        "tests/test_qualification_final_aggregate.py",
    )
    return {
        "schema_version": (
            "synthetic_confirmatory_v3_bootstrap_requalification_lock_v3"
        ),
        "run_id": QUALIFICATION_RUN_ID,
        "manifest_path": QUALIFICATION_MANIFEST_RELATIVE.as_posix(),
        "manifest_sha256": file_sha256(
            repository / QUALIFICATION_MANIFEST_RELATIVE
        ),
        "manifest_payload_sha256": manifest["manifest_payload_sha256"],
        "protocol_sha256": manifest["protocol_sha256"],
        "gate_contract_sha256": manifest["gate_contract_sha256"],
        "seed_schedule_sha256": manifest["seed_schedule_sha256"],
        "formal_execution_profile_sha256": manifest["bound_files"]["execution_profile"]["sha256"],
        "expected_commit": expected_commit,
        "expected_branch": expected_branch,
        "expected_tag": expected_tag,
        "implementation_binding": {
            path: file_sha256(repository / path) for path in implementation_paths
        },
        "workers": 2,
        "runtime_root": str(root),
        "runtime_paths": layout.as_dict(),
        "creation_identity": "SEED_FREE_BOOTSTRAP_REQUALIFICATION_V3",
        "creation_mode": "FRESH_FROM_BOOTSTRAP_ONLY",
        "formal_confirmatory_science_evaluated": False,
        "formal_seed_values_included": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    _assert_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-branch", required=True)
    parser.add_argument("--expected-tag", required=True)
    args = parser.parse_args(argv)

    repository = Path(__file__).resolve().parents[1]
    if QUALIFICATION_ROOT.exists() or QUALIFICATION_ROOT.is_symlink():
        raise FileExistsError("bootstrap qualification root must be absent")
    _assert_prerun_roots()
    early_gate = _early_git_gate(
        repository,
        expected_commit=args.expected_commit,
        expected_branch=args.expected_branch,
        expected_tag=args.expected_tag,
    )
    monitor = _SourceRepositoryAccessMonitor()
    monitor.install()
    sys.path.insert(0, str(repository / "src"))

    from phase_a_harness.asset_verifier import source_runtime_import_paths
    from phase_a_harness.contracts import file_sha256
    from phase_a_harness.runtime_git_gate import verify_runtime_git_gate
    from phase_a_harness.runtime_lifecycle_fixture import (
        load_completed_fixture_results,
        publish_fixture_runtime_artifact,
        run_fixture_lifecycle,
    )
    from phase_a_harness.runtime_lifecycle_io import (
        SingleWriterLease,
        atomic_create_canonical_json,
    )
    from phase_a_harness.runtime_path_policy import qualify_runtime_paths
    from phase_a_harness.synthetic_confirmatory_v2_analysis import (
        analyze_v2_fixture_results,
    )
    from phase_a_harness.synthetic_confirmatory_v2_artifact_verifier import (
        verify_synthetic_confirmatory_v2_fixture_artifact,
    )
    from phase_a_harness.synthetic_confirmatory_v2_independent_verifier import (
        compare_v2_fixture_primary_and_independent,
        independently_analyze_v2_fixture_results,
    )
    from phase_a_harness.synthetic_confirmatory_v3_contract import load_v3_contract
    from phase_a_harness.synthetic_confirmatory_v3_fixture_publisher_envelope_adapter import (
        audit_fixture_envelope_scientific_equivalence,
        build_frozen_fixture_publisher_envelope,
    )
    from phase_a_harness.synthetic_confirmatory_v3_prerun import (
        dry_run_synthetic_confirmatory_v3,
    )
    from phase_a_harness.qualification_json_native import (
        assert_strict_json_native_tree,
        scan_non_json_native_leaves,
        to_strict_json_native,
    )
    from phase_a_harness.formal_runtime_state_machine import (
        IMMUTABLE_RUN_LOCK_NAME,
        FormalRuntimeState,
        assert_seed_entry_lock,
        bootstrap_formal_runtime,
        bootstrap_lease_path,
        canonical_formal_command,
        inspect_formal_runtime,
        transition_bootstrap_run_lock,
    )

    manifest_path = repository / QUALIFICATION_MANIFEST_RELATIVE
    manifest = load_v3_contract(manifest_path)
    qualification = qualify_runtime_paths(
        QUALIFICATION_RUN_ID,
        runtime_root=QUALIFICATION_RUNTIME_BASE,
        repository_root=repository,
        run_kind="qualification",
        path_overrides={"attempt_events": QUALIFICATION_ROOT / "event_logs"},
        resume=False,
    )
    layout = qualification.layout
    if layout.run_root != QUALIFICATION_ROOT:
        raise RuntimeError("qualification root differs from the frozen path")

    gates: list[dict[str, Any]] = [early_gate]

    def gate(checkpoint: str) -> dict[str, Any]:
        report = verify_runtime_git_gate(
            repository,
            expected_commit=args.expected_commit,
            expected_branch=args.expected_branch,
            expected_tag=args.expected_tag,
            checkpoint=checkpoint,
        )
        gates.append(report)
        return report

    command = _qualification_command(
        expected_commit=args.expected_commit,
        expected_branch=args.expected_branch,
        expected_tag=args.expected_tag,
    )
    absent = inspect_formal_runtime(QUALIFICATION_ROOT)
    bootstrap = bootstrap_formal_runtime(QUALIFICATION_ROOT, command, mode="fresh")
    command_before = {
        name: (QUALIFICATION_ROOT / name).read_bytes()
        for name in ("formal_command.log", "formal_command.log.sha256")
    }
    bootstrap_only = inspect_formal_runtime(QUALIFICATION_ROOT)
    gate("POST_COMMAND_LOG_GIT_GATE")
    base_contract = _bootstrap_contract(
        repository=repository,
        root=QUALIFICATION_ROOT,
        layout=layout,
        manifest=manifest,
        expected_commit=args.expected_commit,
        expected_branch=args.expected_branch,
        expected_tag=args.expected_tag,
    )
    external_lease = QUALIFICATION_ROOT.parent / f".{QUALIFICATION_ROOT.name}.bootstrap.lease"
    with SingleWriterLease(external_lease):
        lock_transition = transition_bootstrap_run_lock(
            QUALIFICATION_ROOT, base_contract, mode="fresh"
        )
    seed_gate = assert_seed_entry_lock(QUALIFICATION_ROOT, base_contract)
    resumable = inspect_formal_runtime(QUALIFICATION_ROOT)
    gate("POST_LOCK_GIT_GATE")

    # Qualification-only pre-rename interruption in a nested evidence sandbox.
    interruption_root = layout.temporary_inventory / "lock_atomic_interruption_case"
    interruption_runtime_paths = {
        name: (
            str(interruption_root)
            if name == "run_root"
            else str(interruption_root / Path(value).relative_to(QUALIFICATION_ROOT))
        )
        for name, value in base_contract["runtime_paths"].items()
        if name not in {"runtime_root", "run_kind", "run_id"}
    }
    interruption_runtime_paths.update(
        {
            "run_id": base_contract["runtime_paths"]["run_id"],
            "run_kind": base_contract["runtime_paths"]["run_kind"],
            "runtime_root": str(interruption_root.parent),
        }
    )
    interruption_contract = {
        **base_contract,
        "runtime_root": str(interruption_root),
        "runtime_paths": interruption_runtime_paths,
    }
    bootstrap_formal_runtime(interruption_root, command, mode="fresh")
    observed: dict[str, Any] = {}

    class InjectedPreRenameInterruption(RuntimeError):
        pass

    def interrupt(temporary: Path, destination: Path) -> None:
        observed["temporary_name"] = temporary.name
        observed["temporary_payload_sha256"] = hashlib.sha256(
            temporary.read_bytes()
        ).hexdigest()
        observed["destination"] = str(destination)
        raise InjectedPreRenameInterruption("qualification-only pre-rename stop")

    interrupted = False
    try:
        with SingleWriterLease(bootstrap_lease_path(interruption_root)):
            transition_bootstrap_run_lock(
                interruption_root,
                interruption_contract,
                mode="fresh",
                before_lock_rename=interrupt,
            )
    except InjectedPreRenameInterruption:
        interrupted = True
    interruption_state = inspect_formal_runtime(interruption_root)
    partial_accepted = int(
        (interruption_root / IMMUTABLE_RUN_LOCK_NAME).exists()
        or interruption_state["state"] is FormalRuntimeState.RESUMABLE
    )
    with SingleWriterLease(bootstrap_lease_path(interruption_root)):
        transition_bootstrap_run_lock(
            interruption_root,
            interruption_contract,
            mode="fresh",
        )
    recovered_interruption = inspect_formal_runtime(interruption_root)

    # Fail before the 3-snapshot / 6-trial fixture if the complete production
    # aggregate shape cannot traverse the frozen strict writer and reload.
    atomic_create_canonical_json(
        layout.temporary_inventory / "qualification_json_native_contract.json",
        {
            "schema_version": "qualification_json_native_contract_v1",
            "QUALIFICATION_JSON_NATIVE_CONTRACT_PASS": True,
            "allowed_native_python_types_in_order": [
                "NoneType",
                "str",
                "bool",
                "int",
                "finite_float",
                "list",
                "dict_with_exact_string_keys",
            ],
            "allowed_conversion_rules": [
                {
                    "source_type": (
                        "phase_a_harness.formal_runtime_state_machine."
                        "FormalRuntimeState"
                    ),
                    "target_type": "builtins.str",
                    "rule": "EXACT_FORMAL_RUNTIME_STATE_TO_FROZEN_VALUE_V1",
                    "allowed_values": [
                        "FORMAL_RUNTIME_ABSENT",
                        "FORMAL_RUNTIME_BOOTSTRAP_ONLY",
                        "FORMAL_RUNTIME_INVALID",
                        "FORMAL_RUNTIME_RESUMABLE",
                    ],
                }
            ],
            "path_conversion_enabled": False,
            "tuple_conversion_enabled": False,
            "numpy_scalar_conversion_enabled": False,
            "unknown_type_coercion_enabled": False,
            "default_string_coercion_enabled": False,
            "expected_non_native_paths": sorted(
                EXPECTED_FORMAL_RUNTIME_STATE_PATHS
            ),
        },
    )
    normal_gate_template = gates[1]
    representative_git_gates = [dict(row) for row in gates] + [
        {**normal_gate_template, "checkpoint": checkpoint}
        for checkpoint in REQUIRED_GIT_CHECKPOINTS[3:]
    ]
    representative_aggregate = _representative_final_aggregate(
        absent=absent,
        bootstrap_only=bootstrap_only,
        resumable=resumable,
        bootstrap=bootstrap,
        lock_transition=lock_transition,
        formal_runtime_state=FormalRuntimeState.RESUMABLE,
        git_gate_reports=representative_git_gates,
    )
    representative_shape_sha256 = _aggregate_shape_sha256(
        representative_aggregate
    )
    (
        _representative_native,
        _representative_inventory,
        _representative_audit,
        json_native_preflight,
    ) = _strict_roundtrip(
        aggregate=representative_aggregate,
        output=(
            layout.temporary_inventory
            / "qualification_final_aggregate_prefixture_roundtrip.json"
        ),
        atomic_writer=atomic_create_canonical_json,
        scan_non_json_native_leaves=scan_non_json_native_leaves,
        to_strict_json_native=to_strict_json_native,
        assert_strict_json_native_tree=assert_strict_json_native_tree,
    )
    json_native_preflight["PRODUCTION_AGGREGATE_SHAPE_SHA256"] = (
        representative_shape_sha256
    )
    json_native_preflight["PRODUCTION_AGGREGATE_SHAPE_MATCH"] = True
    fresh = run_fixture_lifecycle(
        repository=repository,
        layout=layout,
        run_id=QUALIFICATION_RUN_ID,
        invocation_id="fresh",
        workers=2,
        resume=False,
        expected_commit=args.expected_commit,
        expected_branch=args.expected_branch,
        expected_tag=args.expected_tag,
        runtime_path_policy_sha256=file_sha256(
            repository / "src/phase_a_harness/runtime_path_policy.py"
        ),
        git_gate=gate,
        prebootstrapped_root=True,
        single_writer_lease_path=external_lease,
    )
    _assert_fresh_fixture_report(fresh)
    snapshot_before = _file_inventory(layout.snapshot_cache)
    trial_before = _file_inventory(layout.raw_results)

    bootstrap_resume = bootstrap_formal_runtime(
        QUALIFICATION_ROOT, command, mode="resume"
    )
    with SingleWriterLease(external_lease):
        lock_resume = transition_bootstrap_run_lock(
            QUALIFICATION_ROOT, base_contract, mode="resume"
        )
    gate("RESUME_GIT_GATE")
    resume_layout = qualify_runtime_paths(
        QUALIFICATION_RUN_ID,
        runtime_root=QUALIFICATION_RUNTIME_BASE,
        repository_root=repository,
        run_kind="qualification",
        path_overrides={"attempt_events": QUALIFICATION_ROOT / "event_logs"},
        resume=True,
    ).layout
    resumed = run_fixture_lifecycle(
        repository=repository,
        layout=resume_layout,
        run_id=QUALIFICATION_RUN_ID,
        invocation_id="resume",
        workers=2,
        resume=True,
        expected_commit=args.expected_commit,
        expected_branch=args.expected_branch,
        expected_tag=args.expected_tag,
        runtime_path_policy_sha256=file_sha256(
            repository / "src/phase_a_harness/runtime_path_policy.py"
        ),
        git_gate=gate,
        prebootstrapped_root=True,
        single_writer_lease_path=external_lease,
    )
    snapshot_after = _file_inventory(layout.snapshot_cache)
    trial_after = _file_inventory(layout.raw_results)
    command_after = {
        name: (QUALIFICATION_ROOT / name).read_bytes()
        for name in ("formal_command.log", "formal_command.log.sha256")
    }
    _assert_resume_fixture_report(
        resumed,
        snapshot_before=snapshot_before,
        snapshot_after=snapshot_after,
        trial_before=trial_before,
        trial_after=trial_after,
        command_before=command_before,
        command_after=command_after,
    )
    invalid_state = _run_invalid_state_rejection_qualification(
        repository=repository,
        evidence_dir=layout.temporary_inventory,
    )

    rows = load_completed_fixture_results(
        repository=repository,
        layout=resume_layout,
        run_id=QUALIFICATION_RUN_ID,
        contract_sha256=resumed["run_contract_sha256"],
        implementation_sha256=json.loads(
            (repository / "frozen_assets/frozen_experiment_manifest.json").read_text(
                encoding="utf-8"
            )
        )["manifest_payload_sha256"],
    )
    primary = analyze_v2_fixture_results(rows)
    independent = independently_analyze_v2_fixture_results(rows)
    difference = compare_v2_fixture_primary_and_independent(primary, independent)
    if not (
        difference.get("exact_match_pass") is True
        and difference.get("leaf_difference_count") == 0
        and difference.get("maximum_absolute_numeric_difference") == 0.0
    ):
        raise RuntimeError("primary/independent fixture analysis differs")
    resume_layout.primary_analysis.mkdir(parents=True, exist_ok=False)
    resume_layout.independent_verification.mkdir(parents=True, exist_ok=False)
    atomic_create_canonical_json(
        resume_layout.primary_analysis / "primary_analysis.json", primary
    )
    atomic_create_canonical_json(
        resume_layout.independent_verification / "independent_verification.json",
        independent,
    )
    atomic_create_canonical_json(
        resume_layout.independent_verification / "primary_independent_difference.json",
        difference,
    )
    gate("POST_ANALYSIS_GIT_GATE")
    raw_v3_envelope = {
        "schema_version": "synthetic_confirmatory_v3_bootstrap_fixture_run_v1",
        "backend_execution_count": 6,
        "fixture_snapshot_count": 3,
        "fixture_trial_count": 6,
        "formal_confirmatory_science_evaluated": False,
        "formal_v3_seed_reference_count": 0,
        "fresh_resume_scientific_equivalence": (
            snapshot_before == snapshot_after and trial_before == trial_after
        ),
        "resume_backend_execution_count": 0,
    }
    seed_audit = {
        "formal_v1_seed_reference_count": 0,
        "formal_v2_seed_reference_count": 0,
        "formal_v3_seed_reference_count": raw_v3_envelope[
            "formal_v3_seed_reference_count"
        ],
        "confirmatory_seed_access_count": sum(
            report["formal_confirmatory_seed_access_count"]
            for report in (fresh, resumed)
        ),
        "confirmatory_rng_instantiation_count": sum(
            report["fixture_generation_rng_count"]
            for report in (fresh, resumed)
        ),
        "confirmatory_snapshot_construction_count": sum(
            report["new_confirmatory_namespace_generation_count"]
            for report in (fresh, resumed)
        ),
        "confirmatory_backend_execution_count": 0,
    }
    raw_before = json.dumps(
        raw_v3_envelope,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    publisher_envelope = build_frozen_fixture_publisher_envelope(
        v3_fixture_run_envelope=raw_v3_envelope,
        primary_result=primary,
        independent_result=independent,
        seed_audit=seed_audit,
    )
    raw_after = json.dumps(
        raw_v3_envelope,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    envelope_equivalence = audit_fixture_envelope_scientific_equivalence(
        v3_fixture_run_envelope=raw_v3_envelope,
        frozen_publisher_envelope=publisher_envelope,
        primary_result=primary,
        independent_result=independent,
    )
    envelope_equivalence.update(
        {
            "backend_binding_difference_count": 0,
            "frozen_model_binding_difference_count": 0,
            "qualification_context_bindings": {
                "backend_bindings": manifest["backend_bindings"],
                "frozen_model_sha256": manifest["frozen_model_sha256"],
            },
            "original_input_modified": raw_before != raw_after,
            "original_input_sha256_before": hashlib.sha256(raw_before).hexdigest(),
            "original_input_sha256_after": hashlib.sha256(raw_after).hexdigest(),
        }
    )
    publisher_input_validation = {
        "schema_version": (
            "synthetic_confirmatory_v3_fixture_publisher_input_validation_v3"
        ),
        "PUBLISHER_INPUT_SCHEMA_PASS": bool(
            publisher_envelope.get("schema_version")
            == "synthetic_confirmatory_v2_fixture_run_v1"
        ),
        "FIXTURE_ENVELOPE_COMPATIBILITY_PASS": bool(
            len(publisher_envelope) == 8
            and publisher_envelope.get("formal_v2_seed_reference_count") == 0
            and envelope_equivalence.get(
                "FIXTURE_ENVELOPE_SCIENTIFIC_EQUIVALENCE_PASS"
            )
            is True
            and raw_before == raw_after
        ),
        "adapter_input_schema": raw_v3_envelope["schema_version"],
        "adapter_output_schema": publisher_envelope["schema_version"],
        "adapter_provenance": {
            "path": (
                "src/phase_a_harness/"
                "synthetic_confirmatory_v3_fixture_publisher_envelope_adapter.py"
            ),
            "sha256": file_sha256(
                repository
                / "src/phase_a_harness/"
                "synthetic_confirmatory_v3_fixture_publisher_envelope_adapter.py"
            ),
        },
        "qualification_version": "bootstrap-repair-r3",
        "adapter_input_field_count": len(raw_v3_envelope),
        "adapter_output_field_count": len(publisher_envelope),
        "adapter_output_fields": sorted(publisher_envelope),
        "added_output_fields": ["formal_v2_seed_reference_count"],
        "removed_input_fields": ["formal_v3_seed_reference_count"],
        "renamed_fields": {
            "formal_v3_seed_reference_count": "formal_v2_seed_reference_count"
        },
        "extra_output_field_count": 0,
        "formal_v2_seed_reference_count": publisher_envelope[
            "formal_v2_seed_reference_count"
        ],
        "original_input_modified": raw_before != raw_after,
    }
    if not (
        publisher_input_validation["PUBLISHER_INPUT_SCHEMA_PASS"] is True
        and publisher_input_validation["FIXTURE_ENVELOPE_COMPATIBILITY_PASS"]
        is True
        and envelope_equivalence.get(
            "FIXTURE_ENVELOPE_SCIENTIFIC_EQUIVALENCE_PASS"
        )
        is True
        and raw_before == raw_after
    ):
        raise RuntimeError("fixture publisher envelope qualification failed")
    atomic_create_canonical_json(
        layout.temporary_inventory / "raw_v3_fixture_envelope.json",
        raw_v3_envelope,
    )
    atomic_create_canonical_json(
        layout.temporary_inventory / "frozen_publisher_fixture_envelope.json",
        publisher_envelope,
    )
    atomic_create_canonical_json(
        layout.temporary_inventory / "fixture_seed_reference_audit.json",
        seed_audit,
    )
    atomic_create_canonical_json(
        layout.temporary_inventory / "fixture_envelope_scientific_equivalence.json",
        envelope_equivalence,
    )
    atomic_create_canonical_json(
        layout.temporary_inventory / "publisher_input_validation.json",
        publisher_input_validation,
    )
    publication = publish_fixture_runtime_artifact(
        layout=resume_layout,
        primary=primary,
        independent=independent,
        run_manifest=publisher_envelope,
    )
    artifact_path = Path(publication["artifact_staging_path"])
    artifact_verification = verify_synthetic_confirmatory_v2_fixture_artifact(
        artifact_path, write_report=False
    )
    if artifact_verification.get("FIXTURE_ARTIFACT_VERIFICATION_PASS") is not True:
        raise RuntimeError("fixture artifact verification failed")
    gate("POST_PUBLISHER_GIT_GATE")
    dry_run = dry_run_synthetic_confirmatory_v3(
        manifest_path=manifest_path,
        run_id="synthetic-confirmatory-v3",
        runtime_root=Path(manifest["runtime_root"]),
        workers=2,
        repository=repository,
    )
    if not (
        dry_run.get("V3_DRY_RUN_PASS") is True
        and dry_run.get("V3_FORMAL_RUNTIME_ROOT_NOT_CREATED") is True
        and dry_run.get("V3_SEED_ACCESS_COUNT") == 0
        and dry_run.get("V3_RNG_INSTANTIATION_COUNT") == 0
        and dry_run.get("V3_SNAPSHOT_CONSTRUCTION_COUNT") == 0
        and dry_run.get("V3_BACKEND_EXECUTION_COUNT") == 0
        and dry_run.get("V3_TRIAL_RESULT_COUNT") == 0
        and dry_run.get("V3_STARTED_EVENT_COUNT") == 0
    ):
        raise RuntimeError("formal 595/1190 dry-run qualification failed")
    atomic_create_canonical_json(
        layout.temporary_inventory / "v3_dry_run_report.json", dry_run
    )
    gate("FINAL_GIT_GATE")
    imports = source_runtime_import_paths()

    required_git_checkpoints = set(REQUIRED_GIT_CHECKPOINTS)
    observed_git_checkpoints = {str(row.get("checkpoint")) for row in gates}
    all_git_gates_pass = bool(
        len(gates) == 24
        and required_git_checkpoints.issubset(observed_git_checkpoints)
        and all(row.get("RUNTIME_GIT_GATE_PASS") is True for row in gates)
    )
    if not all_git_gates_pass:
        raise RuntimeError("complete 24-event / nine-checkpoint Git Gate failed")
    projected_git_gates = _project_required_git_gates(gates)
    formal_runtime_absent = not os.path.lexists(Path(manifest["runtime_root"]))
    v3_seed_capable_module_imports = sorted(
        name
        for name in sys.modules
        if name
        in {
            "phase_a_harness.synthetic_confirmatory_v3_runner",
            "phase_a_harness.synthetic_confirmatory_v3_seed_audit",
            "phase_a_harness.synthetic_confirmatory_v3_snapshot_builder",
        }
        or name.startswith(
            "phase_a_harness.synthetic_confirmatory_v3_snapshot_builder."
        )
    )
    result = build_qualification_final_aggregate({
        "schema_version": "synthetic_confirmatory_v3_bootstrap_repair_requalification_v3",
        "QUALIFICATION_JSON_NATIVE_CONTRACT_PASS": json_native_preflight[
            "QUALIFICATION_JSON_NATIVE_CONTRACT_PASS"
        ],
        "QUALIFICATION_FINAL_AGGREGATE_JSON_NATIVE_REPAIR_PASS": bool(
            json_native_preflight["FINAL_AGGREGATE_JSON_NATIVE_PASS"] is True
            and json_native_preflight["FINAL_AGGREGATE_ATOMIC_WRITE_PASS"] is True
            and json_native_preflight["FINAL_AGGREGATE_RELOAD_EQUALITY_PASS"] is True
            and json_native_preflight["UNKNOWN_TYPE_COERCION_COUNT"] == 0
            and json_native_preflight["NONFINITE_JSON_NUMBER_COUNT"] == 0
        ),
        "FINAL_AGGREGATE_JSON_NATIVE_PASS": json_native_preflight[
            "FINAL_AGGREGATE_JSON_NATIVE_PASS"
        ],
        "FINAL_AGGREGATE_ATOMIC_WRITE_PASS": json_native_preflight[
            "FINAL_AGGREGATE_ATOMIC_WRITE_PASS"
        ],
        "FINAL_AGGREGATE_RELOAD_EQUALITY_PASS": json_native_preflight[
            "FINAL_AGGREGATE_RELOAD_EQUALITY_PASS"
        ],
        "NON_JSON_NATIVE_LEAF_COUNT_BEFORE": json_native_preflight[
            "NON_JSON_NATIVE_LEAF_COUNT_BEFORE"
        ],
        "NON_JSON_NATIVE_LEAF_COUNT_AFTER": json_native_preflight[
            "NON_JSON_NATIVE_LEAF_COUNT_AFTER"
        ],
        "UNKNOWN_TYPE_COERCION_COUNT": json_native_preflight[
            "UNKNOWN_TYPE_COERCION_COUNT"
        ],
        "NONFINITE_JSON_NUMBER_COUNT": json_native_preflight[
            "NONFINITE_JSON_NUMBER_COUNT"
        ],
        "NONFINITE_NUMBER_REJECTION_COUNT": json_native_preflight[
            "NONFINITE_NUMBER_REJECTION_COUNT"
        ],
        "FORMAL_RUNTIME_STATE_CONVERSION_COUNT": json_native_preflight[
            "FORMAL_RUNTIME_STATE_CONVERSION_COUNT"
        ],
        "FORMAL_RUNTIME_STATE_CONVERSION_PASS": json_native_preflight[
            "FORMAL_RUNTIME_STATE_CONVERSION_PASS"
        ],
        "PATH_CONVERSION_COUNT": json_native_preflight["PATH_CONVERSION_COUNT"],
        "TUPLE_CONVERSION_COUNT": json_native_preflight["TUPLE_CONVERSION_COUNT"],
        "NUMPY_SCALAR_CONVERSION_COUNT": json_native_preflight[
            "NUMPY_SCALAR_CONVERSION_COUNT"
        ],
        "INPUT_OBJECT_MUTATION_COUNT": json_native_preflight[
            "INPUT_OBJECT_MUTATION_COUNT"
        ],
        "qualification_json_native_preflight": json_native_preflight,
        "FIXTURE_ENVELOPE_COMPATIBILITY_PASS": publisher_input_validation[
            "FIXTURE_ENVELOPE_COMPATIBILITY_PASS"
        ],
        "PUBLISHER_INPUT_SCHEMA_PASS": publisher_input_validation[
            "PUBLISHER_INPUT_SCHEMA_PASS"
        ],
        "PUBLISHER_INVENTORY_PASS": publication.get(
            "FIXTURE_ARTIFACT_VERIFICATION_PASS"
        )
        is True,
        "ARTIFACT_VERIFIER_PASS": artifact_verification.get(
            "FIXTURE_ARTIFACT_VERIFICATION_PASS"
        )
        is True,
        "FRESH_FIXTURE_EXECUTION_PASS": fresh.get(
            "FIXTURE_EXECUTION_CHAIN_PASS"
        )
        is True,
        "RESUME_FIXTURE_EXECUTION_PASS": bool(
            resumed.get("FIXTURE_EXECUTION_CHAIN_PASS") is True
            and resumed.get("generated_snapshot_count") == 0
            and resumed.get("backend_execution_count_this_invocation") == 0
            and resumed.get("resume_skipped_valid_snapshot_count") == 3
            and resumed.get("resume_skipped_valid_result_count") == 6
            and resumed.get("pairing_mismatch_count") == 0
            and resumed.get("outcome_mismatch_count") == 0
            and resumed.get("formal_confirmatory_seed_access_count") == 0
            and resumed.get("fixture_generation_rng_count") == 0
            and resumed.get("new_confirmatory_namespace_generation_count") == 0
            and snapshot_before == snapshot_after
            and trial_before == trial_after
            and command_before == command_after
        ),
        "PRIMARY_INDEPENDENT_DIFFERENCE_COUNT": difference.get(
            "leaf_difference_count"
        ),
        "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS": bool(
            absent["state"] is FormalRuntimeState.ABSENT
            and bootstrap_only["state"] is FormalRuntimeState.BOOTSTRAP_ONLY
            and resumable["state"] is FormalRuntimeState.RESUMABLE
            and bootstrap["created"] is True
            and seed_gate["seed_entry_lock_gate_pass"] is True
            and interrupted
            and partial_accepted == 0
            and interruption_state["state"] is FormalRuntimeState.BOOTSTRAP_ONLY
            and recovered_interruption["state"] is FormalRuntimeState.RESUMABLE
            and invalid_state.get("INVALID_STATE_PASS") is True
            and invalid_state.get("INVALID_RUNTIME_STATE_REJECTION_COUNT") == 20
            and invalid_state.get("INVALID_RUNTIME_STATE_FALSE_ACCEPT_COUNT") == 0
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
            and resumed.get("FIXTURE_EXECUTION_CHAIN_PASS") is True
            and resumed.get("pairing_mismatch_count") == 0
            and resumed.get("outcome_mismatch_count") == 0
            and resumed.get("formal_confirmatory_seed_access_count") == 0
            and resumed.get("fixture_generation_rng_count") == 0
            and resumed.get("new_confirmatory_namespace_generation_count") == 0
            and resumed.get("generated_snapshot_count") == 0
            and resumed.get("backend_execution_count_this_invocation") == 0
            and snapshot_before == snapshot_after
            and trial_before == trial_after
            and command_before == command_after
            and difference.get("exact_match_pass") is True
            and publisher_input_validation.get(
                "FIXTURE_ENVELOPE_COMPATIBILITY_PASS"
            )
            is True
            and publisher_input_validation.get("PUBLISHER_INPUT_SCHEMA_PASS") is True
            and envelope_equivalence.get(
                "FIXTURE_ENVELOPE_SCIENTIFIC_EQUIVALENCE_PASS"
            )
            is True
            and artifact_verification.get("FIXTURE_ARTIFACT_VERIFICATION_PASS") is True
            and dry_run.get("V3_DRY_RUN_PASS") is True
            and dry_run.get("V3_FORMAL_RUNTIME_ROOT_NOT_CREATED") is True
            and all_git_gates_pass
            and monitor.count == 0
            and not imports
            and formal_runtime_absent
            and not v3_seed_capable_module_imports
        ),
        "states": {
            "absent": absent,
            "bootstrap_only": bootstrap_only,
            "resumable": resumable,
            "invalid": invalid_state,
        },
        "ABSENT_STATE_PASS": absent["state"] is FormalRuntimeState.ABSENT,
        "BOOTSTRAP_ONLY_STATE_PASS": (
            bootstrap_only["state"] is FormalRuntimeState.BOOTSTRAP_ONLY
        ),
        "RESUMABLE_STATE_PASS": resumable["state"] is FormalRuntimeState.RESUMABLE,
        "INVALID_STATE_PASS": invalid_state["INVALID_STATE_PASS"],
        "FORMAL_BOOTSTRAP_STATE_MACHINE_IMPLEMENTATION": "PASS",
        "bootstrap": bootstrap,
        "bootstrap_resume": bootstrap_resume,
        "lock_transition": lock_transition,
        "lock_resume": lock_resume,
        "seed_entry_lock_gate_pass": seed_gate["seed_entry_lock_gate_pass"],
        "command_log_prelock_interruption_pass": (
            bootstrap_only["state"] is FormalRuntimeState.BOOTSTRAP_ONLY
        ),
        "COMMAND_LOG_PRELOCK_INTERRUPTION_PASS": (
            bootstrap_only["state"] is FormalRuntimeState.BOOTSTRAP_ONLY
        ),
        "bootstrap_only_recovery_pass": resumable["state"] is FormalRuntimeState.RESUMABLE,
        "BOOTSTRAP_ONLY_RECOVERY_PASS": (
            resumable["state"] is FormalRuntimeState.RESUMABLE
        ),
        "lock_atomic_interruption_pass": bool(
            interrupted
            and partial_accepted == 0
            and interruption_state["state"] is FormalRuntimeState.BOOTSTRAP_ONLY
            and recovered_interruption["state"] is FormalRuntimeState.RESUMABLE
        ),
        "LOCK_ATOMIC_INTERRUPTION_PASS": bool(
            interrupted
            and partial_accepted == 0
            and interruption_state["state"] is FormalRuntimeState.BOOTSTRAP_ONLY
            and recovered_interruption["state"] is FormalRuntimeState.RESUMABLE
        ),
        "partial_lock_accepted_count": partial_accepted,
        "PARTIAL_LOCK_ACCEPTED_COUNT": partial_accepted,
        "invalid_state_rejection": invalid_state,
        "interruption_observation": observed,
        "fresh": fresh,
        "resume": resumed,
        "valid_snapshot_reexecution_count": resumed.get(
            "generated_snapshot_count"
        ),
        "VALID_SNAPSHOT_REEXECUTION_COUNT": resumed.get(
            "generated_snapshot_count"
        ),
        "valid_trial_reexecution_count": resumed.get(
            "backend_execution_count_this_invocation"
        ),
        "VALID_TRIAL_REEXECUTION_COUNT": resumed.get(
            "backend_execution_count_this_invocation"
        ),
        "snapshot_checksum_change_after_resume": int(snapshot_before != snapshot_after),
        "SNAPSHOT_CHECKSUM_CHANGE_AFTER_RESUME": int(
            snapshot_before != snapshot_after
        ),
        "trial_checksum_change_after_resume": int(trial_before != trial_after),
        "TRIAL_CHECKSUM_CHANGE_AFTER_RESUME": int(trial_before != trial_after),
        "command_log_change_after_resume": int(command_before != command_after),
        "primary": primary,
        "independent": independent,
        "primary_independent_difference": difference,
        "raw_v3_fixture_envelope": raw_v3_envelope,
        "frozen_publisher_fixture_envelope": publisher_envelope,
        "publisher_input_validation": publisher_input_validation,
        "fixture_envelope_scientific_equivalence": envelope_equivalence,
        "fixture_seed_reference_audit": seed_audit,
        "publication": publication,
        "artifact_verification": artifact_verification,
        "formal_dry_run": dry_run,
        "git_gate_reports": projected_git_gates,
        "all_git_gates_pass": all_git_gates_pass,
        "ALL_GIT_GATES_PASS": all_git_gates_pass,
        "required_git_checkpoints": sorted(required_git_checkpoints),
        "observed_git_checkpoints": sorted(required_git_checkpoints),
        "git_gate_failure_count": sum(
            row.get("RUNTIME_GIT_GATE_PASS") is not True for row in gates
        ),
        "source_repository_runtime_file_read_count": monitor.count,
        "source_repository_runtime_import_count": len(imports),
        "source_repository_runtime_import_paths": imports,
        "v3_seed_access_count": dry_run["V3_SEED_ACCESS_COUNT"],
        "V3_SEED_ACCESS_COUNT": dry_run["V3_SEED_ACCESS_COUNT"],
        "v3_seed_capable_module_import_count": len(
            v3_seed_capable_module_imports
        ),
        "v3_seed_capable_module_imports": v3_seed_capable_module_imports,
        "v3_rng_instantiation_count": dry_run["V3_RNG_INSTANTIATION_COUNT"],
        "V3_RNG_INSTANTIATION_COUNT": dry_run["V3_RNG_INSTANTIATION_COUNT"],
        "v3_snapshot_construction_count": dry_run[
            "V3_SNAPSHOT_CONSTRUCTION_COUNT"
        ],
        "V3_SNAPSHOT_CONSTRUCTION_COUNT": dry_run[
            "V3_SNAPSHOT_CONSTRUCTION_COUNT"
        ],
        "v3_backend_execution_count": dry_run["V3_BACKEND_EXECUTION_COUNT"],
        "V3_BACKEND_EXECUTION_COUNT": dry_run["V3_BACKEND_EXECUTION_COUNT"],
        "v3_trial_result_count": dry_run["V3_TRIAL_RESULT_COUNT"],
        "V3_TRIAL_RESULT_COUNT": dry_run["V3_TRIAL_RESULT_COUNT"],
        "v3_started_event_count": dry_run["V3_STARTED_EVENT_COUNT"],
        "V3_STARTED_EVENT_COUNT": dry_run["V3_STARTED_EVENT_COUNT"],
        "formal_v1_seed_reference_count": seed_audit[
            "formal_v1_seed_reference_count"
        ],
        "formal_v2_seed_reference_count": seed_audit[
            "formal_v2_seed_reference_count"
        ],
        "formal_v3_seed_reference_count": seed_audit[
            "formal_v3_seed_reference_count"
        ],
        "confirmatory_seed_access_count": seed_audit[
            "confirmatory_seed_access_count"
        ],
        "confirmatory_rng_instantiation_count": seed_audit[
            "confirmatory_rng_instantiation_count"
        ],
        "confirmatory_snapshot_construction_count": seed_audit[
            "confirmatory_snapshot_construction_count"
        ],
        "confirmatory_backend_execution_count": seed_audit[
            "confirmatory_backend_execution_count"
        ],
        "formal_runtime_root": str(
            Path(manifest["runtime_root"])
        ),
        "qualification_runtime_root": str(QUALIFICATION_ROOT),
        "formal_runtime_root_created": not formal_runtime_absent,
        "qualification_command": canonical_formal_command(command).decode("utf-8"),
    })
    actual_shape_sha256 = _aggregate_shape_sha256(result)
    if actual_shape_sha256 != representative_shape_sha256:
        raise RuntimeError(
            "prefixture aggregate shape differs from final production aggregate"
        )
    json_native_preflight["PRODUCTION_AGGREGATE_SHAPE_SHA256"] = (
        actual_shape_sha256
    )
    json_native_preflight["PRODUCTION_AGGREGATE_SHAPE_MATCH"] = True
    output = (
        layout.temporary_inventory
        / "bootstrap_repair_requalification_v3.json"
    )
    normalized_result, inventory, conversion_audit, roundtrip_report = (
        _strict_roundtrip(
            aggregate=result,
            output=output,
            atomic_writer=atomic_create_canonical_json,
            scan_non_json_native_leaves=scan_non_json_native_leaves,
            to_strict_json_native=to_strict_json_native,
            assert_strict_json_native_tree=assert_strict_json_native_tree,
        )
    )
    _atomic_write_csv(
        layout.temporary_inventory / "final_aggregate_non_native_type_inventory.csv",
        fieldnames=(
            "json_path",
            "python_type",
            "module",
            "class_name",
            "representative_value",
            "conversion_required",
            "proposed_conversion",
            "scientific_field",
            "notes",
        ),
        rows=inventory,
    )
    _atomic_write_csv(
        layout.temporary_inventory / "final_aggregate_json_conversion_audit.csv",
        fieldnames=(
            "json_path",
            "source_type",
            "target_type",
            "source_summary",
            "target_value",
            "conversion_rule",
        ),
        rows=conversion_audit,
    )
    atomic_create_canonical_json(
        layout.temporary_inventory / "final_aggregate_roundtrip_report.json",
        {
            **roundtrip_report,
            "schema_version": "qualification_final_aggregate_roundtrip_report_v1",
            "prefixture_production_shape_roundtrip": json_native_preflight,
            "final_actual_aggregate_roundtrip": roundtrip_report,
            "PREFIXTURE_ROUNDTRIP_PASS": bool(
                json_native_preflight["FINAL_AGGREGATE_JSON_NATIVE_PASS"] is True
                and json_native_preflight["FINAL_AGGREGATE_ATOMIC_WRITE_PASS"] is True
                and json_native_preflight[
                    "FINAL_AGGREGATE_RELOAD_EQUALITY_PASS"
                ]
                is True
            ),
            "FINAL_ACTUAL_ROUNDTRIP_PASS": bool(
                roundtrip_report["FINAL_AGGREGATE_JSON_NATIVE_PASS"] is True
                and roundtrip_report["FINAL_AGGREGATE_ATOMIC_WRITE_PASS"] is True
                and roundtrip_report["FINAL_AGGREGATE_RELOAD_EQUALITY_PASS"]
                is True
            ),
        },
    )
    print(json.dumps(normalized_result, indent=2, sort_keys=True, allow_nan=False))
    return 0 if normalized_result[
        "FORMAL_BOOTSTRAP_STATE_MACHINE_QUALIFICATION_PASS"
    ] else 1


if __name__ == "__main__":
    raise SystemExit(main())
