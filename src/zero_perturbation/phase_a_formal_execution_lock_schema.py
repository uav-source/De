"""Exact schema, builder primitives, and validator for the Formal Lock v1."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from .phase_a_execution_chain_audit import implementation_manifest
from .phase_a_trial_result_schema import (
    OPEN3D_BACKEND,
    PCL_BACKEND,
    SCHEMA_VERSION as TRIAL_SCHEMA_VERSION,
    canonical_json_sha256,
    file_sha256,
)


SCHEMA_VERSION = "phase_a_formal_execution_lock_v1"
LOCK_TYPE = "phase_a_stage1_formal_execution_lock"
LOCK_VERSION = "1.1"
SCHEMA_RELATIVE_PATH = Path("schemas/phase_a_formal_execution_lock_v1.schema.json")
FORMAL_LOCK_RELATIVE_PATH = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_stage1_formal_lock_v1_2/"
    "backend_phase_a_stage1_formal_execution_lock.json"
)
IMPLEMENTATION_MANIFEST_RELATIVE_PATH = Path(
    "artifacts/current/zero_perturbation_phase_a_execution_chain_audit_v1_2/"
    "implementation_manifest.json"
)
PROTOCOL_RELATIVE_PATH = Path("configs/zero_perturbation/backend_phase_a_v1_2.yaml")
PROTOCOL_LOCK_RELATIVE_PATH = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_v1_2_lock/"
    "backend_phase_a_v1_2_protocol_lock.json"
)
SNAPSHOT_LOCK_RELATIVE_PATH = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_v1_2_stage0/"
    "backend_phase_a_v1_2_snapshot_lock.json"
)
STAGE0_MANIFEST_RELATIVE_PATH = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_v1_2_stage0/run_manifest.json"
)
SNAPSHOT_CACHE_RELATIVE_PATH = Path(
    "data/zero_perturbation/backend_phase_a_v1_2_stage0"
)
PLANNED_SNAPSHOTS_RELATIVE_PATH = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_v1_2_lock/planned_snapshots.csv"
)
PLANNED_TRIALS_RELATIVE_PATH = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_v1_2_lock/planned_trials.csv"
)
METRIC_CONTRACT_RELATIVE_PATH = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_v1_2_lock/metric_contract.json"
)
BACKEND_PARAMETER_CONTRACT_RELATIVE_PATH = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_v1_2_lock/"
    "backend_parameter_contract.json"
)
GATE_CONTRACT_RELATIVE_PATH = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_lock/gate_contract.json"
)

PLANNED_SNAPSHOT_COUNT = 210
PLANNED_TRIAL_COUNT = 420
TRANSLATION_THRESHOLD_M = 0.001
ROTATION_THRESHOLD_RAD = 0.00017453292519943296
QUANTILE_METHOD = "linear"
CONDITION = "IDEAL_MATCHED"
ALLOWED_BACKENDS = (OPEN3D_BACKEND, PCL_BACKEND)
FORBIDDEN_BACKENDS = ("native_full", "native_frozen")

TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "lock_type",
        "lock_version",
        "formal_execution_authorized",
        "formal_phase_a",
        "fixture_only",
        "created_from_commit",
        "created_at_utc",
        "protocol_binding",
        "snapshot_binding",
        "trial_plan_binding",
        "scientific_contract_binding",
        "implementation_bindings",
        "required_trial_schema_version",
        "allowed_backends",
        "forbidden_backends",
        "planned_snapshot_count",
        "planned_trial_count",
        "condition",
        "lock_payload_sha256",
    }
)
PROTOCOL_BINDING_FIELDS = frozenset(
    {"protocol_path", "protocol_sha256", "protocol_lock_path", "protocol_lock_sha256"}
)
SNAPSHOT_BINDING_FIELDS = frozenset(
    {
        "snapshot_lock_path",
        "snapshot_lock_sha256",
        "stage0_manifest_path",
        "stage0_manifest_sha256",
        "snapshot_cache_root",
        "snapshot_count",
    }
)
TRIAL_PLAN_BINDING_FIELDS = frozenset(
    {
        "planned_snapshots_path",
        "planned_snapshots_sha256",
        "planned_trials_path",
        "planned_trials_sha256",
        "planned_snapshot_count",
        "planned_trial_count",
    }
)
SCIENTIFIC_CONTRACT_BINDING_FIELDS = frozenset(
    {
        "metric_contract_sha256",
        "backend_parameter_contract_sha256",
        "gate_contract_sha256",
        "translation_threshold_m",
        "rotation_threshold_rad",
        "quantile_method",
    }
)
IMPLEMENTATION_BINDING_FIELDS = frozenset(
    {
        "formal_runner_sha256",
        "trial_result_schema_sha256",
        "trial_result_validator_sha256",
        "trial_result_writer_sha256",
        "trial_resume_validator_sha256",
        "attempt_event_writer_sha256",
        "stage1_analysis_sha256",
        "independent_verifier_sha256",
        "publisher_sha256",
        "artifact_verifier_sha256",
        "open3d_adapter_sha256",
        "pcl_adapter_sha256",
        "pcl_cli_sha256",
        "rotation_metric_sha256",
    }
)
V1_IMPLEMENTATION_MANIFEST_MAPPING = {
    "formal_runner_sha256": ("files", "formal_runner"),
    "trial_result_schema_sha256": ("files", "trial_schema"),
    "trial_result_validator_sha256": ("files", "schema_validator"),
    "trial_result_writer_sha256": ("files", "writer"),
    "trial_resume_validator_sha256": ("files", "resume"),
    "attempt_event_writer_sha256": ("files", "attempt_event_schema"),
    "stage1_analysis_sha256": ("files", "analysis"),
    "independent_verifier_sha256": ("files", "independent_verifier"),
    "publisher_sha256": ("files", "publisher"),
    "artifact_verifier_sha256": ("files", "artifact_verifier"),
    "open3d_adapter_sha256": ("files", "open3d_adapter"),
    "pcl_adapter_sha256": ("files", "pcl_adapter"),
    "pcl_cli_sha256": ("pcl_cli_binary", None),
    "rotation_metric_sha256": ("files", "rotation_metric"),
}
V1_2_IMPLEMENTATION_MANIFEST_MAPPING = {
    "formal_runner_sha256": ("files", "formal_runner"),
    "trial_result_schema_sha256": ("files", "trial_result_schema"),
    "trial_result_validator_sha256": ("files", "trial_result_validator"),
    "trial_result_writer_sha256": ("files", "trial_result_writer"),
    "trial_resume_validator_sha256": ("files", "strict_resume_validator"),
    "attempt_event_writer_sha256": ("files", "attempt_event_writer"),
    "stage1_analysis_sha256": ("files", "analysis"),
    "independent_verifier_sha256": ("files", "independent_verifier"),
    "publisher_sha256": ("files", "publisher"),
    "artifact_verifier_sha256": ("files", "artifact_verifier"),
    "open3d_adapter_sha256": ("files", "open3d_adapter"),
    "pcl_adapter_sha256": ("files", "pcl_adapter"),
    "pcl_cli_sha256": ("pcl_cli_binary", None),
    "rotation_metric_sha256": ("files", "rotation_metric"),
}
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class FormalExecutionLockValidationError(ValueError):
    """Categorized rejection raised before any Stage-0 cache access."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


