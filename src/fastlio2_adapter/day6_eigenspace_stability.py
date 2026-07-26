"""Translation information and eigenspace stability for frozen Day 6 records."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy.stats import spearmanr

from degen_detector.odi_tracker import compute_ODI
from degen_detector.whitened_info import (
    compute_AIS,
    compute_H_tilde,
    compute_effective_sample_size,
    compute_epsilon,
    compute_translation_schur_info,
    eigen_decompose,
    normalize_information_matrix,
    safe_condition_number,
)

from .detector_adapter import load_production_detector_contract


EIGENVALUE_TOLERANCE = 1.0e-12
GAP_BINS = (
    ("lt_1e-3", float("-inf"), 1.0e-3),
    ("1e-3_to_1e-2", 1.0e-3, 1.0e-2),
    ("1e-2_to_1e-1", 1.0e-2, 1.0e-1),
    ("ge_1e-1", 1.0e-1, float("inf")),
)


class Day6EigenspaceError(ValueError):
    """The offline information/eigenspace contract was violated."""


def reconstruct_translation_information(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Reuse production matrix helpers without calling the detector entrypoint."""

    jacobian = np.asarray(
        record["detector_pose_jacobian_rows"], dtype=np.float64
    )
    if jacobian.ndim != 2 or jacobian.shape[1] != 6:
        raise Day6EigenspaceError("Jacobian must be N by 6")
    variance = np.full(
        jacobian.shape[0],
        float(record["measurement_variance_scalar_m2"]),
        dtype=np.float64,
    )
    config, provenance = load_production_detector_contract()
    h_pose = compute_H_tilde(
        jacobian,
        variance,
        float(config["s_theta"]),
        float(config["s_p"]),
        str(config.get("epsilon_mode", "relative_trace")),
        float(config.get("epsilon_ratio", 1.0e-6)),
    )
    h_translation_raw = compute_translation_schur_info(
        h_pose,
        float(config.get("translation_schur_damping_ratio", 1.0e-6)),
    )
    effective_sample_size = compute_effective_sample_size(variance)
    h_translation = normalize_information_matrix(
        h_translation_raw,
        effective_sample_size,
    )
    descending_values, descending_vectors = eigen_decompose(h_translation)
    eigenvalues = np.asarray(descending_values[::-1], dtype=np.float64)
    eigenvectors = np.asarray(
        descending_vectors[:, ::-1], dtype=np.float64
    )
    epsilon = compute_epsilon(
        eigenvalues,
        str(config.get("epsilon_mode", "relative_trace")),
        float(config.get("epsilon_ratio", 1.0e-6)),
    )
    lambda_1, lambda_2, lambda_3 = [
        float(value) for value in eigenvalues
    ]
    absolute_gap_12 = lambda_2 - lambda_1
    absolute_gap_23 = lambda_3 - lambda_2
    relative_gap_12 = absolute_gap_12 / max(
        abs(lambda_1), abs(lambda_2), 1.0e-18
    )
    relative_gap_23 = absolute_gap_23 / max(
        abs(lambda_2), abs(lambda_3), 1.0e-18
    )
    lambda_max = max(abs(lambda_3), 1.0e-18)
    return {
        "h_pose": h_pose,
        "h_translation_raw": h_translation_raw,
        "h_translation": h_translation,
        "eigenvalues": eigenvalues,
        "eigenvectors": eigenvectors,
        "v1": eigenvectors[:, 0],
        "v2": eigenvectors[:, 1],
        "weak_subspace": eigenvectors[:, :2],
        "absolute_gap_12": float(absolute_gap_12),
        "relative_gap_12": float(relative_gap_12),
        "absolute_gap_23": float(absolute_gap_23),
        "relative_gap_23": float(relative_gap_23),
        "primary_eigengap_ratio": float(absolute_gap_12 / lambda_max),
        "condition_number": float(
            safe_condition_number(eigenvalues, epsilon)
        ),
        "odi_trans": float(compute_ODI(eigenvalues, epsilon)),
        "ais_trans": float(compute_AIS(h_translation, epsilon)),
        "effective_sample_size": float(effective_sample_size),
        "detector_source_sha256": provenance["detector_source_sha256"],
        "detector_config_sha256": provenance["detector_config_sha256"],
        "detector_lock_sha256": provenance["detector_lock_sha256"],
    }


def sign_invariant_angle_deg(left: Any, right: Any) -> float:
    left_vector = np.asarray(left, dtype=np.float64)
    right_vector = np.asarray(right, dtype=np.float64)
    if left_vector.shape != right_vector.shape or left_vector.ndim != 1:
        raise Day6EigenspaceError("angle vectors must have the same 1-D shape")
    left_norm = float(np.linalg.norm(left_vector))
    right_norm = float(np.linalg.norm(right_vector))
    if left_norm < 1.0e-18 or right_norm < 1.0e-18:
        raise Day6EigenspaceError("angle vector has zero norm")
    dot = float(
        np.dot(left_vector / left_norm, right_vector / right_norm)
    )
    return float(
        math.degrees(math.acos(float(np.clip(abs(dot), 0.0, 1.0))))
    )


