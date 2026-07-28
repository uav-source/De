#!/usr/bin/env python3
"""Structured verifier for one frozen PCL backend qualification v2 microtest."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import numpy as np


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
}
FAILURE_REASONS = {
    "",
    "NONFINITE_TRANSFORM",
    "NONFINITE_FITNESS",
    "PCL_NOT_CONVERGED",
    "NO_CORRESPONDENCES",
    "INVALID_NORMALS",
    "RANK_DEFICIENT_DIAGNOSTIC",
    "EXCEPTION",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--test", choices=sorted(TESTS), required=True)
    parser.add_argument("--truth", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def transform_error(truth: np.ndarray, estimate: np.ndarray) -> tuple[float, float]:
    delta = np.linalg.inv(truth) @ estimate
    translation = float(np.linalg.norm(delta[:3, 3]))
    cosine = float(np.clip((np.trace(delta[:3, :3]) - 1.0) * 0.5, -1.0, 1.0))
    return translation, float(math.acos(cosine))


def gate(checks: dict[str, dict[str, Any]], name: str, actual: Any, expected: Any, passed: bool) -> None:
    checks[name] = {"actual": actual, "expected": expected, "pass": bool(passed)}


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


def validate_identity(payload: dict[str, Any], checks: dict[str, dict[str, Any]]) -> None:
    gate(checks, "has_converged_raw", payload["has_converged_raw"], True, payload["has_converged_raw"] is True)
    gate(checks, "final_transform_finite", payload["final_transform_finite"], True, payload["final_transform_finite"] is True)
    gate(checks, "fitness_finite", payload["fitness_finite"], True, payload["fitness_finite"] is True)
    translation = payload["translation_update_norm_m"]
    rotation = payload["rotation_update_norm_rad"]
    gate(checks, "translation_update_norm_m", translation, "<= 1e-8", translation is not None and float(translation) <= 1.0e-8)
    gate(checks, "rotation_update_norm_rad", rotation, "<= 1e-8", rotation is not None and float(rotation) <= 1.0e-8)
    gate(checks, "correspondence_count", payload["correspondence_count"], "> 0", int(payload["correspondence_count"]) > 0)
    for cloud in ("source", "target"):
        gate(checks, f"{cloud}_normal_nan_count", payload[f"{cloud}_normal_nan_count"], 0, int(payload[f"{cloud}_normal_nan_count"]) == 0)
        gate(checks, f"{cloud}_normal_zero_count", payload[f"{cloud}_normal_zero_count"], 0, int(payload[f"{cloud}_normal_zero_count"]) == 0)


def validate_known_transform(
    payload: dict[str, Any], truth_path: Path | None, checks: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if truth_path is None:
        raise ValueError("KNOWN_SMALL_TRANSFORM requires --truth")
    truth_document = json.loads(truth_path.read_text(encoding="utf-8"))
    truth = np.asarray(
        truth_document["expected_source_to_target_transform_4x4"], dtype=np.float64
    ).reshape(4, 4)
    raw_estimate = payload["final_transformation_4x4"]
    estimate_available = isinstance(raw_estimate, list) and len(raw_estimate) == 16
    gate(checks, "final_transform_available", estimate_available, True, estimate_available)
    translation_error = None
    rotation_error = None
    estimate = None
    if estimate_available:
        estimate = np.asarray(raw_estimate, dtype=np.float64).reshape(4, 4)
        translation_error, rotation_error = transform_error(truth, estimate)
    gate(checks, "translation_error_to_truth_m", translation_error, "<= 1e-4", translation_error is not None and translation_error <= 1.0e-4)
    gate(checks, "rotation_error_to_truth_rad", rotation_error, "<= 1e-4", rotation_error is not None and rotation_error <= 1.0e-4)
    gate(checks, "has_converged_raw", payload["has_converged_raw"], True, payload["has_converged_raw"] is True)
    gate(checks, "final_transform_finite", payload["final_transform_finite"], True, payload["final_transform_finite"] is True)
    gate(checks, "fitness_finite", payload["fitness_finite"], True, payload["fitness_finite"] is True)
    return {
        "truth_passed_to_cli": False,
        "truth_source_to_target_transform_4x4": truth.tolist(),
        "estimated_source_to_target_transform_4x4": estimate.tolist() if estimate is not None else None,
        "translation_error_to_truth_m": translation_error,
        "rotation_error_to_truth_rad": rotation_error,
    }


def validate_planar(payload: dict[str, Any], checks: dict[str, dict[str, Any]]) -> None:
    gate(checks, "point_cloud_rank", payload["point_cloud_rank"], 2, int(payload["point_cloud_rank"]) == 2)
    rank = int(payload["point_to_plane_jacobian_rank"])
    gate(checks, "point_to_plane_jacobian_rank", rank, "< 6", rank < 6)
    gate(checks, "rank_deficient", payload["rank_deficient"], True, payload["rank_deficient"] is True)
    eigenvalues = payload["point_to_plane_hessian_eigenvalues"]
    valid_eigenvalues = isinstance(eigenvalues, list) and len(eigenvalues) == 6 and all(math.isfinite(float(value)) for value in eigenvalues)
    gate(checks, "hessian_eigenvalues_available", eigenvalues, "six finite sorted values", valid_eigenvalues)
    gate(checks, "condition_status", payload["condition_status"], "RANK_DEFICIENT", payload["condition_status"] == "RANK_DEFICIENT")
    gate(checks, "failure_reason", payload["failure_reason"], "RANK_DEFICIENT_DIAGNOSTIC", payload["failure_reason"] == "RANK_DEFICIENT_DIAGNOSTIC")


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
                validate_identity(payload, checks)
            elif args.test == "KNOWN_SMALL_TRANSFORM":
                details = validate_known_transform(payload, args.truth, checks)
            else:
                validate_planar(payload, checks)
    passed = all(item["pass"] for item in checks.values())
    result = {
        "schema_version": "pcl_backend_qualification_v2_microtest_result_v1",
        "microtest": args.test,
        "microtest_pass": passed,
        "cli_command": command,
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
