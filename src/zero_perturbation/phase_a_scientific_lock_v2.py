"""Scientific-only Phase A lock projection and strict validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import jsonschema
import yaml

from .phase_a_trial_result_schema import canonical_json_sha256, file_sha256


LEGACY_PROTOCOL_LOCK_RELATIVE = Path(
    "artifacts/current/zero_perturbation_backend_phase_a_v1_2_lock/"
    "backend_phase_a_v1_2_protocol_lock.json"
)
SCIENTIFIC_BASE_PROTOCOL_RELATIVE = Path(
    "configs/zero_perturbation/backend_phase_a_v1.yaml"
)
SCIENTIFIC_SCHEMA_RELATIVE = Path(
    "schemas/phase_a_scientific_protocol_lock_v2.schema.json"
)
SCIENTIFIC_LOCK_RELATIVE = Path(
    "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/"
    "phase_a_scientific_protocol_lock_v2.json"
)

IMPLEMENTATION_FIELD_NAMES = frozenset(
    {
        "runner_sha",
        "runner_sha256",
        "formal_runner_sha256",
        "engine_sha",
        "engine_sha256",
        "execution_engine_sha256",
        "schema_implementation_sha256",
        "writer_sha",
        "writer_sha256",
        "resume_sha",
        "resume_sha256",
        "analysis_sha",
        "analysis_sha256",
        "verifier_sha",
        "verifier_sha256",
        "publisher_sha",
        "publisher_sha256",
        "artifact_verifier_sha256",
        "implementation_bindings",
        "implementation_sha256",
        "formal_execution_authorized",
        "run_id",
        "output_dir",
        "output_directory",
    }
)


class ScientificLockError(RuntimeError):
    """The scientific layer is invalid or contains another layer's fields."""


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ScientificLockError(f"cannot parse JSON: {path}") from error
    if type(value) is not dict:
        raise ScientificLockError(f"JSON root is not an object: {path}")
    return value


def _yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise ScientificLockError(f"cannot parse YAML: {path}") from error
    if type(value) is not dict:
        raise ScientificLockError(f"YAML root is not a mapping: {path}")
    return value