def weak_subspace_principal_angles_deg(
    left: Any,
    right: Any,
) -> tuple[float, float]:
    left_basis = np.asarray(left, dtype=np.float64)
    right_basis = np.asarray(right, dtype=np.float64)
    if (
        left_basis.shape != (3, 2)
        or right_basis.shape != (3, 2)
    ):
        raise Day6EigenspaceError("weak bases must both have shape 3 by 2")
    left_q, _ = np.linalg.qr(left_basis)
    right_q, _ = np.linalg.qr(right_basis)
    singular_values = np.linalg.svd(
        left_q.T @ right_q,
        compute_uv=False,
    )
    angles = np.degrees(
        np.arccos(np.clip(singular_values, 0.0, 1.0))
    )
    return float(np.min(angles)), float(np.max(angles))


def matrix_perturbation(left: Any, right: Any) -> dict[str, float]:
    left_matrix = np.asarray(left, dtype=np.float64)
    right_matrix = np.asarray(right, dtype=np.float64)
    if left_matrix.shape != (3, 3) or right_matrix.shape != (3, 3):
        raise Day6EigenspaceError("translation matrices must be 3 by 3")
    absolute = float(np.linalg.norm(right_matrix - left_matrix, ord=2))
    relative = absolute / max(
        float(np.linalg.norm(left_matrix, ord=2)),
        float(np.linalg.norm(right_matrix, ord=2)),
        1.0e-18,
    )
    return {
        "h_perturbation_norm_2": absolute,
        "relative_h_perturbation": float(relative),
    }


def descriptive_statistics(values: Sequence[float]) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.float64)
    finite = array[np.isfinite(array)]
    excluded = int(array.size - finite.size)
    if finite.size == 0:
        return {
            "count": 0,
            "nonfinite_excluded_count": excluded,
            "min": None,
            "median": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "max": None,
            "mean": None,
            "std": None,
        }
    return {
        "count": int(finite.size),
        "nonfinite_excluded_count": excluded,
        "min": float(np.min(finite)),
        "median": float(np.median(finite)),
        "p90": float(np.quantile(finite, 0.90)),
        "p95": float(np.quantile(finite, 0.95)),
        "p99": float(np.quantile(finite, 0.99)),
        "max": float(np.max(finite)),
        "mean": float(np.mean(finite)),
        "std": float(np.std(finite)),
    }


def spearman_summary(
    left: Sequence[float],
    right: Sequence[float],
) -> dict[str, Any]:
    left_array = np.asarray(left, dtype=np.float64)
    right_array = np.asarray(right, dtype=np.float64)
    if left_array.shape != right_array.shape:
        raise Day6EigenspaceError("correlation vectors have different shapes")
    mask = np.isfinite(left_array) & np.isfinite(right_array)
    count = int(np.sum(mask))
    excluded = int(mask.size - count)
    if count < 2:
        return {
            "sample_count": count,
            "nonfinite_excluded_count": excluded,
            "spearman_rho": None,
            "pvalue": None,
            "causal_interpretation": False,
        }
    result = spearmanr(left_array[mask], right_array[mask])
    rho = float(result.statistic)
    pvalue = float(result.pvalue)
    return {
        "sample_count": count,
        "nonfinite_excluded_count": excluded,
        "spearman_rho": rho if math.isfinite(rho) else None,
        "pvalue": pvalue if math.isfinite(pvalue) else None,
        "causal_interpretation": False,
    }


def gap_bin_name(relative_gap_12: float) -> str:
    value = float(relative_gap_12)
    for name, lower, upper in GAP_BINS:
        if lower <= value < upper:
            return name
    raise Day6EigenspaceError("relative gap did not enter a fixed bin")


def compare_reconstruction(
    reconstruction: Mapping[str, Any],
    direct_output: Mapping[str, Any],
) -> dict[str, float]:
    expected = np.asarray(
        direct_output["translation_eigenvalues_ascending"],
        dtype=np.float64,
    )
    actual = np.asarray(reconstruction["eigenvalues"], dtype=np.float64)
    eigenvalue_error = float(np.max(np.abs(actual - expected)))
    direction_error = sign_invariant_angle_deg(
        reconstruction["v1"],
        direct_output["primary_weak_direction"],
    )
    metric_errors = {
        "odi_abs_error": abs(
            float(reconstruction["odi_trans"])
            - float(direct_output["odi_trans"])
        ),
        "ais_abs_error": abs(
            float(reconstruction["ais_trans"])
            - float(direct_output["ais_trans"])
        ),
        "lambda_min_abs_error": abs(
            float(actual[0]) - float(direct_output["lambda_min_trans"])
        ),
        "condition_number_abs_error": abs(
            float(reconstruction["condition_number"])
            - float(direct_output["condition_number_trans"])
        ),
    }
    return {
        "eigenvalue_max_abs_error": eigenvalue_error,
        "primary_direction_sign_invariant_angle_error_deg": direction_error,
        **metric_errors,
    }


def reconstruction_pass(error: Mapping[str, float]) -> bool:
    return bool(
        float(error["eigenvalue_max_abs_error"])
        <= EIGENVALUE_TOLERANCE
        and float(
            error["primary_direction_sign_invariant_angle_error_deg"]
        )
        <= 1.0e-5
        and float(error["odi_abs_error"]) <= EIGENVALUE_TOLERANCE
        and float(error["ais_abs_error"]) <= EIGENVALUE_TOLERANCE
        and float(error["lambda_min_abs_error"])
        <= EIGENVALUE_TOLERANCE
        and float(error["condition_number_abs_error"])
        <= 1.0e-9
    )