def _reject(code: str, detail: str) -> None:
    raise FormalExecutionLockValidationError(code, detail)


def _load_json_object(path: Path, label: str) -> dict[str, Any]:
    def reject_constant(token: str) -> None:
        raise ValueError(f"non-finite JSON constant: {token}")

    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        _reject("FORMAL_LOCK_INVALID_JSON", f"{label}: {error}")
    if type(value) is not dict:
        _reject("FORMAL_LOCK_INVALID_JSON", f"{label} root must be an object")
    return value


def _exact_fields(
    value: Any,
    expected: frozenset[str],
    label: str,
    *,
    implementation_bindings: bool = False,
) -> Mapping[str, Any]:
    if type(value) is not dict:
        _reject("FORMAL_LOCK_SCHEMA_INVALID", f"{label} must be an object")
    missing = expected - set(value)
    unknown = set(value) - expected
    if missing:
        code = (
            "FORMAL_LOCK_MISSING_REQUIRED_BINDING"
            if implementation_bindings
            else "FORMAL_LOCK_SCHEMA_INVALID"
        )
        _reject(code, f"{label} missing fields: {sorted(missing)}")
    if unknown:
        _reject("FORMAL_LOCK_SCHEMA_INVALID", f"{label} unknown fields: {sorted(unknown)}")
    return value


def _require_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        _reject("FORMAL_LOCK_SCHEMA_INVALID", f"{label} must be 64 lowercase hex characters")
    return value