def _walk_keys(value: Any, path: str = "$") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            found.append((child, str(key).lower()))
            found.extend(_walk_keys(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_walk_keys(item, f"{path}[{index}]"))
    return found


def scientific_lock_implementation_fields(value: Mapping[str, Any]) -> list[str]:
    return [path for path, key in _walk_keys(value) if key in IMPLEMENTATION_FIELD_NAMES]


def expected_scientific_payload(root: str | Path) -> dict[str, Any]:
    """Project every scientific value from frozen source artifacts."""

    repository = Path(root).resolve()
    legacy_path = repository / LEGACY_PROTOCOL_LOCK_RELATIVE
    base = _yaml(repository / SCIENTIFIC_BASE_PROTOCOL_RELATIVE)
    matrix = base["phase_a_matrix"]
    open3d = base["open3d_parameter_contract"]["parameters"]
    pcl = base["pcl_parameter_contract"]["parameters"]
    allowed = list(base["formal_backends"]["allowed_in_order"])
    forbidden = list(base["formal_backends"]["excluded"].keys())
    result: dict[str, Any] = {
        "schema_version": "phase_a_scientific_protocol_lock_v2",
        "lock_type": "phase_a_scientific_protocol_lock",
        "lock_version": "2",
        "source_legacy_protocol_path": LEGACY_PROTOCOL_LOCK_RELATIVE.as_posix(),
        "source_legacy_protocol_sha256": file_sha256(legacy_path),
        "scenes": list(matrix["scenes"]),
        "geometry_seeds": [dict(item) for item in matrix["development_geometry_seeds"]],
        "measurement_seeds": [dict(item) for item in matrix["development_measurement_seeds"]],
        "repeat_indices": list(matrix["repeat_indices"]),
        "condition": str(matrix["conditions"][0]),
        "backend_algorithms": {
            allowed[0]: str(open3d["algorithm"]),
            allowed[1]: {
                "algorithm": str(pcl["algorithm"]),
                "transformation_estimation": str(pcl["transformation_estimation"]),
            },
        },
        "backend_versions": {
            allowed[0]: str(open3d["version"]),
            allowed[1]: str(pcl["version"]),
        },
        "backend_parameters": {
            allowed[0]: dict(open3d),
            allowed[1]: dict(pcl),
        },
        "transform_semantics": dict(base["transform_semantics"]),
        "translation_metric": dict(base["transform_semantics"]["translation_update_m"]),
        "rotation_metric_semantics": {
            "rotation_update_rad": dict(base["transform_semantics"]["rotation_update_rad"]),
            "rotation_matrix_quality_gate": dict(base["rotation_matrix_quality_gate"]),
        },
        "quantile_method": str(base["quantile_contract"]["q95"]["method"]),
        "qualification_gates": {
            "phase_a_hard_gates": dict(base["phase_a_hard_gates"]),
            "rotation_matrix_quality_gate": dict(base["rotation_matrix_quality_gate"]),
            "snapshot_diversity_gate": dict(base["snapshot_diversity_gate"]),
        },
        "failure_definitions": dict(base["solver_failure_definitions"]),
        "planned_snapshot_count": int(matrix["planned_snapshot_count"]),
        "planned_trial_count": int(matrix["planned_trial_count"]),
        "allowed_backends": allowed,
        "forbidden_backends": forbidden,
    }
    result["scientific_payload_sha256"] = canonical_json_sha256(result)
    return result


def validate_scientific_lock(value: Mapping[str, Any], *, root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    candidate = dict(value)
    try:
        jsonschema.Draft202012Validator(
            _json(repository / SCIENTIFIC_SCHEMA_RELATIVE)
        ).validate(candidate)
    except jsonschema.ValidationError as error:
        raise ScientificLockError(f"SCIENTIFIC_LOCK_INVALID: {error.message}") from error
    stored = candidate.pop("scientific_payload_sha256")
    if stored != canonical_json_sha256(candidate):
        raise ScientificLockError("SCIENTIFIC_LOCK_INVALID: payload SHA mismatch")
    fields = scientific_lock_implementation_fields(value)
    if fields:
        raise ScientificLockError(f"LOCK_LAYER_VIOLATION: implementation fields: {fields}")
    expected = expected_scientific_payload(repository)
    if dict(value) != expected:
        changed = sorted(key for key in expected if value.get(key) != expected[key])
        raise ScientificLockError(
            f"SCIENTIFIC_LOCK_INVALID: frozen projection changed: {changed}"
        )
    return dict(value)


def load_scientific_lock(path: str | Path, *, root: str | Path) -> dict[str, Any]:
    return validate_scientific_lock(_json(Path(path).resolve()), root=root)


def scientific_projection_diff(value: Mapping[str, Any], *, root: str | Path) -> dict[str, Any]:
    expected = expected_scientific_payload(root)

    def difference(field: str) -> int:
        return 0 if value.get(field) == expected[field] else 1

    counters = {
        "scene_difference_count": difference("scenes"),
        "geometry_seed_difference_count": difference("geometry_seeds"),
        "measurement_seed_difference_count": difference("measurement_seeds"),
        "repeat_difference_count": difference("repeat_indices"),
        "condition_difference_count": difference("condition"),
        "backend_algorithm_difference_count": difference("backend_algorithms"),
        "backend_version_difference_count": difference("backend_versions"),
        "backend_parameter_difference_count": difference("backend_parameters"),
        "transform_semantics_difference_count": difference("transform_semantics"),
        "translation_metric_difference_count": difference("translation_metric"),
        "rotation_metric_difference_count": difference("rotation_metric_semantics"),
        "quantile_method_difference_count": difference("quantile_method"),
        "threshold_difference_count": difference("qualification_gates"),
        "qualification_gate_difference_count": difference("qualification_gates"),
        "failure_definition_difference_count": difference("failure_definitions"),
        "planned_snapshot_count_difference": difference("planned_snapshot_count"),
        "planned_trial_count_difference": difference("planned_trial_count"),
        "allowed_backend_difference_count": difference("allowed_backends"),
        "forbidden_backend_difference_count": difference("forbidden_backends"),
    }
    return {
        "SCIENTIFIC_PROTOCOL_PROJECTION_PASS": all(item == 0 for item in counters.values()),
        "schema_version": "phase_a_scientific_protocol_projection_diff_v2",
        **counters,
    }


__all__ = [
    "LEGACY_PROTOCOL_LOCK_RELATIVE",
    "SCIENTIFIC_LOCK_RELATIVE",
    "ScientificLockError",
    "expected_scientific_payload",
    "load_scientific_lock",
    "scientific_lock_implementation_fields",
    "scientific_projection_diff",
    "validate_scientific_lock",
]
