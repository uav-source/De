"""Shared non-formal helpers for Phase A v1.1 runner tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from zero_perturbation.backend_phase_a_protocol import (
    canonical_json_sha256,
    file_sha256,
    load_backend_phase_a_protocol,
)
from zero_perturbation.backend_phase_a_v1_1 import (
    V1_1_DOCUMENT_SHA256,
    V1_1_PROTOCOL_SHA256,
    implementation_hashes,
    execute_fixture_chain,
)


ROOT = Path(__file__).resolve().parents[1]
V1_ARTIFACT = ROOT / "artifacts/current/zero_perturbation_backend_phase_a_lock"
FIXTURE = ROOT / "tests/data/backend_phase_a_runner_fixture"


def fixture_points() -> np.ndarray:
    contract = json.loads((FIXTURE / "fixture_contract.json").read_text())
    point_path = FIXTURE / contract["point_file"]
    assert file_sha256(point_path) == contract["point_file_sha256"]
    points = np.loadtxt(point_path, comments="#", dtype=np.float64)
    assert points.shape == (contract["point_count"], 3)
    return points


def write_valid_lock(path: Path) -> dict[str, Any]:
    base = load_backend_phase_a_protocol(ROOT)
    implementation = implementation_hashes(ROOT)
    snapshots = V1_ARTIFACT / "planned_snapshots.csv"
    trials = V1_ARTIFACT / "planned_trials.csv"
    payload = {
        "schema_version": "backend_phase_a_v1_1_protocol_lock_v1",
        "protocol_sha256": V1_1_PROTOCOL_SHA256,
        "protocol_document_sha256": V1_1_DOCUMENT_SHA256,
        "base_protocol_sha256": base.source_sha256,
        "planned_snapshots_path": snapshots.relative_to(ROOT).as_posix(),
        "planned_snapshots_sha256": file_sha256(snapshots),
        "planned_trials_path": trials.relative_to(ROOT).as_posix(),
        "planned_trials_sha256": file_sha256(trials),
        "open3d_parameter_sha256": base.data["open3d_parameter_contract"][
            "canonical_sha256"
        ],
        "pcl_parameter_sha256": base.data["pcl_parameter_contract"][
            "canonical_sha256"
        ],
        "implementation": implementation,
        "implementation_sha256": canonical_json_sha256(implementation),
        "formal_execution_authorized": True,
        "BACKEND_PHASE_A_V1_1_PROTOCOL_LOCK_PASS": True,
        "BACKEND_PHASE_A_V1_1_RUN_AUTHORIZED": True,
    }
    document = {
        **payload,
        "lock_payload_sha256": canonical_json_sha256(payload),
    }
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return document


def fake_result(backend: str):
    def run(**arguments: Any) -> dict[str, Any]:
        checksums = arguments["checksums"]
        return {
            "schema_version": "backend_phase_a_v1_1_fixture_trial_result_v1",
            "planned_trial_id": arguments["trial_id"],
            "trial_id": arguments["trial_id"],
            "snapshot_id": arguments["snapshot_id"],
            "backend": backend,
            "protocol_sha256": arguments["protocol_sha256"],
            "implementation_sha256": arguments["implementation_sha256"],
            "is_formal_phase_a": False,
            "fixture_only": True,
            **checksums,
            "final_transform": np.eye(4).tolist(),
            "final_transform_finite": True,
            "finite_output": True,
            "translation_update_m": 0.0,
            "rotation_update_rad": 0.0,
            "solver_failure_reasons": [],
            "solver_failed": False,
            "failure_classifications": [],
            "exception": None,
        }

    return run


@pytest.fixture(scope="session")
def actual_fixture_run(tmp_path_factory):
    output = tmp_path_factory.mktemp("phase-a-v1-1-actual-fixture")
    manifest = execute_fixture_chain(
        root=ROOT,
        points=fixture_points(),
        output_dir=output,
    )
    results = {}
    for path in (output / "trials").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        results[payload["backend"]] = payload
    return {"output": output, "manifest": manifest, "results": results}
