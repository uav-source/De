"""Execution-only Phase A implementation lock construction and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import jsonschema

from .phase_a_execution_chain_audit import AUDIT_LOCK_RELATIVE, DEFAULT_PCL_CLI_RELATIVE
from .phase_a_execution_chain_fixture import (
    FIXTURE_LOCK_RELATIVE,
    FIXTURE_PARAMETER_LOCK_RELATIVE,
    FIXTURE_PLAN_RELATIVE,
)
from .phase_a_trial_result_schema import canonical_json_sha256, file_sha256


IMPLEMENTATION_SCHEMA_RELATIVE = Path(
    "schemas/phase_a_execution_implementation_lock_v2.schema.json"
)
IMPLEMENTATION_LOCK_RELATIVE = Path(
    "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/"
    "phase_a_execution_implementation_lock_v2.json"
)
EXECUTION_AUDIT_DECISION_RELATIVE = Path(
    "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/"
    "execution_fixture_final_decision.json"
)

IMPLEMENTATION_PATHS = {
    "formal_runner_sha256": "scripts/179_run_backend_phase_a_v2.py",
    "execution_engine_sha256": "src/zero_perturbation/backend_phase_a_v2.py",
    "trial_result_schema_sha256": "schemas/phase_a_trial_result_v1.schema.json",
    "trial_result_validator_sha256": "src/zero_perturbation/phase_a_trial_result_schema.py",
    "trial_result_writer_sha256": "src/zero_perturbation/phase_a_trial_result_writer.py",
    "trial_resume_validator_sha256": "src/zero_perturbation/phase_a_trial_resume.py",
    "attempt_event_writer_sha256": "src/zero_perturbation/phase_a_attempt_events.py",
    "resume_scientific_equivalence_sha256": "src/zero_perturbation/phase_a_resume_scientific_equivalence.py",
    "stage1_analysis_sha256": "src/zero_perturbation/phase_a_stage1_analysis.py",
    "independent_verifier_sha256": "src/zero_perturbation/phase_a_stage1_independent_verifier.py",
    "publisher_sha256": "src/zero_perturbation/phase_a_stage1_publisher.py",
    "artifact_verifier_sha256": "src/zero_perturbation/phase_a_lock_architecture_v2.py",
    "open3d_adapter_sha256": "src/zero_perturbation/open3d_backend.py",
    "pcl_adapter_sha256": "src/zero_perturbation/pcl_backend.py",
    "pcl_cli_sha256": DEFAULT_PCL_CLI_RELATIVE.as_posix(),
    "rotation_metric_sha256": "src/zero_perturbation/rotation_metrics.py",
}

SCIENTIFIC_KEY_FRAGMENTS = (
    "scene",
    "geometry_seed",
    "measurement_seed",
    "repeat",
    "condition",
    "threshold",
    "qualification_gate",
    "planned_snapshot",
    "planned_trial",
    "backend_parameter",
)


class ImplementationLockError(RuntimeError):
    """The implementation layer is incomplete, mismatched, or contaminated."""


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ImplementationLockError(f"cannot parse JSON: {path}") from error
    if type(value) is not dict:
        raise ImplementationLockError(f"JSON root is not an object: {path}")
    return value


def _walk_keys(value: Any, path: str = "$") -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            result.append((child, str(key).lower()))
            result.extend(_walk_keys(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.extend(_walk_keys(item, f"{path}[{index}]"))
    return result


def implementation_lock_scientific_fields(value: Mapping[str, Any]) -> list[str]:
    allowed_fixture_counts = {
        "$.fixture_contract_binding.fixture_snapshot_count",
        "$.fixture_contract_binding.fixture_trial_count",
    }
    return [
        path
        for path, key in _walk_keys(value)
        if path not in allowed_fixture_counts
        and any(fragment in key for fragment in SCIENTIFIC_KEY_FRAGMENTS)
    ]


def current_implementation_bindings(root: str | Path) -> dict[str, str]:
    repository = Path(root).resolve()
    missing = [path for path in IMPLEMENTATION_PATHS.values() if not (repository / path).is_file()]
    if missing:
        raise ImplementationLockError(f"implementation file missing: {missing}")
    return {
        name: file_sha256(repository / relative)
        for name, relative in IMPLEMENTATION_PATHS.items()
    }


def fixture_contract_binding(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    paths = {
        "fixture_protocol_lock": AUDIT_LOCK_RELATIVE,
        "fixture_lock": FIXTURE_LOCK_RELATIVE,
        "fixture_plan": FIXTURE_PLAN_RELATIVE,
        "fixture_parameter_lock": FIXTURE_PARAMETER_LOCK_RELATIVE,
        "fixture_builder": Path("src/zero_perturbation/phase_a_execution_chain_fixture.py"),
    }
    result: dict[str, Any] = {}
    for name, relative in paths.items():
        result[f"{name}_path"] = relative.as_posix()
        result[f"{name}_sha256"] = file_sha256(repository / relative)
    result["fixture_snapshot_count"] = 3
    result["fixture_trial_count"] = 6
    return result


def build_implementation_lock(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    audit = repository / EXECUTION_AUDIT_DECISION_RELATIVE
    decision = _json(audit)
    if decision.get("EXECUTION_FIXTURE_AUDIT_PASS") is not True:
        raise ImplementationLockError("execution fixture audit is not PASS")
    result: dict[str, Any] = {
        "schema_version": "phase_a_execution_implementation_lock_v2",
        "lock_type": "phase_a_execution_implementation_lock",
        "lock_version": "2",
        "execution_chain_audit_path": EXECUTION_AUDIT_DECISION_RELATIVE.as_posix(),
        "execution_chain_audit_sha256": file_sha256(audit),
        "execution_chain_audit_pass": True,
        "implementation_bindings": current_implementation_bindings(repository),
        "fixture_contract_binding": fixture_contract_binding(repository),
    }
    result["implementation_payload_sha256"] = canonical_json_sha256(result)
    return result


def validate_implementation_lock(
    value: Mapping[str, Any], *, root: str | Path, verify_current_files: bool = True
) -> dict[str, Any]:
    repository = Path(root).resolve()
    candidate = dict(value)
    try:
        jsonschema.Draft202012Validator(
            _json(repository / IMPLEMENTATION_SCHEMA_RELATIVE)
        ).validate(candidate)
    except jsonschema.ValidationError as error:
        raise ImplementationLockError(f"IMPLEMENTATION_LOCK_INVALID: {error.message}") from error
    stored = candidate.pop("implementation_payload_sha256")
    if stored != canonical_json_sha256(candidate):
        raise ImplementationLockError("IMPLEMENTATION_LOCK_INVALID: payload SHA mismatch")
    scientific = implementation_lock_scientific_fields(value)
    if scientific:
        raise ImplementationLockError(f"LOCK_LAYER_VIOLATION: scientific fields: {scientific}")
    for key in ("execution_chain_audit_path",):
        path = repository / str(value[key])
        if not path.is_file() or file_sha256(path) != value["execution_chain_audit_sha256"]:
            raise ImplementationLockError("IMPLEMENTATION_LOCK_INVALID: audit SHA mismatch")
    fixture = value["fixture_contract_binding"]
    for name in (
        "fixture_protocol_lock",
        "fixture_lock",
        "fixture_plan",
        "fixture_parameter_lock",
        "fixture_builder",
    ):
        path = repository / str(fixture[f"{name}_path"])
        if not path.is_file() or file_sha256(path) != fixture[f"{name}_sha256"]:
            raise ImplementationLockError(f"IMPLEMENTATION_LOCK_INVALID: {name} mismatch")
    if verify_current_files:
        actual = current_implementation_bindings(repository)
        mismatch = sorted(
            name for name, digest in actual.items()
            if value["implementation_bindings"].get(name) != digest
        )
        if mismatch:
            raise ImplementationLockError(f"IMPLEMENTATION_SHA_MISMATCH: {mismatch}")
    return dict(value)


def load_implementation_lock(path: str | Path, *, root: str | Path) -> dict[str, Any]:
    return validate_implementation_lock(_json(Path(path).resolve()), root=root)


__all__ = [
    "EXECUTION_AUDIT_DECISION_RELATIVE",
    "IMPLEMENTATION_LOCK_RELATIVE",
    "IMPLEMENTATION_PATHS",
    "ImplementationLockError",
    "build_implementation_lock",
    "current_implementation_bindings",
    "fixture_contract_binding",
    "implementation_lock_scientific_fields",
    "load_implementation_lock",
    "validate_implementation_lock",
]
