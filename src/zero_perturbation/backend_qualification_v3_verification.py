"""Independent verification for PCL Backend Qualification v3 artifacts."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .rotation_metrics import rotation_metric_audit


PROTOCOL_SHA256 = "79716b374ea7531fc945fb6df4ccedb8ca7a5ce9553cf3b7b6c769ed63b0cc24"
V2_COMMIT = "f43c11f615a9b03c9e20bd80fcbf2b6c604b5d35"
V3_PROTOCOL_LOCK_COMMIT = "a8eec0492a1e48844e6cad56d1d065e9f6f54d0e"
V2_BUNDLE_SHA256 = "7d7e53669718a61e099182440b7a340bc4cab109a24bb9fd2fab36bce77dacc2"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sums(directory: Path) -> list[str]:
    sums = directory / "SHA256SUMS"
    if not sums.is_file():
        return ["missing SHA256SUMS"]
    errors: list[str] = []
    declared: set[str] = set()
    for line in sums.read_text(encoding="utf-8").splitlines():
        try:
            expected, relative = line.split("  ", 1)
        except ValueError:
            errors.append(f"malformed checksum line: {line}")
            continue
        declared.add(relative)
        path = directory / relative
        if not path.is_file():
            errors.append(f"missing checksum path: {relative}")
        elif file_sha256(path) != expected:
            errors.append(f"checksum mismatch: {relative}")
    actual = {
        path.relative_to(directory).as_posix()
        for path in directory.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if actual != declared:
        errors.append("SHA256 inventory mismatch")
    return errors


def close(actual: float, expected: float, tolerance: float = 1.0e-15) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tolerance)


def _git_tag_target(repository: Path, tag: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"{tag}^{{}}"],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def verify_backend_qualification_v3(root: str | Path) -> dict[str, Any]:
    repository = Path(root).resolve()
    artifact = repository / "artifacts/current/zero_perturbation_backend_qualification_v3"
    errors = verify_sums(artifact)

    protocol_path = repository / "configs/zero_perturbation/backend_qualification_v3.yaml"
    if file_sha256(protocol_path) != PROTOCOL_SHA256:
        errors.append("v3 protocol hash changed")
    protocol = yaml.safe_load(protocol_path.read_text(encoding="utf-8"))
    if protocol["protocol"]["protocol_type"] != "rotation_metric_validity_requalification":
        errors.append("v3 protocol type changed")
    if protocol["protocol"]["allowed_microtests_only"] != [
        "NONDEGENERATE_IDENTITY",
        "KNOWN_SMALL_TRANSFORM",
        "PLANAR_DEGENERACY_DIAGNOSTIC",
    ]:
        errors.append("v3 allowed test list changed")

    if _git_tag_target(
        repository, "archive/zero-perturbation-pcl-backend-qualification-v2-fail"
    ) != V2_COMMIT:
        errors.append("v2 archive tag target mismatch")
    if _git_tag_target(
        repository,
        "archive/zero-perturbation-pcl-backend-qualification-v3-protocol-lock",
    ) != V3_PROTOCOL_LOCK_COMMIT:
        errors.append("v3 protocol lock tag target mismatch")
    bundle = Path(
        "/home/lj/zero_perturbation_pcl_backend_qualification_v2_fail_f43c11f.bundle"
    )
    if not bundle.is_file() or file_sha256(bundle) != V2_BUNDLE_SHA256:
        errors.append("v2 bundle missing or hash mismatch")

    fixture_audit = json.loads((artifact / "fixture_checksum_audit.json").read_text())
    for item in fixture_audit["files"]:
        path = repository / item["path"]
        actual = file_sha256(path)
        if actual != item["expected_sha256"] or item["actual_sha256"] != actual:
            errors.append(f"fixture hash mismatch: {item['name']}")
    if not fixture_audit["all_hashes_pass"]:
        errors.append("fixture checksum audit did not pass")

    results = {
        name: json.loads((artifact / f"test_{name.lower()}_result.json").read_text())
        for name in ("A", "B", "C")
    }
    if not all(result["microtest_pass"] is True for result in results.values()):
        errors.append("not all v3 microtests pass")

    a = results["A"]
    ap = a["cli_result"]
    if not (
        ap["has_converged_raw"] is True
        and ap["final_transform_finite"] is True
        and ap["fitness_finite"] is True
        and ap["translation_update_norm_m"] <= 1.0e-8
        and a["formal_rotation_error_rad"] <= 1.0e-8
        and ap["correspondence_count"] > 0
        and ap["source_normal_zero_count"] == 0
        and ap["source_normal_nan_count"] == 0
        and ap["target_normal_zero_count"] == 0
        and ap["target_normal_nan_count"] == 0
        and a["ROTATION_MATRIX_QUALITY_PASS"] is True
        and a["ROTATION_METRIC_CROSSCHECK_PASS"] is True
    ):
        errors.append("Test A gate recomputation failed")

    b = results["B"]
    bp = b["cli_result"]
    truth = np.asarray(b["truth_source_to_target_transform_4x4"], dtype=np.float64)
    estimate = np.asarray(
        b["estimated_source_to_target_transform_4x4"], dtype=np.float64
    )
    independent_translation = float(np.linalg.norm(estimate[:3, 3] - truth[:3, 3]))
    independent_rotation = rotation_metric_audit(estimate[:3, :3], truth[:3, :3])
    if not close(independent_translation, b["translation_error_to_truth_m"]):
        errors.append("Test B translation error does not reproduce")
    if not close(
        independent_rotation["rotation_error_rad"],
        b["python_projected_rotation_error_rad"],
    ):
        errors.append("Test B Python projected rotation error does not reproduce")
    if not (
        independent_translation <= 1.0e-4
        and b["rotation_error_to_truth_rad"] <= 1.0e-4
        and bp["has_converged_raw"] is True
        and bp["final_transform_finite"] is True
        and bp["fitness_finite"] is True
        and b["truth_passed_to_cli"] is False
        and b["truth_argument_passed_to_registration_cli"] is False
        and b["ROTATION_MATRIX_QUALITY_PASS"] is True
        and b["ROTATION_METRIC_CROSSCHECK_PASS"] is True
        and b["rotation_metric_abs_difference_rad"] <= 1.0e-10
    ):
        errors.append("Test B gate recomputation failed")

    c = results["C"]["cli_result"]
    if not (
        c["point_cloud_rank"] == 2
        and c["point_to_plane_jacobian_rank"] < 6
        and c["rank_deficient"] is True
        and c["condition_status"] == "RANK_DEFICIENT"
        and c["failure_reason"] == "RANK_DEFICIENT_DIAGNOSTIC"
    ):
        errors.append("Test C diagnostic recomputation failed")

    audit = json.loads((artifact / "rotation_metric_audit.json").read_text())
    for field in (
        "R_est_transpose_R_est",
        "orthogonality_defect_fro",
        "determinant",
        "raw_trace_acos_argument",
        "raw_trace_acos_rotation_error_rad",
        "nearest_so3_projection",
        "projection_correction_fro",
        "projected_rotation_error_rad",
        "maximum_elementwise_error_to_truth",
    ):
        if field not in audit:
            errors.append(f"rotation audit field missing: {field}")
    if not (
        audit["ROTATION_MATRIX_QUALITY_PASS"] is True
        and audit["ROTATION_METRIC_CROSSCHECK_PASS"] is True
        and audit["rotation_metric_abs_difference_rad"] <= 1.0e-10
        and audit["raw_trace_acos_rotation_error_rad"] > 1.0e-4
        and audit["projected_rotation_error_rad"] < 1.0e-8
        and audit["raw_trace_acos_used_as_formal_gate"] is False
        and audit["smaller_value_selection_used"] is False
    ):
        errors.append("rotation metric audit decision is invalid")

    differences = json.loads((artifact / "parameter_diff_v2_v3.json").read_text())
    for field in (
        "pcl_version_difference_count",
        "backend_contract_difference_count",
        "icp_parameter_difference_count",
        "normal_parameter_difference_count",
        "fixture_difference_count",
        "truth_transform_difference_count",
        "unapproved_difference_count",
    ):
        if differences[field] != 0:
            errors.append(f"nonzero v2/v3 difference: {field}")
    if differences["allowed_difference_categories"] != [
        "rotation metric implementation",
        "diagnostic output precision",
        "v3 tests",
        "v3 protocol/reporting",
    ]:
        errors.append("allowed v3 difference categories changed")

    decision = json.loads((artifact / "final_decision.json").read_text())
    for field in (
        "V3_TEST_A_NONDEGENERATE_IDENTITY_PASS",
        "V3_TEST_B_KNOWN_SMALL_TRANSFORM_PASS",
        "V3_TEST_C_PLANAR_DEGENERACY_DIAGNOSTIC_PASS",
        "ROTATION_MATRIX_QUALITY_PASS",
        "ROTATION_METRIC_CROSSCHECK_PASS",
        "PCL_BACKEND_IMPLEMENTATION_VALID",
        "PCL_BACKEND_PHASE_A_QUALIFICATION_AUTHORIZED",
    ):
        if decision[field] is not True:
            errors.append(f"v3 decision false: {field}")
    preserved = decision["v2_preserved"]
    if preserved != {
        "Test_A": "PASS",
        "Test_B": "FAIL",
        "Test_C": "PASS",
        "PCL_BACKEND_IMPLEMENTATION_VALID": False,
        "PCL_BACKEND_PHASE_A_QUALIFICATION_AUTHORIZED": False,
        "V2_RAW_TRACE_ACOS_ROTATION_GATE_FAIL": True,
        "V2_ROTATION_MATRIX_NEAR_SO3": True,
        "V2_METRIC_VALIDITY_REQUIRES_AUDIT": True,
    }:
        errors.append("v2 decision was not preserved exactly")
    false_scope_fields = (
        "phase_a_executed",
        "phase_b_executed",
        "formal_pcl_parameters_modified",
        "pcl_version_changed",
        "truth_passed_to_registration_cli",
        "third_backend_substitution_attempted",
        "parameter_rescue_attempted",
        "git_push_performed",
        "open3d_modified",
        "native_modified",
        "odi_modified",
        "d50_restored",
        "fast_lio2_modified",
        "scene_generator_modified",
    )
    if any(decision[field] for field in false_scope_fields):
        errors.append("one or more scope firewalls failed")
    if decision["seed_access_count"] != 0:
        errors.append("seed access count is nonzero")
    if decision["final_worktree_clean_after_commit"] is not True:
        errors.append("final clean-worktree requirement is not asserted")

    manifest = json.loads((artifact / "run_manifest.json").read_text())
    if manifest["microtest_execution_count"] != {"A": 1, "B": 1, "C": 1}:
        errors.append("actual microtest execution count is not one each")
    if not (
        manifest["ctest_invocation_count"] == 2
        and manifest["qualification_ctest_success_count"] == 1
        and manifest["infrastructure_preflight_failure_count"] == 1
        and manifest["microtest_registration_execution_count_before_preflight_repair"]
        == {"A": 0, "B": 0, "C": 0}
    ):
        errors.append("CTest preflight/qualification execution accounting is invalid")
    if any(
        manifest[field]
        for field in (
            "phase_a_executed",
            "phase_b_executed",
            "development_run_executed",
            "confirmatory_run_executed",
            "open3d_modified",
            "native_modified",
            "odi_modified",
            "d50_restored",
            "fast_lio2_modified",
            "scene_generator_modified",
            "formal_pcl_parameters_modified",
            "git_push_performed",
        )
    ):
        errors.append("run manifest scope firewall failed")
    if manifest["seed_access_count"] != 0:
        errors.append("run manifest seed access count is nonzero")
    if not (
        manifest["full_python_test_executed"] is True
        and manifest["full_python_test_status"] == "PASSED"
        and manifest["frozen_environment_full_python_execution_count"] == 1
        and manifest["full_python_test_pass_count"] == 1559
        and manifest["full_python_test_skip_count"] == 1
        and manifest["full_python_test_failure_count"] == 0
    ):
        errors.append("final frozen-environment full Python test status is invalid")

    cmake = (repository / "tools/pcl_point_to_plane/CMakeLists.txt").read_text()
    if cmake.count("NAME pcl_v3_") != 3 or "PASS_REGULAR_EXPRESSION" in cmake:
        errors.append("CTest is not exactly three structured v3 tests")
    cli = (repository / "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp").read_text()
    header = (repository / "tools/pcl_point_to_plane/rotation_metric_v3.hpp").read_text()
    if "ROTATION_MATRIX_QUALITY_FAILED" not in cli:
        errors.append("CLI rotation matrix quality failure is not split")
    for source_fragment in (
        "Eigen::JacobiSVD",
        "reflection_correction(2, 2)",
        "std::atan2",
        "kOrthogonalityDefectMaximum = 1.0e-5",
        "kProjectionCorrectionMaximum = 1.0e-5",
    ):
        if source_fragment not in header:
            errors.append(f"rotation implementation fragment missing: {source_fragment}")

    report = (artifact / "backend_qualification_v3_report.md").read_text()
    for heading in (
        "## Decision",
        "## Immutable v2 result and archive",
        "## Full-precision v2 rotation audit",
        "## Test A — NONDEGENERATE_IDENTITY",
        "## Test B — KNOWN_SMALL_TRANSFORM",
        "## Test C — PLANAR_DEGENERACY_DIAGNOSTIC",
        "## Frozen inputs, parameters, and scope",
    ):
        if heading not in report:
            errors.append(f"report heading missing: {heading}")

    return {
        "schema_version": "pcl_backend_qualification_v3_verification_v1",
        "verification_pass": not errors,
        "error_count": len(errors),
        "errors": errors,
        "microtest_pass_count": sum(
            result["microtest_pass"] is True for result in results.values()
        ),
        "pcl_backend_implementation_valid": decision[
            "PCL_BACKEND_IMPLEMENTATION_VALID"
        ],
        "phase_a_authorized": decision[
            "PCL_BACKEND_PHASE_A_QUALIFICATION_AUTHORIZED"
        ],
        "phase_a_executed": decision["phase_a_executed"],
        "phase_b_executed": decision["phase_b_executed"],
        "seed_access_count": decision["seed_access_count"],
    }


__all__ = ["PROTOCOL_SHA256", "verify_backend_qualification_v3"]