def _require_file_sha(repository: Path, relative: Path, expected: Any, label: str) -> None:
    candidate = repository / relative
    if not candidate.is_file() or file_sha256(candidate) != expected:
        _reject("FORMAL_LOCK_UPSTREAM_BINDING_MISMATCH", f"{label} SHA mismatch")


def _csv_row_count(path: Path) -> int:
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            return sum(1 for _ in csv.DictReader(stream))
    except OSError as error:
        _reject("FORMAL_LOCK_UPSTREAM_BINDING_MISMATCH", f"cannot read plan: {error}")


def implementation_bindings_from_manifest(value: Mapping[str, Any]) -> dict[str, str]:
    """Extract the exact 14 lock bindings; never synthesize missing manifest entries."""

    output: dict[str, str] = {}
    mapping = (
        V1_2_IMPLEMENTATION_MANIFEST_MAPPING
        if value.get("schema_version")
        == "phase_a_execution_chain_implementation_manifest_v1_2"
        else V1_IMPLEMENTATION_MANIFEST_MAPPING
    )
    try:
        for binding, (section, name) in mapping.items():
            entry = value[section] if name is None else value[section][name]
            output[binding] = _require_sha(entry["sha256"], f"manifest.{binding}")
    except (KeyError, TypeError) as error:
        _reject(
            "FORMAL_LOCK_IMPLEMENTATION_BINDING_MISMATCH",
            f"implementation manifest lacks a required component: {error}",
        )
    return output


def implementation_manifest_v1_2(root: str | Path) -> dict[str, Any]:
    """Recompute every file bound by execution-chain audit v1.2."""

    repository = Path(root).resolve()
    paths = {
        "formal_runner": "scripts/168_run_backend_phase_a.py",
        "formal_lock_schema": "schemas/phase_a_formal_execution_lock_v1.schema.json",
        "formal_lock_validator": "src/zero_perturbation/phase_a_formal_execution_lock_schema.py",
        "trial_result_schema": "schemas/phase_a_trial_result_v1.schema.json",
        "trial_result_validator": "src/zero_perturbation/phase_a_trial_result_schema.py",
        "trial_result_writer": "src/zero_perturbation/phase_a_trial_result_writer.py",
        "strict_resume_validator": "src/zero_perturbation/phase_a_trial_resume.py",
        "attempt_event_writer": "src/zero_perturbation/phase_a_attempt_events.py",
        "scientific_equivalence_comparator": "src/zero_perturbation/phase_a_resume_scientific_equivalence.py",
        "analysis": "src/zero_perturbation/phase_a_stage1_analysis.py",
        "independent_verifier": "src/zero_perturbation/phase_a_stage1_independent_verifier.py",
        "publisher": "src/zero_perturbation/phase_a_stage1_publisher.py",
        "artifact_verifier": "src/zero_perturbation/phase_a_execution_chain_v1_2_artifact_verifier.py",
        "execution_chain_audit_v1_2_runner": "scripts/176_run_phase_a_execution_chain_audit_v1_2.py",
        "open3d_adapter": "src/zero_perturbation/open3d_backend.py",
        "pcl_adapter": "src/zero_perturbation/pcl_backend.py",
        "pcl_cli_source": "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp",
        "rotation_metric": "src/zero_perturbation/rotation_metrics.py",
    }
    manifest: dict[str, Any] = {
        "files": {
            name: {"path": path, "sha256": file_sha256(repository / path)}
            for name, path in paths.items()
        },
        "pcl_cli_binary": {
            "path": "build/pcl_point_to_plane_v3/pcl_point_to_plane_cli",
            "sha256": file_sha256(
                repository / "build/pcl_point_to_plane_v3/pcl_point_to_plane_cli"
            ),
        },
        "schema_version": "phase_a_execution_chain_implementation_manifest_v1_2",
    }
    manifest["implementation_sha256"] = canonical_json_sha256(manifest)
    return manifest


def _load_current_implementation_bindings(
    repository: Path, implementation_manifest_path: Path
) -> dict[str, str]:
    frozen = _load_json_object(implementation_manifest_path, "implementation manifest")
    try:
        current = (
            implementation_manifest_v1_2(repository)
            if frozen.get("schema_version")
            == "phase_a_execution_chain_implementation_manifest_v1_2"
            else implementation_manifest(repository)
        )
    except (OSError, KeyError, ValueError) as error:
        _reject("FORMAL_LOCK_IMPLEMENTATION_BINDING_MISMATCH", str(error))
    if frozen != current:
        _reject(
            "FORMAL_LOCK_IMPLEMENTATION_BINDING_MISMATCH",
            "frozen execution-chain implementation manifest differs from current implementation",
        )
    return implementation_bindings_from_manifest(frozen)


