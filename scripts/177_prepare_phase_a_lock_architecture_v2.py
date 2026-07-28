#!/usr/bin/env python3
"""Project and publish the pre-implementation Phase A lock layers."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.phase_a_lock_architecture_v2 import (
    ARTIFACT_RELATIVE,
    build_snapshot_binding,
    legacy_field_classification,
    lock_dependency_graph,
)
from zero_perturbation.phase_a_scientific_lock_v2 import (
    expected_scientific_payload,
    scientific_lock_implementation_fields,
    scientific_projection_diff,
    validate_scientific_lock,
)
from zero_perturbation.phase_a_trial_result_schema import canonical_json_bytes
from zero_perturbation.phase_a_trial_result_writer import atomic_write_bytes


def _write_json(path: Path, value: dict) -> None:
    atomic_write_bytes(path, canonical_json_bytes(value), replace=False)


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "json_path", "value_summary", "classification", "reason",
        "target_v2_lock", "retained_unchanged", "legacy_conflict_risk",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_write_bytes(path, stream.getvalue().encode("utf-8"), replace=False)


def prepare(directory: Path) -> dict:
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError("architecture artifact directory must be empty")
    directory.mkdir(parents=True, exist_ok=True)
    scientific = expected_scientific_payload(ROOT)
    validate_scientific_lock(scientific, root=ROOT)
    projection = scientific_projection_diff(scientific, root=ROOT)
    snapshot = build_snapshot_binding(ROOT)
    graph = lock_dependency_graph()
    rows, classification = legacy_field_classification(ROOT)
    _write_csv(directory / "legacy_lock_field_classification.csv", rows)
    _write_json(directory / "legacy_lock_field_classification_summary.json", classification)
    _write_json(directory / "lock_dependency_graph.json", graph)
    _write_json(directory / "phase_a_scientific_protocol_lock_v2.json", scientific)
    _write_json(directory / "scientific_protocol_projection_diff.json", projection)
    _write_json(directory / "snapshot_lock_binding_v2.json", snapshot)
    result = {
        **classification,
        "LOCK_GRAPH_ACYCLIC": graph["LOCK_GRAPH_ACYCLIC"],
        "LOCK_GRAPH_DUPLICATE_BINDING_COUNT": graph["LOCK_GRAPH_DUPLICATE_BINDING_COUNT"],
        "SCIENTIFIC_LOCK_IMPLEMENTATION_FIELD_COUNT": len(scientific_lock_implementation_fields(scientific)),
        "SCIENTIFIC_PROTOCOL_PROJECTION_PASS": projection["SCIENTIFIC_PROTOCOL_PROJECTION_PASS"],
        "SNAPSHOT_LOCK_V2_BINDING_PASS": snapshot["SNAPSHOT_LOCK_V2_BINDING_PASS"],
        "schema_version": "phase_a_lock_architecture_v2_preparation_v1",
    }
    _write_json(directory / "lock_architecture_v2_preparation.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=ROOT / ARTIFACT_RELATIVE)
    args = parser.parse_args()
    print(json.dumps(prepare(args.artifact_dir.resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
