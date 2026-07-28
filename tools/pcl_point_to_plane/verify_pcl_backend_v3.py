#!/usr/bin/env python3
"""Structured verifier for one frozen PCL backend qualification v3 microtest."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ROTATION_METRIC_PATH = REPOSITORY_ROOT / "src/zero_perturbation/rotation_metrics.py"
ROTATION_METRIC_SPEC = importlib.util.spec_from_file_location(
    "pcl_backend_v3_independent_rotation_metrics", ROTATION_METRIC_PATH
)
if ROTATION_METRIC_SPEC is None or ROTATION_METRIC_SPEC.loader is None:
    raise RuntimeError("cannot load independent Python rotation metric implementation")
ROTATION_METRIC_MODULE = importlib.util.module_from_spec(ROTATION_METRIC_SPEC)
ROTATION_METRIC_SPEC.loader.exec_module(ROTATION_METRIC_MODULE)
rotation_metric_audit = ROTATION_METRIC_MODULE.rotation_metric_audit


TESTS = {
    "NONDEGENERATE_IDENTITY",
    "KNOWN_SMALL_TRANSFORM",
    "PLANAR_DEGENERACY_DIAGNOSTIC",
}
REQUIRED_FIELDS = {
    "has_converged_raw",
    "final_transform_finite",
    "fitness_finite",
    "finite_output",
    "qualification_pass",
    "iteration_count",
    "correspondence_count",
    "source_normal_finite_count",
    "source_normal_zero_count",
    "source_normal_nan_count",
    "source_normal_norm_min",
    "source_normal_norm_median",
    "source_normal_norm_max",
    "target_normal_finite_count",
    "target_normal_zero_count",
    "target_normal_nan_count",
    "target_normal_norm_min",
    "target_normal_norm_median",
    "target_normal_norm_max",
    "point_cloud_rank",
    "point_to_plane_jacobian_rank",
    "point_to_plane_hessian_eigenvalues",
    "condition_status",
    "rank_deficient",
    "failure_reason",
    "raw_rotation_finite",
    "raw_rotation_determinant_positive",
    "raw_rotation_3x3",
    "R_est_transpose_R_est",
    "orthogonality_defect_fro",
    "determinant",
    "raw_trace_acos_argument",
    "raw_trace_acos_rotation_error_rad",
    "nearest_so3_projection",
    "projected_determinant",
    "projection_correction_fro",
    "singular_values",
    "rotation_matrix_quality_pass",
    "float_serialization_max_digits10",
    "double_serialization_max_digits10",
}
FAILURE_REASONS = {
    "",
    "NONFINITE_TRANSFORM",
    "NONFINITE_FITNESS",
    "PCL_NOT_CONVERGED",
    "NO_CORRESPONDENCES",
    "INVALID_NORMALS",
    "RANK_DEFICIENT_DIAGNOSTIC",
    "ROTATION_MATRIX_QUALITY_FAILED",
    "EXCEPTION",
}
CROSSCHECK_MAX_RAD = 1.0e-10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--metric-cli", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--test", choices=sorted(TESTS), required=True)
    parser.add_argument("--truth", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def gate(
    checks: dict[str, dict[str, Any]],
    name: str,
    actual: Any,
    expected: Any,
    passed: bool,
) -> None:
    checks[name] = {"actual": actual, "expected": expected, "pass": bool(passed)}


def _matrix4(payload: dict[str, Any]) -> np.ndarray | None:
    raw = payload.get("final_transformation_4x4")
    if not isinstance(raw, list) or len(raw) != 16:
        return None
    matrix = np.asarray(raw, dtype=np.float64).reshape(4, 4)
    return matrix if np.all(np.isfinite(matrix)) else None


def _run_cpp_metric(
    metric_cli: Path, raw_rotation: np.ndarray, truth_rotation: np.ndarray
) -> tuple[dict[str, Any], list[str], int, str]:
    metric_input = {
        "raw_rotation_3x3": np.asarray(raw_rotation, dtype=np.float64).reshape(9).tolist(),
        "truth_rotation_3x3": np.asarray(truth_rotation, dtype=np.float64).reshape(9).tolist(),
    }
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", encoding="utf-8", delete=False
        ) as stream:
            json.dump(metric_input, stream, allow_nan=False)
            stream.write("\n")
            temporary_path = Path(stream.name)
        command = [str(metric_cli.resolve()), "--input", str(temporary_path)]
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError:
            result = {}
        return result, command, completed.returncode, completed.stderr
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def evaluate_rotation_crosscheck(
    metric_cli: Path, estimate: np.ndarray, truth: np.ndarray
) -> dict[str, Any]:
    raw_rotation = np.asarray(estimate[:3, :3], dtype=np.float64)
    truth_rotation = np.asarray(truth[:3, :3], dtype=np.float64)
    python_metric = rotation_metric_audit(raw_rotation, truth_rotation)
    cpp_metric, command, exit_code, stderr = _run_cpp_metric(
        metric_cli, raw_rotation, truth_rotation
    )
    cpp_error = cpp_metric.get("rotation_error_rad")
    python_error = python_metric.get("rotation_error_rad")
    difference = None
    if cpp_error is not None and python_error is not None:
        difference = abs(float(cpp_error) - float(python_error))
    quality_pass = bool(
        cpp_metric.get("rotation_matrix_quality_pass") is True
        and python_metric.get("rotation_matrix_quality_pass") is True
    )
    crosscheck_pass = bool(
        exit_code == 0
        and difference is not None
        and math.isfinite(difference)
        and difference <= CROSSCHECK_MAX_RAD
    )
    return {
        "cpp_rotation_metric": cpp_metric,
        "python_rotation_metric": python_metric,
        "cpp_metric_command": command,
        "cpp_metric_exit_code": exit_code,
        "cpp_metric_stderr": stderr,
        "cpp_projected_rotation_error_rad": cpp_error,
        "python_projected_rotation_error_rad": python_error,
        "rotation_metric_abs_difference_rad": difference,
        "ROTATION_MATRIX_QUALITY_PASS": quality_pass,
        "ROTATION_METRIC_CROSSCHECK_PASS": crosscheck_pass,
        "formal_rotation_error_rad": cpp_error,
        "formal_metric_implementation": "C++ Eigen reflection-safe SVD plus atan2",
        "smaller_value_selection_used": False,
    }


def validate_common(payload: dict[str, Any], checks: dict[str, dict[str, Any]]) -> None:
    missing = sorted(REQUIRED_FIELDS - set(payload))
    gate(checks, "required_fields_present", missing, [], not missing)
    if missing:
        return
    gate(
        checks,
        "failure_reason_vocabulary",
        payload["failure_reason"],
        sorted(FAILURE_REASONS),
        payload["failure_reason"] in FAILURE_REASONS,
    )
    gate(
        checks,
        "v1_unified_failure_reason_absent",
        payload["failure_reason"],
        "not pcl_icp_did_not_converge_or_nonfinite",
        payload["failure_reason"] != "pcl_icp_did_not_converge_or_nonfinite",
    )
    gate(
        checks,
        "float_serialization_precision",
        payload["float_serialization_max_digits10"],
        ">= 9",
        int(payload["float_serialization_max_digits10"]) >= 9,
    )
    gate(
        checks,
        "double_serialization_precision",
        payload["double_serialization_max_digits10"],
        ">= 17",
        int(payload["double_serialization_max_digits10"]) >= 17,
    )


def validate_rotation_gates(
    metric: dict[str, Any], checks: dict[str, dict[str, Any]]
) -> None:
    gate(
        checks,
        "ROTATION_MATRIX_QUALITY_PASS",
        metric["ROTATION_MATRIX_QUALITY_PASS"],
        True,
        metric["ROTATION_MATRIX_QUALITY_PASS"] is True,
    )
    gate(
        checks,
        "ROTATION_METRIC_CROSSCHECK_PASS",
        metric["ROTATION_METRIC_CROSSCHECK_PASS"],
        True,
        metric["ROTATION_METRIC_CROSSCHECK_PASS"] is True,
    )
    gate(
        checks,
        "rotation_metric_abs_difference_rad",
        metric["rotation_metric_abs_difference_rad"],
        "<= 1e-10",
        metric["rotation_metric_abs_difference_rad"] is not None
        and float(metric["rotation_metric_abs_difference_rad"]) <= CROSSCHECK_MAX_RAD,
    )


def validate_identity(
    payload: dict[str, Any], metric_cli: Path, checks: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    estimate = _matrix4(payload)
    gate(checks, "final_transform_available", estimate is not None, True, estimate is not None)
    metric: dict[str, Any] = {}
    if estimate is not None:
        metric = evaluate_rotation_crosscheck(metric_cli, estimate, np.eye(4))
        validate_rotation_gates(metric, checks)
    else:
        gate(checks, "ROTATION_MATRIX_QUALITY_PASS", False, True, False)
        gate(checks, "ROTATION_METRIC_CROSSCHECK_PASS", False, True, False)
    gate(
        checks,
        "has_converged_raw",
        payload["has_converged_raw"],
        True,
        payload["has_converged_raw"] is True,
    )
    gate(
        checks,
        "final_transform_finite",
        payload["final_transform_finite"],
        True,
        payload["final_transform_finite"] is True,
    )
    gate(
        checks,
        "fitness_finite",
        payload["fitness_finite"],
        True,
        payload["fitness_finite"] is True,
    )
    translation = payload["translation_update_norm_m"]
    rotation = metric.get("formal_rotation_error_rad")
    gate(
        checks,
        "translation_update_norm_m",
        translation,
        "<= 1e-8",
        translation is not None and float(translation) <= 1.0e-8,
    )
    gate(
        checks,
        "rotation_update_norm_rad",
        rotation,
        "<= 1e-8",
        rotation is not None and float(rotation) <= 1.0e-8,
    )
    gate(
        checks,
        "correspondence_count",
        payload["correspondence_count"],
        "> 0",
        int(payload["correspondence_count"]) > 0,
    )
    for cloud in ("source", "target"):
        gate(
            checks,
            f"{cloud}_normal_nan_count",
            payload[f"{cloud}_normal_nan_count"],
            0,
            int(payload[f"{cloud}_normal_nan_count"]) == 0,
        )
        gate(
            checks,
            f"{cloud}_normal_zero_count",
            payload[f"{cloud}_normal_zero_count"],
            0,
            int(payload[f"{cloud}_normal_zero_count"]) == 0,
        )
    return {
        **metric,
        "truth_passed_to_cli": False,
        "truth_source_to_target_transform_4x4": np.eye(4).tolist(),
        "estimated_source_to_target_transform_4x4": (
            estimate.tolist() if estimate is not None else None
        ),
    }


def validate_known_transform(
    payload: dict[str, Any],
    metric_cli: Path,
    truth_path: Path | None,
    checks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if truth_path is None:
        raise ValueError("KNOWN_SMALL_TRANSFORM requires --truth")
    truth_document = json.loads(truth_path.read_text(encoding="utf-8"))
    truth = np.asarray(
        truth_document["expected_source_to_target_transform_4x4"], dtype=np.float64
    ).reshape(4, 4)
    estimate = _matrix4(payload)
    gate(checks, "final_transform_available", estimate is not None, True, estimate is not None)
    translation_error = None
    metric: dict[str, Any] = {}
    if estimate is not None:
        delta_translation = estimate[:3, 3] - truth[:3, 3]
        translation_error = float(np.linalg.norm(delta_translation))
        metric = evaluate_rotation_crosscheck(metric_cli, estimate, truth)
        validate_rotation_gates(metric, checks)
    else:
        gate(checks, "ROTATION_MATRIX_QUALITY_PASS", False, True, False)
        gate(checks, "ROTATION_METRIC_CROSSCHECK_PASS", False, True, False)
    rotation_error = metric.get("formal_rotation_error_rad")
    gate(
        checks,
        "translation_error_to_truth_m",
        translation_error,
        "<= 1e-4",
        translation_error is not None and translation_error <= 1.0e-4,
    )
    gate(
        checks,
        "rotation_error_to_truth_rad",
        rotation_error,
        "<= 1e-4",
        rotation_error is not None and float(rotation_error) <= 1.0e-4,
    )
    for name in ("has_converged_raw", "final_transform_finite", "fitness_finite"):
        gate(checks, name, payload[name], True, payload[name] is True)
    return {
        **metric,
        "truth_passed_to_cli": False,
        "truth_source_to_target_transform_4x4": truth.tolist(),
        "estimated_source_to_target_transform_4x4": (
            estimate.tolist() if estimate is not None else None
        ),
        "translation_error_to_truth_m": translation_error,
        "rotation_error_to_truth_rad": rotation_error,
        "raw_trace_acos_rotation_error_rad": (
            metric.get("cpp_rotation_metric", {}).get(
                "raw_trace_acos_rotation_error_rad"
            )
        ),
    }


def validate_planar(payload: dict[str, Any], checks: dict[str, dict[str, Any]]) -> None:
    gate(
        checks,
        "point_cloud_rank",
        payload["point_cloud_rank"],
        2,
        int(payload["point_cloud_rank"]) == 2,
    )
    rank = int(payload["point_to_plane_jacobian_rank"])
    gate(checks, "point_to_plane_jacobian_rank", rank, "< 6", rank < 6)
    gate(
        checks,
        "rank_deficient",
        payload["rank_deficient"],
        True,
        payload["rank_deficient"] is True,
    )
    eigenvalues = payload["point_to_plane_hessian_eigenvalues"]
    valid_eigenvalues = (
        isinstance(eigenvalues, list)
        and len(eigenvalues) == 6
        and all(math.isfinite(float(value)) for value in eigenvalues)
    )
    gate(
        checks,
        "hessian_eigenvalues_available",
        eigenvalues,
        "six finite sorted values",
        valid_eigenvalues,
    )
    gate(
        checks,
        "condition_status",
        payload["condition_status"],
        "RANK_DEFICIENT",
        payload["condition_status"] == "RANK_DEFICIENT",
    )
    gate(
        checks,
        "failure_reason",
        payload["failure_reason"],
        "RANK_DEFICIENT_DIAGNOSTIC",
        payload["failure_reason"] == "RANK_DEFICIENT_DIAGNOSTIC",
    )


def main() -> int:
    args = parse_args()
    command = [str(args.cli.resolve()), "--config", str(args.config.resolve())]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    checks: dict[str, dict[str, Any]] = {}
    payload: dict[str, Any]
    parse_error = ""
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        payload = {}
        parse_error = str(error)
    gate(checks, "cli_exit_code", completed.returncode, 0, completed.returncode == 0)
    gate(checks, "stdout_is_one_json_document", parse_error, "", not parse_error)
    details: dict[str, Any] = {}
    if not parse_error:
        validate_common(payload, checks)
        if not (REQUIRED_FIELDS - set(payload)):
            if args.test == "NONDEGENERATE_IDENTITY":
                details = validate_identity(payload, args.metric_cli, checks)
            elif args.test == "KNOWN_SMALL_TRANSFORM":
                details = validate_known_transform(
                    payload, args.metric_cli, args.truth, checks
                )
            else:
                validate_planar(payload, checks)
    passed = all(item["pass"] for item in checks.values())
    result = {
        "schema_version": "pcl_backend_qualification_v3_microtest_result_v1",
        "microtest": args.test,
        "microtest_pass": passed,
        "cli_command": command,
        "truth_argument_passed_to_registration_cli": False,
        "cli_exit_code": completed.returncode,
        "cli_stderr": completed.stderr,
        "cli_result": payload,
        "gate_checks": checks,
        **details,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
