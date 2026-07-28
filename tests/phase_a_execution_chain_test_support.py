from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from zero_perturbation.phase_a_execution_chain_audit import (
    AUDIT_LOCK_RELATIVE,
    execute_fixture_audit_trials,
)
from zero_perturbation.phase_a_execution_chain_fixture import (
    FIXTURE_LOCK_RELATIVE,
    FIXTURE_PLAN_RELATIVE,
)
from zero_perturbation.phase_a_stage1_analysis import analyze_phase_a_stage1_fixture
from zero_perturbation.phase_a_stage1_independent_verifier import (
    independently_verify_phase_a_stage1_fixture,
)
from zero_perturbation.phase_a_stage1_publisher import publish_phase_a_execution_chain_audit
from zero_perturbation.phase_a_trial_result_schema import OPEN3D_BACKEND, PCL_BACKEND


ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOCK = ROOT / AUDIT_LOCK_RELATIVE
FIXTURE_LOCK = ROOT / FIXTURE_LOCK_RELATIVE
FIXTURE_PLAN = ROOT / FIXTURE_PLAN_RELATIVE
SHA = "a" * 64


def normal_statistics() -> dict:
    return {
        "finite_count": 806,
        "nan_count": 0,
        "norm_max": 1.0,
        "norm_median": 1.0,
        "norm_min": 1.0,
        "zero_count": 0,
    }


def sample_result(backend: str = OPEN3D_BACKEND) -> dict:
    diagnostics = (
        {"correspondence_set_size": 806, "fitness": 1.0, "inlier_rmse": 0.0}
        if backend == OPEN3D_BACKEND
        else {
            "correspondence_count": 806,
            "exit_code": 0,
            "fitness_score": 0.0,
            "has_converged_raw": True,
            "iteration_count": 1,
            "pcl_cli_sha256": SHA,
            "pcl_version": "1.15.1",
            "source_normal_statistics": normal_statistics(),
            "target_normal_statistics": normal_statistics(),
        }
    )
    return {
        "backend": backend,
        "backend_diagnostics": diagnostics,
        "condition": "FIXTURE_IDENTITY",
        "failure_classification": "NONE",
        "failure_detail": None,
        "final_transform_4x4": np.eye(4).tolist(),
        "finite_output": True,
        "implementation_sha256": SHA,
        "orthogonality_defect_fro": 0.0,
        "planned_trial_id": f"fixture-audit-v1/identity/{backend}",
        "projection_correction_fro": 0.0,
        "protocol_sha256": SHA,
        "raw_rotation_determinant": 1.0,
        "raw_rotation_finite": True,
        "reference_pose_checksum": SHA,
        "rotation_update_rad": 0.0,
        "runtime_ms": 1.0,
        "scene_variant": "AUDIT_ASYMMETRIC_3D",
        "schema_version": "phase_a_trial_result_v1",
        "snapshot_checksum": SHA,
        "snapshot_id": "fixture-audit-v1/identity",
        "snapshot_lock_sha256": SHA,
        "solver_failure": False,
        "source_checksum": SHA,
        "target_checksum": SHA,
        "translation_update_m": 0.0,
    }


def fake_backend_result(*, fixture, common) -> dict:
    backend = common["backend"]
    failure = fixture.condition == "FIXTURE_NO_CORRESPONDENCE"
    diagnostics = (
        {
            "correspondence_set_size": 0 if failure else len(fixture.source),
            "fitness": 0.0 if failure else 1.0,
            "inlier_rmse": 0.0,
        }
        if backend == OPEN3D_BACKEND
        else {
            "correspondence_count": 0 if failure else len(fixture.source),
            "exit_code": 0,
            "fitness_score": 0.0,
            "has_converged_raw": not failure,
            "iteration_count": 1,
            "pcl_cli_sha256": SHA,
            "pcl_version": "1.15.1",
            "source_normal_statistics": normal_statistics(),
            "target_normal_statistics": normal_statistics(),
        }
    )
    return {
        **common,
        "backend_diagnostics": diagnostics,
        "failure_classification": "NO_CORRESPONDENCES" if failure else "NONE",
        "failure_detail": "expected separated fixture" if failure else None,
        "final_transform_4x4": fixture.reference.tolist(),
        "finite_output": True,
        "orthogonality_defect_fro": float(
            np.linalg.norm(fixture.reference[:3, :3].T @ fixture.reference[:3, :3] - np.eye(3))
        ),
        "projection_correction_fro": 0.0,
        "raw_rotation_determinant": float(np.linalg.det(fixture.reference[:3, :3])),
        "raw_rotation_finite": True,
        "rotation_update_rad": 0.0,
        "runtime_ms": 1.0,
        "solver_failure": failure,
        "translation_update_m": 0.0,
    }


FAKE_HOOKS = {OPEN3D_BACKEND: fake_backend_result, PCL_BACKEND: fake_backend_result}


@pytest.fixture(scope="session")
def actual_execution_chain(tmp_path_factory):
    output = tmp_path_factory.mktemp("phase-a-execution-chain-actual") / "run"
    manifest = execute_fixture_audit_trials(
        root=ROOT,
        protocol_lock=AUDIT_LOCK,
        fixture_lock=FIXTURE_LOCK,
        run_id="pytest-actual-fixture-chain",
        output_dir=output,
    )
    analysis = analyze_phase_a_stage1_fixture(
        run_dir=output,
        fixture_plan=FIXTURE_PLAN,
        fixture_lock=FIXTURE_LOCK,
    )
    verifier = independently_verify_phase_a_stage1_fixture(
        run_dir=output,
        fixture_plan=FIXTURE_PLAN,
        fixture_lock=FIXTURE_LOCK,
        analysis_output=analysis,
    )
    return {"analysis": analysis, "manifest": manifest, "output": output, "verifier": verifier}


@pytest.fixture(scope="session")
def published_execution_chain(actual_execution_chain, tmp_path_factory):
    artifact = tmp_path_factory.mktemp("phase-a-execution-chain-artifact") / "artifact"
    resume = {
        "FINAL_TRIAL_COUNT_AFTER_RESUME": 6,
        "RESUMED_AND_FRESH_RESULT_EQUIVALENT": True,
        "RESUME_REEXECUTED_VALID_RESULT_COUNT": 0,
        "RESUME_SKIPPED_VALID_RESULT_COUNT": 2,
    }
    tamper = {"TAMPERED_RESULT_REJECTED": True}
    publication = publish_phase_a_execution_chain_audit(
        artifact_dir=artifact,
        analysis=actual_execution_chain["analysis"],
        verification=actual_execution_chain["verifier"],
        fixture_run_manifest=actual_execution_chain["manifest"],
        resume_audit=resume,
        tamper_audit=tamper,
        audit_protocol_lock=AUDIT_LOCK,
    )
    return {"artifact": artifact, "publication": publication}


def load_results(output: Path) -> list[dict]:
    manifest = json.loads((output / "raw_result_manifest.json").read_text())
    return [
        json.loads((output / "raw_results" / entry["path"]).read_text())
        for _, entry in sorted(manifest["results"].items())
    ]
