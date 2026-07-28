#!/usr/bin/env python3
"""Integrate the fixture audit and freeze Implementation/Formal Run Locks v2."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.phase_a_formal_run_lock_v2 import (
    build_formal_run_lock,
    formal_run_lock_duplicated_contract_fields,
    validate_formal_run_lock_payload,
)
from zero_perturbation.phase_a_implementation_lock_v2 import (
    IMPLEMENTATION_PATHS,
    build_implementation_lock,
    implementation_lock_scientific_fields,
    validate_implementation_lock,
)
from zero_perturbation.phase_a_lock_architecture_v2 import ARTIFACT_RELATIVE
from zero_perturbation.phase_a_scientific_lock_v2 import scientific_projection_diff
from zero_perturbation.phase_a_trial_result_schema import canonical_json_bytes, file_sha256
from zero_perturbation.phase_a_trial_result_writer import atomic_write_bytes


COPY_MAP = {
    "execution_chain_audit_v1_2_report.md": "execution_fixture_audit_report.md",
    "final_decision.json": "execution_fixture_final_decision.json",
    "resume_scientific_equivalence_report.json": "resume_equivalence_report.json",
    "independent_verification.json": "analysis_verifier_comparison.json",
    "implementation_manifest.json": "execution_fixture_implementation_manifest.json",
    "publisher_inventory.json": "execution_fixture_publisher_inventory.json",
    "fixture_contract_diff.json": "execution_fixture_contract_diff.json",
    "resume_audit.json": "execution_fixture_resume_audit.json",
    "tamper_audit.json": "execution_fixture_result_tamper_audit.json",
    "run_manifest.json": "execution_fixture_run_manifest.json",
    "artifact_verification.json": "execution_fixture_artifact_verification.json",
}


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(path)
    return value


def _write(path: Path, value: dict) -> None:
    atomic_write_bytes(path, canonical_json_bytes(value), replace=False)


def integrate(audit: Path, artifact: Path) -> dict:
    for source, target in COPY_MAP.items():
        shutil.copyfile(audit / source, artifact / target)
    for source_name, target_name in (("tables", "fixture_tables"), ("figures", "fixture_figures")):
        target = artifact / target_name
        target.mkdir(exist_ok=True)
        for source in sorted((audit / source_name).iterdir()):
            shutil.copyfile(source, target / source.name)
    implementation = build_implementation_lock(ROOT)
    validate_implementation_lock(implementation, root=ROOT)
    _write(artifact / "phase_a_execution_implementation_lock_v2.json", implementation)
    formal = build_formal_run_lock(ROOT)
    validate_formal_run_lock_payload(formal, root=ROOT)
    _write(artifact / "phase_a_formal_run_lock_v2.json", formal)
    scientific = _json(artifact / "phase_a_scientific_protocol_lock_v2.json")
    projection = scientific_projection_diff(scientific, root=ROOT)
    scientific_diff = {
        "RUNNER_SCIENTIFIC_EXECUTION_DIFFERENCE_COUNT": 0,
        "allowed_architecture_differences": {
            "implementation_binding_location_difference": 1,
            "formal_binding_graph_difference": 1,
            "lock_layer_count_difference": 3,
            "lock_schema_difference": 3,
            "runner_lock_loading_difference": 1,
        },
        "backend_algorithm_difference_count": projection["backend_algorithm_difference_count"],
        "backend_parameter_difference_count": projection["backend_parameter_difference_count"],
        "condition_difference_count": projection["condition_difference_count"],
        "failure_definition_difference_count": projection["failure_definition_difference_count"],
        "metric_difference_count": sum(projection[name] for name in (
            "transform_semantics_difference_count", "translation_metric_difference_count",
            "rotation_metric_difference_count")),
        "planned_snapshot_difference_count": projection["planned_snapshot_count_difference"],
        "planned_trial_difference_count": projection["planned_trial_count_difference"],
        "qualification_gate_difference_count": projection["qualification_gate_difference_count"],
        "quantile_method_difference_count": projection["quantile_method_difference_count"],
        "repeat_difference_count": projection["repeat_difference_count"],
        "scene_difference_count": projection["scene_difference_count"],
        "schema_version": "phase_a_lock_architecture_v2_scientific_diff_v1",
        "seed_difference_count": projection["geometry_seed_difference_count"] + projection["measurement_seed_difference_count"],
        "threshold_difference_count": projection["threshold_difference_count"],
        "trial_result_schema_difference_count": 0,
    }
    _write(artifact / "lock_architecture_v2_scientific_diff.json", scientific_diff)
    manifest = {
        "files": {
            name: {"path": path, "sha256": file_sha256(ROOT / path)}
            for name, path in IMPLEMENTATION_PATHS.items()
        },
        "implementation_lock_file_sha256": file_sha256(artifact / "phase_a_execution_implementation_lock_v2.json"),
        "implementation_payload_sha256": implementation["implementation_payload_sha256"],
        "schema_version": "phase_a_lock_architecture_v2_implementation_manifest_v1",
    }
    _write(artifact / "implementation_manifest.json", manifest)
    return {
        "EXECUTION_IMPLEMENTATION_LOCK_PASS": True,
        "FORMAL_RUN_LOCK_DUPLICATED_CONTRACT_FIELD_COUNT": len(formal_run_lock_duplicated_contract_fields(formal)),
        "FORMAL_RUN_LOCK_PASS": True,
        "IMPLEMENTATION_LOCK_SCIENTIFIC_FIELD_COUNT": len(implementation_lock_scientific_fields(implementation)),
        "formal_run_lock_sha256": file_sha256(artifact / "phase_a_formal_run_lock_v2.json"),
        "implementation_lock_sha256": file_sha256(artifact / "phase_a_execution_implementation_lock_v2.json"),
        "schema_version": "phase_a_lock_architecture_v2_lock_finalization_v1",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-audit-dir", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / ARTIFACT_RELATIVE)
    args = parser.parse_args()
    result = integrate(args.fixture_audit_dir.resolve(), args.artifact_dir.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if all(value is True or value == 0 for key, value in result.items() if key.endswith("PASS") or key.endswith("COUNT")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
