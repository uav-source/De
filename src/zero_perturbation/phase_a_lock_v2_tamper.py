"""Deterministic 23-case pre-cache rejection audit for the layered locks."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
from typing import Any, Callable

from .backend_phase_a_v2 import LockValidationFailure, ValidationTrace, validate_lock_stack
from .phase_a_trial_result_schema import canonical_json_sha256, file_sha256


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(path)
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _rehash(value: dict[str, Any], field: str) -> None:
    value.pop(field, None)
    value[field] = canonical_json_sha256(value)


def _change_nested_threshold(scientific: dict[str, Any]) -> None:
    scientific["qualification_gates"]["phase_a_hard_gates"]["per_backend"]["q95_translation_update_m_max"] = 0.002


def _change_backend_parameter(scientific: dict[str, Any]) -> None:
    key = "open3d_point_to_plane"
    scientific["backend_parameters"][key]["maximum_correspondence_distance_m"] = 0.51


CaseMutation = Callable[[dict[str, Any]], None]


CASES: tuple[tuple[int, str, str, CaseMutation], ...] = (
    (1, "scientific_add_runner_sha", "scientific", lambda x: x.__setitem__("runner_sha256", "0" * 64)),
    (2, "scientific_modify_scene", "scientific", lambda x: x["scenes"].__setitem__(0, "CHANGED_SCENE")),
    (3, "scientific_modify_seed", "scientific", lambda x: x["geometry_seeds"][0].__setitem__("value", 1)),
    (4, "scientific_modify_threshold", "scientific", _change_nested_threshold),
    (5, "scientific_modify_backend_parameter", "scientific", _change_backend_parameter),
    (6, "scientific_unknown_top_level", "scientific", lambda x: x.__setitem__("unknown", True)),
    (7, "implementation_missing_publisher", "implementation", lambda x: x["implementation_bindings"].pop("publisher_sha256")),
    (8, "implementation_missing_independent_verifier", "implementation", lambda x: x["implementation_bindings"].pop("independent_verifier_sha256")),
    (9, "implementation_modify_runner", "implementation", lambda x: x["implementation_bindings"].__setitem__("formal_runner_sha256", "0" * 64)),
    (10, "implementation_modify_engine", "implementation", lambda x: x["implementation_bindings"].__setitem__("execution_engine_sha256", "0" * 64)),
    (11, "implementation_add_translation_threshold", "implementation", lambda x: x.__setitem__("translation_threshold_m", 0.001)),
    (12, "implementation_add_geometry_seed", "implementation", lambda x: x.__setitem__("geometry_seed", 1)),
    (13, "implementation_unknown_binding", "implementation", lambda x: x["implementation_bindings"].__setitem__("unknown_sha256", "0" * 64)),
    (14, "snapshot_binding_modify_lock_sha", "snapshot", lambda x: x.__setitem__("snapshot_lock_file_sha256", "0" * 64)),
    (15, "snapshot_binding_modify_cache_root", "snapshot", lambda x: x.__setitem__("stage0_cache_root", "data/changed")),
    (16, "snapshot_binding_modify_count", "snapshot", lambda x: x.__setitem__("planned_snapshot_count", 209)),
    (17, "formal_modify_planned_trial_sha", "formal", lambda x: x.__setitem__("planned_trials_sha256", "0" * 64)),
    (18, "formal_planned_trial_count_419", "formal", lambda x: x.__setitem__("planned_trial_count", 419)),
    (19, "formal_add_native", "formal", lambda x: x["allowed_backends"].append("native_full")),
    (20, "formal_authorization_false", "formal", lambda x: x.__setitem__("formal_execution_authorized", False)),
    (21, "formal_modify_scientific_sha", "formal", lambda x: x.__setitem__("scientific_protocol_lock_sha256", "0" * 64)),
    (22, "formal_modify_implementation_sha", "formal", lambda x: x.__setitem__("execution_implementation_lock_sha256", "0" * 64)),
    (23, "formal_unknown_top_level", "formal", lambda x: x.__setitem__("unknown", True)),
)


def run_23_tamper_cases(*, root: str | Path, formal_run_lock: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    base_formal = _read(Path(formal_run_lock).resolve())
    base_scientific = _read(repository / base_formal["scientific_protocol_lock_path"])
    base_implementation = _read(repository / base_formal["execution_implementation_lock_path"])
    source_binding = repository / Path(base_formal["scientific_protocol_lock_path"]).parent / "snapshot_lock_binding_v2.json"
    base_binding = _read(source_binding)
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="phase-a-lock-v2-tamper-") as temporary:
        temporary_root = Path(temporary)
        for number, name, layer, mutation in CASES:
            directory = temporary_root / f"case-{number:02d}"
            directory.mkdir()
            scientific = copy.deepcopy(base_scientific)
            implementation = copy.deepcopy(base_implementation)
            binding = copy.deepcopy(base_binding)
            formal = copy.deepcopy(base_formal)
            if layer == "scientific":
                mutation(scientific)
                _rehash(scientific, "scientific_payload_sha256")
            elif layer == "implementation":
                mutation(implementation)
                _rehash(implementation, "implementation_payload_sha256")
            elif layer == "snapshot":
                mutation(binding)
                _rehash(binding, "binding_payload_sha256")
            scientific_path = directory / "phase_a_scientific_protocol_lock_v2.json"
            implementation_path = directory / "phase_a_execution_implementation_lock_v2.json"
            binding_path = directory / "snapshot_lock_binding_v2.json"
            _write(scientific_path, scientific)
            _write(implementation_path, implementation)
            _write(binding_path, binding)
            formal["scientific_protocol_lock_path"] = str(scientific_path)
            formal["scientific_protocol_lock_sha256"] = file_sha256(scientific_path)
            formal["execution_implementation_lock_path"] = str(implementation_path)
            formal["execution_implementation_lock_sha256"] = file_sha256(implementation_path)
            if layer == "formal":
                # Preserve the requested formal mutation after rebinding temporary layers.
                mutation(formal)
            _rehash(formal, "formal_payload_sha256")
            formal_path = directory / "phase_a_formal_run_lock_v2.json"
            _write(formal_path, formal)
            trace = ValidationTrace()
            rejected = False
            classification = None
            message = None
            try:
                validate_lock_stack(
                    root=repository,
                    formal_run_lock=formal_path,
                    trace=trace,
                    require_environment=False,
                )
            except LockValidationFailure as error:
                rejected = True
                classification = error.classification
                message = str(error)
            results.append(
                {
                    "backend_execution_count": trace.backend_execution_count,
                    "cache_read_count": trace.cache_read_count,
                    "case_name": name,
                    "case_number": number,
                    "failure_classification": classification,
                    "failure_message": message,
                    "rejected": rejected,
                    "seed_access_count": trace.formal_seed_access_count,
                    "trial_result_count": trace.trial_result_count,
                }
            )
    passed = all(
        row["rejected"]
        and row["cache_read_count"] == 0
        and row["seed_access_count"] == 0
        and row["backend_execution_count"] == 0
        and row["trial_result_count"] == 0
        for row in results
    )
    return {
        "LOCK_ARCHITECTURE_V2_TAMPER_REJECTION_PASS": passed,
        "case_count": len(results),
        "cases": results,
        "rejected_case_count": sum(row["rejected"] for row in results),
        "schema_version": "phase_a_lock_architecture_v2_tamper_rejection_v1",
    }


__all__ = ["CASES", "run_23_tamper_cases"]
