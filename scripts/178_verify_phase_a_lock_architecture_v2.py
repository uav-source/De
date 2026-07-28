#!/usr/bin/env python3
"""Independently verify Phase A Lock Architecture v2 artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.phase_a_formal_run_lock_v2 import (
    formal_run_lock_duplicated_contract_fields,
    validate_formal_run_lock_payload,
)
from zero_perturbation.phase_a_implementation_lock_v2 import (
    implementation_lock_scientific_fields,
    validate_implementation_lock,
)
from zero_perturbation.phase_a_lock_architecture_v2 import (
    ARTIFACT_RELATIVE,
    legacy_field_classification,
    validate_snapshot_binding,
    verify_lock_architecture_artifact,
)
from zero_perturbation.phase_a_scientific_lock_v2 import (
    scientific_lock_implementation_fields,
    scientific_projection_diff,
    validate_scientific_lock,
)


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ValueError(f"not an object: {path}")
    return value


def verify_preparation(directory: Path) -> dict:
    scientific = _json(directory / "phase_a_scientific_protocol_lock_v2.json")
    validate_scientific_lock(scientific, root=ROOT)
    projection = scientific_projection_diff(scientific, root=ROOT)
    binding = validate_snapshot_binding(_json(directory / "snapshot_lock_binding_v2.json"), root=ROOT)
    expected_rows, expected_summary = legacy_field_classification(ROOT)
    with (directory / "legacy_lock_field_classification.csv").open(newline="", encoding="utf-8") as stream:
        actual_rows = list(csv.DictReader(stream))
    graph = _json(directory / "lock_dependency_graph.json")
    return {
        "LEGACY_LOCK_FIELD_CLASSIFICATION_PASS": actual_rows == expected_rows and expected_summary["LEGACY_LOCK_FIELD_CLASSIFICATION_PASS"],
        "LOCK_GRAPH_ACYCLIC": graph.get("LOCK_GRAPH_ACYCLIC") is True,
        "LOCK_GRAPH_DUPLICATE_BINDING_COUNT": graph.get("LOCK_GRAPH_DUPLICATE_BINDING_COUNT"),
        "SCIENTIFIC_LOCK_IMPLEMENTATION_FIELD_COUNT": len(scientific_lock_implementation_fields(scientific)),
        "SCIENTIFIC_PROTOCOL_PROJECTION_PASS": projection["SCIENTIFIC_PROTOCOL_PROJECTION_PASS"],
        "SNAPSHOT_LOCK_V2_BINDING_PASS": binding["SNAPSHOT_LOCK_V2_BINDING_PASS"],
        "schema_version": "phase_a_lock_architecture_v2_preparation_verification_v1",
    }


def verify_complete(directory: Path) -> dict:
    result = verify_preparation(directory)
    implementation = validate_implementation_lock(
        _json(directory / "phase_a_execution_implementation_lock_v2.json"), root=ROOT
    )
    formal = validate_formal_run_lock_payload(
        _json(directory / "phase_a_formal_run_lock_v2.json"), root=ROOT
    )
    artifact = verify_lock_architecture_artifact(directory)
    return {
        **result,
        "IMPLEMENTATION_LOCK_SCIENTIFIC_FIELD_COUNT": len(implementation_lock_scientific_fields(implementation)),
        "EXECUTION_IMPLEMENTATION_LOCK_PASS": True,
        "FORMAL_RUN_LOCK_DUPLICATED_CONTRACT_FIELD_COUNT": len(formal_run_lock_duplicated_contract_fields(formal)),
        "FORMAL_RUN_LOCK_PASS": True,
        **artifact,
        "schema_version": "phase_a_lock_architecture_v2_complete_verification_v1",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / ARTIFACT_RELATIVE)
    parser.add_argument("--preparation-only", action="store_true")
    args = parser.parse_args()
    result = verify_preparation(args.artifact_dir.resolve()) if args.preparation_only else verify_complete(args.artifact_dir.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if all(
        value is True or value == 0
        for key, value in result.items()
        if key.endswith("PASS") or key.endswith("COUNT") or key in {"LOCK_GRAPH_ACYCLIC"}
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