def build_phase_a_formal_execution_lock(
    *,
    root: str | Path,
    implementation_manifest_path: str | Path,
    created_from_commit: str,
    created_at_utc: str,
) -> dict[str, Any]:
    """Build a complete lock from already published and independently verified inputs."""

    repository = Path(root).resolve()
    if COMMIT_PATTERN.fullmatch(created_from_commit) is None:
        raise ValueError("created_from_commit must be a 40-character lowercase Git SHA")
    try:
        datetime.strptime(created_at_utc, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise ValueError("created_at_utc must use YYYY-MM-DDTHH:MM:SSZ") from error
    implementation_path = Path(implementation_manifest_path).resolve()
    bindings = _load_current_implementation_bindings(repository, implementation_path)
    payload: dict[str, Any] = {
        "allowed_backends": list(ALLOWED_BACKENDS),
        "condition": CONDITION,
        "created_at_utc": created_at_utc,
        "created_from_commit": created_from_commit,
        "fixture_only": False,
        "forbidden_backends": list(FORBIDDEN_BACKENDS),
        "formal_execution_authorized": True,
        "formal_phase_a": True,
        "implementation_bindings": bindings,
        "lock_type": LOCK_TYPE,
        "lock_version": LOCK_VERSION,
        "planned_snapshot_count": PLANNED_SNAPSHOT_COUNT,
        "planned_trial_count": PLANNED_TRIAL_COUNT,
        "protocol_binding": {
            "protocol_lock_path": PROTOCOL_LOCK_RELATIVE_PATH.as_posix(),
            "protocol_lock_sha256": file_sha256(repository / PROTOCOL_LOCK_RELATIVE_PATH),
            "protocol_path": PROTOCOL_RELATIVE_PATH.as_posix(),
            "protocol_sha256": file_sha256(repository / PROTOCOL_RELATIVE_PATH),
        },
        "required_trial_schema_version": TRIAL_SCHEMA_VERSION,
        "schema_version": SCHEMA_VERSION,
        "scientific_contract_binding": {
            "backend_parameter_contract_sha256": file_sha256(
                repository / BACKEND_PARAMETER_CONTRACT_RELATIVE_PATH
            ),
            "gate_contract_sha256": file_sha256(repository / GATE_CONTRACT_RELATIVE_PATH),
            "metric_contract_sha256": file_sha256(
                repository / METRIC_CONTRACT_RELATIVE_PATH
            ),
            "quantile_method": QUANTILE_METHOD,
            "rotation_threshold_rad": ROTATION_THRESHOLD_RAD,
            "translation_threshold_m": TRANSLATION_THRESHOLD_M,
        },
        "snapshot_binding": {
            "snapshot_cache_root": SNAPSHOT_CACHE_RELATIVE_PATH.as_posix(),
            "snapshot_count": PLANNED_SNAPSHOT_COUNT,
            "snapshot_lock_path": SNAPSHOT_LOCK_RELATIVE_PATH.as_posix(),
            "snapshot_lock_sha256": file_sha256(repository / SNAPSHOT_LOCK_RELATIVE_PATH),
            "stage0_manifest_path": STAGE0_MANIFEST_RELATIVE_PATH.as_posix(),
            "stage0_manifest_sha256": file_sha256(repository / STAGE0_MANIFEST_RELATIVE_PATH),
        },
        "trial_plan_binding": {
            "planned_snapshot_count": PLANNED_SNAPSHOT_COUNT,
            "planned_snapshots_path": PLANNED_SNAPSHOTS_RELATIVE_PATH.as_posix(),
            "planned_snapshots_sha256": file_sha256(
                repository / PLANNED_SNAPSHOTS_RELATIVE_PATH
            ),
            "planned_trial_count": PLANNED_TRIAL_COUNT,
            "planned_trials_path": PLANNED_TRIALS_RELATIVE_PATH.as_posix(),
            "planned_trials_sha256": file_sha256(repository / PLANNED_TRIALS_RELATIVE_PATH),
        },
    }
    payload["lock_payload_sha256"] = canonical_json_sha256(payload)
    return payload


def validate_phase_a_formal_execution_lock_strict(
    path: str | Path,
    *,
    root: str | Path,
    protocol_lock: str | Path,
    snapshot_lock: str | Path,
    implementation_manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    """Reject any incomplete, aliased, stale, or scientifically divergent lock."""

    repository = Path(root).resolve()
    candidate = Path(path).resolve()
    if not candidate.is_file():
        raise FileNotFoundError("--formal-execution-lock file does not exist")

    # 1-6: parse and validate the exact shape before consulting any manifest.
    value = _load_json_object(candidate, "formal execution lock")
    if value.get("schema_version") != SCHEMA_VERSION:
        _reject("FORMAL_LOCK_SCHEMA_INVALID", "legacy or unknown schema_version")
    _exact_fields(value, TOP_LEVEL_FIELDS, "formal execution lock")
    protocol = _exact_fields(value["protocol_binding"], PROTOCOL_BINDING_FIELDS, "protocol_binding")
    snapshot = _exact_fields(value["snapshot_binding"], SNAPSHOT_BINDING_FIELDS, "snapshot_binding")
    trial_plan = _exact_fields(value["trial_plan_binding"], TRIAL_PLAN_BINDING_FIELDS, "trial_plan_binding")
    scientific = _exact_fields(
        value["scientific_contract_binding"],
        SCIENTIFIC_CONTRACT_BINDING_FIELDS,
        "scientific_contract_binding",
    )
    bindings = _exact_fields(
        value["implementation_bindings"],
        IMPLEMENTATION_BINDING_FIELDS,
        "implementation_bindings",
        implementation_bindings=True,
    )
    sha_values = {
        "lock_payload_sha256": value["lock_payload_sha256"],
        "protocol_sha256": protocol["protocol_sha256"],
        "protocol_lock_sha256": protocol["protocol_lock_sha256"],
        "snapshot_lock_sha256": snapshot["snapshot_lock_sha256"],
        "stage0_manifest_sha256": snapshot["stage0_manifest_sha256"],
        "planned_snapshots_sha256": trial_plan["planned_snapshots_sha256"],
        "planned_trials_sha256": trial_plan["planned_trials_sha256"],
        "metric_contract_sha256": scientific["metric_contract_sha256"],
        "backend_parameter_contract_sha256": scientific["backend_parameter_contract_sha256"],
        "gate_contract_sha256": scientific["gate_contract_sha256"],
        **bindings,
    }
    for label, item in sha_values.items():
        _require_sha(item, label)

    schema_document = _load_json_object(repository / SCHEMA_RELATIVE_PATH, "formal lock JSON schema")
    errors = sorted(
        Draft202012Validator(schema_document).iter_errors(value),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        _reject("FORMAL_LOCK_SCHEMA_INVALID", errors[0].message)

    # 7-15: fixed authorization and scientific scope.
    if value["formal_execution_authorized"] is not True:
        _reject("FORMAL_LOCK_NOT_AUTHORIZED", "formal_execution_authorized must be true")
    if value["formal_phase_a"] is not True or value["fixture_only"] is not False:
        _reject("FORMAL_LOCK_SCHEMA_INVALID", "formal Phase A scope is invalid")
    if value["required_trial_schema_version"] != TRIAL_SCHEMA_VERSION:
        _reject("FORMAL_LOCK_SCIENTIFIC_CONTRACT_MISMATCH", "trial schema version changed")
    if value["allowed_backends"] != list(ALLOWED_BACKENDS):
        _reject("FORMAL_LOCK_SCIENTIFIC_CONTRACT_MISMATCH", "allowed backends changed")
    if value["forbidden_backends"] != list(FORBIDDEN_BACKENDS):
        _reject("FORMAL_LOCK_SCIENTIFIC_CONTRACT_MISMATCH", "Native prohibition changed")
    if (
        value["planned_snapshot_count"] != PLANNED_SNAPSHOT_COUNT
        or value["planned_trial_count"] != PLANNED_TRIAL_COUNT
        or value["condition"] != CONDITION
    ):
        _reject("FORMAL_LOCK_SCIENTIFIC_CONTRACT_MISMATCH", "plan counts or condition changed")
    if COMMIT_PATTERN.fullmatch(value["created_from_commit"]) is None:
        _reject("FORMAL_LOCK_SCHEMA_INVALID", "created_from_commit is invalid")
    try:
        datetime.strptime(value["created_at_utc"], "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        _reject("FORMAL_LOCK_SCHEMA_INVALID", "created_at_utc is invalid")

    # Payload integrity is checked before any upstream or implementation file lookup.
    stored_payload_sha = value["lock_payload_sha256"]
    payload = {name: item for name, item in value.items() if name != "lock_payload_sha256"}
    if canonical_json_sha256(payload) != stored_payload_sha:
        _reject("FORMAL_LOCK_PAYLOAD_SHA_MISMATCH", "lock payload SHA is not self-consistent")

    # 16: every upstream path is canonical and every SHA is checked.
    expected_protocol = {
        "protocol_path": PROTOCOL_RELATIVE_PATH.as_posix(),
        "protocol_lock_path": PROTOCOL_LOCK_RELATIVE_PATH.as_posix(),
    }
    if any(protocol[name] != expected for name, expected in expected_protocol.items()):
        _reject("FORMAL_LOCK_UPSTREAM_BINDING_MISMATCH", "protocol path binding changed")
    actual_protocol_lock = Path(protocol_lock).resolve()
    if actual_protocol_lock != repository / PROTOCOL_LOCK_RELATIVE_PATH:
        _reject("FORMAL_LOCK_UPSTREAM_BINDING_MISMATCH", "--protocol-lock path is not bound")
    _require_file_sha(repository, PROTOCOL_RELATIVE_PATH, protocol["protocol_sha256"], "protocol")
    _require_file_sha(
        repository, PROTOCOL_LOCK_RELATIVE_PATH, protocol["protocol_lock_sha256"], "protocol lock"
    )

    expected_snapshot_paths = {
        "snapshot_lock_path": SNAPSHOT_LOCK_RELATIVE_PATH.as_posix(),
        "stage0_manifest_path": STAGE0_MANIFEST_RELATIVE_PATH.as_posix(),
        "snapshot_cache_root": SNAPSHOT_CACHE_RELATIVE_PATH.as_posix(),
    }
    if any(snapshot[name] != expected for name, expected in expected_snapshot_paths.items()):
        _reject("FORMAL_LOCK_UPSTREAM_BINDING_MISMATCH", "snapshot path binding changed")
    if snapshot["snapshot_count"] != PLANNED_SNAPSHOT_COUNT:
        _reject("FORMAL_LOCK_UPSTREAM_BINDING_MISMATCH", "snapshot binding count changed")
    actual_snapshot_lock = Path(snapshot_lock).resolve()
    if actual_snapshot_lock != repository / SNAPSHOT_LOCK_RELATIVE_PATH:
        _reject("FORMAL_LOCK_UPSTREAM_BINDING_MISMATCH", "--snapshot-lock path is not bound")
    _require_file_sha(
        repository, SNAPSHOT_LOCK_RELATIVE_PATH, snapshot["snapshot_lock_sha256"], "snapshot lock"
    )
    _require_file_sha(
        repository, STAGE0_MANIFEST_RELATIVE_PATH, snapshot["stage0_manifest_sha256"], "Stage-0 manifest"
    )
    stage0_manifest = _load_json_object(repository / STAGE0_MANIFEST_RELATIVE_PATH, "Stage-0 manifest")
    if (
        stage0_manifest.get("complete_snapshot_count") != PLANNED_SNAPSHOT_COUNT
        or stage0_manifest.get("stage0_backend_execution_count") != 0
        or stage0_manifest.get("formal_trial_result_count") != 0
        or stage0_manifest.get("native_execution_count") != 0
    ):
        _reject("FORMAL_LOCK_UPSTREAM_BINDING_MISMATCH", "Stage-0 manifest boundary changed")

    expected_plan_paths = {
        "planned_snapshots_path": PLANNED_SNAPSHOTS_RELATIVE_PATH.as_posix(),
        "planned_trials_path": PLANNED_TRIALS_RELATIVE_PATH.as_posix(),
    }
    if any(trial_plan[name] != expected for name, expected in expected_plan_paths.items()):
        _reject("FORMAL_LOCK_UPSTREAM_BINDING_MISMATCH", "trial plan path binding changed")
    if (
        trial_plan["planned_snapshot_count"] != PLANNED_SNAPSHOT_COUNT
        or trial_plan["planned_trial_count"] != PLANNED_TRIAL_COUNT
    ):
        _reject("FORMAL_LOCK_UPSTREAM_BINDING_MISMATCH", "trial plan count binding changed")
    _require_file_sha(
        repository,
        PLANNED_SNAPSHOTS_RELATIVE_PATH,
        trial_plan["planned_snapshots_sha256"],
        "planned snapshots",
    )
    _require_file_sha(
        repository,
        PLANNED_TRIALS_RELATIVE_PATH,
        trial_plan["planned_trials_sha256"],
        "planned trials",
    )
    if (
        _csv_row_count(repository / PLANNED_SNAPSHOTS_RELATIVE_PATH) != PLANNED_SNAPSHOT_COUNT
        or _csv_row_count(repository / PLANNED_TRIALS_RELATIVE_PATH) != PLANNED_TRIAL_COUNT
    ):
        _reject("FORMAL_LOCK_UPSTREAM_BINDING_MISMATCH", "trial plan row count changed")

    # 17: every lock-carried implementation SHA must equal the newly frozen manifest.
    manifest_path = (
        Path(implementation_manifest_path).resolve()
        if implementation_manifest_path is not None
        else repository / IMPLEMENTATION_MANIFEST_RELATIVE_PATH
    )
    current_bindings = _load_current_implementation_bindings(repository, manifest_path)
    mismatches = sorted(
        name for name in IMPLEMENTATION_BINDING_FIELDS if bindings[name] != current_bindings[name]
    )
    if mismatches:
        _reject(
            "FORMAL_LOCK_IMPLEMENTATION_BINDING_MISMATCH",
            f"implementation SHA mismatch: {mismatches}",
        )

    # 18: byte-exact scientific contracts and their semantic scalar values.
    scientific_files = {
        "metric_contract_sha256": METRIC_CONTRACT_RELATIVE_PATH,
        "backend_parameter_contract_sha256": BACKEND_PARAMETER_CONTRACT_RELATIVE_PATH,
        "gate_contract_sha256": GATE_CONTRACT_RELATIVE_PATH,
    }
    for field, relative in scientific_files.items():
        _require_file_sha(repository, relative, scientific[field], field)
    if (
        scientific["translation_threshold_m"] != TRANSLATION_THRESHOLD_M
        or scientific["rotation_threshold_rad"] != ROTATION_THRESHOLD_RAD
        or scientific["quantile_method"] != QUANTILE_METHOD
    ):
        _reject("FORMAL_LOCK_SCIENTIFIC_CONTRACT_MISMATCH", "metric threshold changed")

    # 19: payload was already checked before file access; retain this marker for callers.
    result = dict(value)
    result["validation"] = {
        "FORMAL_LOCK_ALL_IMPLEMENTATION_BINDINGS_REQUIRED": True,
        "FORMAL_LOCK_BINDING_SHA_MATCH_PASS": True,
        "FORMAL_LOCK_INDEPENDENT_VERIFIER_BINDING_REQUIRED": True,
        "FORMAL_LOCK_PUBLISHER_BINDING_REQUIRED": True,
        "FORMAL_LOCK_SCHEMA_PASS": True,
        "FORMAL_LOCK_V1_1_IMPLEMENTATION_BINDING_PASS": True,
        "FORMAL_LOCK_V1_1_SCIENTIFIC_CONTRACT_PASS": True,
        "FORMAL_LOCK_V1_1_UPSTREAM_BINDING_PASS": True,
    }
    return result


def implementation_binding_sha256(lock: Mapping[str, Any]) -> str:
    """Stable trial provenance digest derived only from lock-carried implementation bindings."""

    bindings = _exact_fields(
        lock.get("implementation_bindings"),
        IMPLEMENTATION_BINDING_FIELDS,
        "implementation_bindings",
        implementation_bindings=True,
    )
    return canonical_json_sha256(dict(bindings))


__all__ = [
    "ALLOWED_BACKENDS",
    "FORMAL_LOCK_RELATIVE_PATH",
    "FormalExecutionLockValidationError",
    "IMPLEMENTATION_BINDING_FIELDS",
    "IMPLEMENTATION_MANIFEST_RELATIVE_PATH",
    "SCHEMA_VERSION",
    "TOP_LEVEL_FIELDS",
    "build_phase_a_formal_execution_lock",
    "implementation_binding_sha256",
    "implementation_bindings_from_manifest",
    "implementation_manifest_v1_2",
    "validate_phase_a_formal_execution_lock_strict",
]
