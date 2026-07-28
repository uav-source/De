"""Independent verification of the stopped PCL backend qualification v2 artifact."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import yaml


PROTOCOL_SHA256 = "e70595eecc0ac41cf2e04e843ce1d3e2ca31c1caf05757be1fc28fd4647e3709"
V1_SOURCE_SHA256 = "b34c107bbb291a99c139fdd7787bde5101911d7e0a506bb0bba2e1a0f4c40a10"
V1_TARGET_SHA256 = "af6967943369548ef7f2d31b5e759e25dc277bb15e6471f086b4e450c86d6a92"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def verify_sums(directory: Path) -> list[str]:
    errors: list[str] = []
    sums = directory / "SHA256SUMS"
    if not sums.is_file():
        return [f"missing SHA256SUMS: {directory}"]
    declared: set[str] = set()
    for line in sums.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        declared.add(relative)
        path = directory / relative
        if not path.is_file():
            errors.append(f"missing checksum path: {relative}")
        elif file_sha256(path) != digest:
            errors.append(f"checksum mismatch: {relative}")
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if declared != actual:
        errors.append(f"SHA256 inventory mismatch: {directory}")
    return errors


def raw_rotation_error(truth: np.ndarray, estimate: np.ndarray) -> float:
    delta = np.linalg.inv(truth) @ estimate
    cosine = float(np.clip((np.trace(delta[:3, :3]) - 1.0) * 0.5, -1.0, 1.0))
    return float(math.acos(cosine))


def verify_backend_qualification_v2(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    artifact = repository / "artifacts/current/zero_perturbation_backend_qualification_v2"
    reports = repository / "reports/zero_perturbation_pcl_environment_v2"
    errors: list[str] = []
    errors.extend(verify_sums(artifact))
    errors.extend(verify_sums(reports))

    protocol_path = repository / "configs/zero_perturbation/backend_qualification_v2.yaml"
    if file_sha256(protocol_path) != PROTOCOL_SHA256:
        errors.append("v2 protocol hash changed")
    protocol = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    if protocol["v1_preserved_result"]["PCL_V1_PLANAR_IDENTITY_SMOKE"] != "FAIL":
        errors.append("v1 failure was rewritten")
    if protocol["v1_preserved_result"]["reclassification"][
        "PCL_BACKEND_QUALIFICATION"
    ] != "NOT_EVALUATED":
        errors.append("v1 qualification reclassification changed")

    if file_sha256(repository / "tests/data/pcl_backend/identity_source.pcd") != V1_SOURCE_SHA256:
        errors.append("v1 source fixture changed")
    if file_sha256(repository / "tests/data/pcl_backend/identity_target.pcd") != V1_TARGET_SHA256:
        errors.append("v1 target fixture changed")
    old_smoke = (
        repository / "reports/zero_perturbation_pcl_environment/smoke_test.txt"
    ).read_text(encoding="utf-8")
    if '"has_converged":false' not in old_smoke or '"finite_output":false' not in old_smoke:
        errors.append("v1 failed smoke evidence changed")

    results = {
        name: json.loads((artifact / f"raw/test_{name}_result.json").read_text())
        for name in ("a", "b", "c")
    }
    if results["a"]["microtest_pass"] is not True:
        errors.append("Test A result is not PASS")
    a = results["a"]["cli_result"]
    if not (
        a["has_converged_raw"] is True
        and a["final_transform_finite"] is True
        and a["fitness_finite"] is True
        and a["translation_update_norm_m"] <= 1.0e-8
        and a["rotation_update_norm_rad"] <= 1.0e-8
        and a["correspondence_count"] > 0
        and a["source_normal_nan_count"] == 0
        and a["source_normal_zero_count"] == 0
        and a["target_normal_nan_count"] == 0
        and a["target_normal_zero_count"] == 0
    ):
        errors.append("Test A independent gate recomputation failed")

    b = results["b"]
    truth = np.asarray(b["truth_source_to_target_transform_4x4"], dtype=np.float64)
    estimate = np.asarray(
        b["estimated_source_to_target_transform_4x4"], dtype=np.float64
    )
    rotation_error = raw_rotation_error(truth, estimate)
    if not math.isclose(rotation_error, b["rotation_error_to_truth_rad"], abs_tol=1.0e-15):
        errors.append("Test B rotation error did not independently reproduce")
    if rotation_error <= 1.0e-4 or b["microtest_pass"] is not False:
        errors.append("Test B stopped failure changed")
    if not (
        b["translation_error_to_truth_m"] <= 1.0e-4
        and b["cli_result"]["has_converged_raw"] is True
        and b["cli_result"]["final_transform_finite"] is True
        and b["cli_result"]["fitness_finite"] is True
    ):
        errors.append("Test B non-rotation gates changed")

    c = results["c"]
    if c["microtest_pass"] is not True:
        errors.append("Test C diagnostic is not PASS")
    c_payload = c["cli_result"]
    if not (
        c_payload["point_cloud_rank"] == 2
        and c_payload["point_to_plane_jacobian_rank"] < 6
        and c_payload["rank_deficient"] is True
        and c_payload["failure_reason"] == "RANK_DEFICIENT_DIAGNOSTIC"
    ):
        errors.append("Test C rank-deficiency expectation changed")
    expected_v1_eigenvalues = np.asarray([0.0, 0.0, 0.0, 3.36, 3.36, 64.0])
    if not np.allclose(
        c_payload["point_to_plane_hessian_eigenvalues"],
        expected_v1_eigenvalues,
        atol=1.0e-6,
        rtol=0.0,
    ):
        errors.append("v1 Hessian eigenvalues changed")

    decision = json.loads((artifact / "final_decision.json").read_text())
    expected_decision = {
        "PCL_DEPENDENCY_READY": True,
        "PCL_CLI_COMPILED": True,
        "PCL_V1_PLANAR_IDENTITY_SMOKE": "FAIL",
        "PCL_V1_SMOKE_FIXTURE_DEGENERATE": True,
        "PCL_BACKEND_QUALIFICATION": "NOT_EVALUATED",
        "V2_TEST_A_NONDEGENERATE_IDENTITY_PASS": True,
        "V2_TEST_B_KNOWN_SMALL_TRANSFORM_PASS": False,
        "V2_TEST_C_PLANAR_DEGENERACY_DIAGNOSTIC_PASS": True,
        "PCL_BACKEND_IMPLEMENTATION_VALID": False,
        "PCL_BACKEND_PHASE_A_QUALIFICATION_AUTHORIZED": False,
        "phase_a_executed": False,
        "phase_b_executed": False,
        "seed_access_count": 0,
        "formal_pcl_parameters_modified": False,
        "pcl_version_changed": False,
        "open3d_modified": False,
        "native_modified": False,
        "third_backend_substitution_attempted": False,
        "parameter_rescue_attempted": False,
        "microtest_rerun_after_failure": False,
        "git_push_performed": False,
    }
    for field, expected in expected_decision.items():
        if decision.get(field) != expected:
            errors.append(f"decision mismatch: {field}")

    manifest = json.loads((artifact / "run_manifest.json").read_text())
    if manifest["ctest_execution_count"] != 1 or manifest["microtest_execution_count"] != {
        "A": 1,
        "B": 1,
        "C": 1,
    }:
        errors.append("microtests were rerun or omitted")
    if any(
        manifest[field]
        for field in (
            "phase_a_executed",
            "phase_b_executed",
            "development_run_executed",
            "confirmatory_run_executed",
            "v1_reports_modified",
            "v1_fixture_modified",
            "open3d_modified",
            "native_modified",
            "formal_pcl_parameters_modified",
            "git_push_performed",
        )
    ):
        errors.append("scope/firewall manifest changed")

    archived_cmake = subprocess.run(
        [
            "git",
            "show",
            "f43c11f615a9b03c9e20bd80fcbf2b6c604b5d35:tools/pcl_point_to_plane/CMakeLists.txt",
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    cmake = archived_cmake.stdout
    if archived_cmake.returncode != 0:
        errors.append("cannot read archived v2 CTest definition")
    if cmake.count("NAME pcl_v2_") != 3 or "PASS_REGULAR_EXPRESSION" in cmake:
        errors.append("archived CTest does not contain exactly three structured v2 tests")
    archived_cli = subprocess.run(
        [
            "git",
            "show",
            "f43c11f615a9b03c9e20bd80fcbf2b6c604b5d35:tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp",
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    cli_source = archived_cli.stdout
    if archived_cli.returncode != 0:
        errors.append("cannot read archived v2 CLI definition")
    if "pcl_icp_did_not_converge_or_nonfinite" in cli_source:
        errors.append("v1 combined failure reason remains in v2 CLI")

    report = (artifact / "backend_qualification_v2_report.md").read_text()
    for heading in (
        "## Decision",
        "## v1 fixture rank and reclassification",
        "## v2 nondegenerate fixture and Hessian",
        "## Source and target normal statistics",
        "## Test A — NONDEGENERATE_IDENTITY",
        "## Test B — KNOWN_SMALL_TRANSFORM",
        "## Test C — PLANAR_DEGENERACY_DIAGNOSTIC",
        "## Scope and compliance",
    ):
        if heading not in report:
            errors.append(f"report section missing: {heading}")

    return {
        "schema_version": "pcl_backend_qualification_v2_verification_v1",
        "verification_pass": not errors,
        "error_count": len(errors),
        "errors": errors,
        "microtest_pass_count": 2,
        "microtest_failure_count": 1,
        "pcl_backend_implementation_valid": False,
        "phase_a_authorized": False,
        "phase_a_executed": False,
        "phase_b_executed": False,
    }


__all__ = ["PROTOCOL_SHA256", "verify_backend_qualification_v2"]
