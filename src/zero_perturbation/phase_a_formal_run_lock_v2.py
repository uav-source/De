"""Minimal Phase A Formal Run Lock v2 construction and strict validation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping

import jsonschema

from .phase_a_implementation_lock_v2 import IMPLEMENTATION_LOCK_RELATIVE
from .phase_a_scientific_lock_v2 import SCIENTIFIC_LOCK_RELATIVE
from .phase_a_trial_result_schema import canonical_json_sha256, file_sha256


FORMAL_SCHEMA_RELATIVE = Path("schemas/phase_a_formal_run_lock_v2.schema.json")
FORMAL_LOCK_RELATIVE = Path(
    "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/"
    "phase_a_formal_run_lock_v2.json"
)
SNAPSHOT_LOCK_RELATIVE = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_v1_2_stage0/"
    "backend_phase_a_v1_2_snapshot_lock.json"
)
PLANNED_SNAPSHOTS_RELATIVE = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_v1_2_lock/planned_snapshots.csv"
)
PLANNED_TRIALS_RELATIVE = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_v1_2_lock/planned_trials.csv"
)

DUPLICATED_CONTRACT_KEYS = frozenset(
    {
        "scenes",
        "geometry_seeds",
        "measurement_seeds",
        "repeat_indices",
        "backend_algorithms",
        "backend_versions",
        "backend_parameters",
        "transform_semantics",
        "translation_metric",
        "rotation_metric_semantics",
        "quantile_method",
        "qualification_gates",
        "failure_definitions",
        "implementation_bindings",
        "fixture_contract_binding",
        "translation_threshold_m",
        "rotation_threshold_rad",
    }
)


class FormalRunLockError(RuntimeError):
    """The formal run binding graph or authorization is invalid."""


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FormalRunLockError(f"cannot parse JSON: {path}") from error
    if type(value) is not dict:
        raise FormalRunLockError(f"JSON root is not an object: {path}")
    return value


def _csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))
    except (OSError, UnicodeError, csv.Error) as error:
        raise FormalRunLockError(f"cannot parse CSV: {path}") from error


def formal_run_lock_duplicated_contract_fields(value: Mapping[str, Any]) -> list[str]:
    return sorted(key for key in value if key in DUPLICATED_CONTRACT_KEYS)


def build_formal_run_lock(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    scientific = _json(repository / SCIENTIFIC_LOCK_RELATIVE)
    result: dict[str, Any] = {
        "schema_version": "phase_a_formal_run_lock_v2",
        "lock_type": "phase_a_formal_run_lock",
        "lock_version": "2",
        "scientific_protocol_lock_path": SCIENTIFIC_LOCK_RELATIVE.as_posix(),
        "scientific_protocol_lock_sha256": file_sha256(repository / SCIENTIFIC_LOCK_RELATIVE),
        "snapshot_lock_path": SNAPSHOT_LOCK_RELATIVE.as_posix(),
        "snapshot_lock_sha256": file_sha256(repository / SNAPSHOT_LOCK_RELATIVE),
        "execution_implementation_lock_path": IMPLEMENTATION_LOCK_RELATIVE.as_posix(),
        "execution_implementation_lock_sha256": file_sha256(repository / IMPLEMENTATION_LOCK_RELATIVE),
        "planned_snapshots_path": PLANNED_SNAPSHOTS_RELATIVE.as_posix(),
        "planned_snapshots_sha256": file_sha256(repository / PLANNED_SNAPSHOTS_RELATIVE),
        "planned_trials_path": PLANNED_TRIALS_RELATIVE.as_posix(),
        "planned_trials_sha256": file_sha256(repository / PLANNED_TRIALS_RELATIVE),
        "planned_snapshot_count": int(scientific["planned_snapshot_count"]),
        "planned_trial_count": int(scientific["planned_trial_count"]),
        "allowed_backends": list(scientific["allowed_backends"]),
        "forbidden_backends": list(scientific["forbidden_backends"]),
        "condition": str(scientific["condition"]),
        "formal_execution_authorized": True,
        "required_trial_schema_version": "phase_a_trial_result_v1",
    }
    result["formal_payload_sha256"] = canonical_json_sha256(result)
    return result


def validate_formal_run_lock_payload(value: Mapping[str, Any], *, root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    candidate = dict(value)
    try:
        jsonschema.Draft202012Validator(_json(repository / FORMAL_SCHEMA_RELATIVE)).validate(candidate)
    except jsonschema.ValidationError as error:
        raise FormalRunLockError(f"FORMAL_RUN_LOCK_INVALID: {error.message}") from error
    stored = candidate.pop("formal_payload_sha256")
    if stored != canonical_json_sha256(candidate):
        raise FormalRunLockError("FORMAL_RUN_LOCK_INVALID: payload SHA mismatch")
    duplicates = formal_run_lock_duplicated_contract_fields(value)
    if duplicates:
        raise FormalRunLockError(f"LOCK_LAYER_VIOLATION: duplicated fields: {duplicates}")
    if any("native" in str(item).lower() for item in value["allowed_backends"]):
        raise FormalRunLockError("FORMAL_RUN_LOCK_INVALID: Native backend allowed")
    return dict(value)


def validate_plan_bindings(value: Mapping[str, Any], *, root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    for prefix in ("planned_snapshots", "planned_trials"):
        path = repository / str(value[f"{prefix}_path"])
        if not path.is_file() or file_sha256(path) != value[f"{prefix}_sha256"]:
            raise FormalRunLockError(f"TRIAL_PLAN_MISMATCH: {prefix} SHA")
    snapshots = _csv(repository / str(value["planned_snapshots_path"]))
    trials = _csv(repository / str(value["planned_trials_path"]))
    if len(snapshots) != value["planned_snapshot_count"] or len(trials) != value["planned_trial_count"]:
        raise FormalRunLockError("TRIAL_PLAN_MISMATCH: row count")
    snapshot_ids = [row.get("snapshot_id") for row in snapshots]
    trial_ids = [row.get("planned_trial_id") for row in trials]
    if len(set(snapshot_ids)) != len(snapshot_ids) or len(set(trial_ids)) != len(trial_ids):
        raise FormalRunLockError("TRIAL_PLAN_MISMATCH: duplicate identifier")
    if any(row.get("condition") != value["condition"] for row in snapshots + trials):
        raise FormalRunLockError("TRIAL_PLAN_MISMATCH: condition")
    backends = {str(row.get("backend")) for row in trials}
    if backends != set(value["allowed_backends"]):
        raise FormalRunLockError("TRIAL_PLAN_MISMATCH: allowed backend set")
    if backends.intersection(value["forbidden_backends"]):
        raise FormalRunLockError("TRIAL_PLAN_MISMATCH: forbidden backend")
    return {"snapshots": snapshots, "trials": trials}


__all__ = [
    "FORMAL_LOCK_RELATIVE",
    "PLANNED_SNAPSHOTS_RELATIVE",
    "PLANNED_TRIALS_RELATIVE",
    "SNAPSHOT_LOCK_RELATIVE",
    "FormalRunLockError",
    "build_formal_run_lock",
    "formal_run_lock_duplicated_contract_fields",
    "validate_formal_run_lock_payload",
    "validate_plan_bindings",
]
