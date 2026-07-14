"""ODI computation utilities for Day 6."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

from .whitened_info import (
    compute_AIS,
    compute_effective_sample_size,
    compute_H_tilde,
    compute_epsilon,
    compute_lambda_min,
    compute_translation_schur_info,
    eigen_decompose,
    normalize_information_matrix,
    safe_condition_number,
)
from .weak_direction import (
    compute_axis_alignment,
    compute_subspace_axis_alignment,
    compute_weak_projector,
    extract_weak_subspace,
    get_primary_weak_direction,
    is_direction_reliable,
    translation_component,
)


def compute_effective_rank(eigvals: np.ndarray, eps: float) -> float:
    values = np.maximum(np.asarray(eigvals, dtype=float), 0.0)
    weights = values + eps
    probs = weights / np.sum(weights)
    entropy = -float(np.sum(probs * np.log(probs)))
    return float(np.exp(entropy))


def compute_ODI(eigvals: np.ndarray, eps: float) -> float:
    values = np.asarray(eigvals, dtype=float)
    d = values.size
    if d <= 1:
        return 0.0
    r_eff = compute_effective_rank(values, eps)
    odi = 1.0 - (r_eff - 1.0) / (d - 1.0)
    return float(np.clip(odi, 0.0, 1.0))


def compute_metrics_for_frame(
    J: np.ndarray,
    R_diag: np.ndarray,
    config: Dict[str, Any],
    axis: np.ndarray | None = None,
) -> Dict[str, float]:
    H_tilde = compute_H_tilde(
        J,
        R_diag,
        float(config["s_theta"]),
        float(config["s_p"]),
        str(config.get("epsilon_mode", "relative_trace")),
        float(config.get("epsilon_ratio", 1.0e-6)),
    )
    eigvals, eigvecs = eigen_decompose(H_tilde)
    eps = compute_epsilon(eigvals, str(config.get("epsilon_mode", "relative_trace")), float(config.get("epsilon_ratio", 1.0e-6)))
    primary_weak = get_primary_weak_direction(eigvals, eigvecs)
    weak_trans = translation_component(primary_weak)
    reliable = is_direction_reliable(
        eigvals,
        eigvecs,
        float(config.get("weak_min_gap_ratio", config.get("min_gap_ratio", 1.0e-3))),
        float(config.get("weak_min_translation_norm", 0.25)),
    )
    axis_alignment = float("nan")
    if reliable and axis is not None:
        axis_alignment = compute_axis_alignment(weak_trans, np.asarray(axis, dtype=float))

    trans_info_raw = compute_translation_schur_info(
        H_tilde, float(config.get("translation_schur_damping_ratio", 1.0e-6))
    )
    n_eff = compute_effective_sample_size(R_diag)
    trans_info_normalized = normalize_information_matrix(trans_info_raw, n_eff)
    trans_eigvals, trans_eigvecs = eigen_decompose(trans_info_normalized)
    trans_eps = compute_epsilon(
        trans_eigvals,
        str(config.get("epsilon_mode", "relative_trace")),
        float(config.get("epsilon_ratio", 1.0e-6)),
    )
    trans_raw_eigvals, _ = eigen_decompose(trans_info_raw)
    trans_weak = extract_weak_subspace(trans_eigvals, trans_eigvecs, float(config.get("tau_w", 0.02)))
    trans_projector = compute_weak_projector(trans_eigvals, trans_eigvecs, float(config.get("tau_w", 0.02)))
    trans_alignment = float("nan")
    if axis is not None:
        trans_alignment = compute_subspace_axis_alignment(trans_projector, np.asarray(axis, dtype=float))
    trans_primary = get_primary_weak_direction(trans_eigvals, trans_eigvecs)
    trans_primary_reliable = is_direction_reliable(
        trans_eigvals,
        trans_eigvecs,
        float(config.get("translation_primary_min_gap_ratio", config.get("weak_min_gap_ratio", 1.0e-3))),
        0.0,
    )

    metrics: Dict[str, float] = {
        "ODI": compute_ODI(eigvals, eps),
        "AIS": compute_AIS(H_tilde, eps),
        "lambda_min": compute_lambda_min(eigvals),
        "lambda_min_clamped": max(compute_lambda_min(eigvals), 0.0),
        "condition_number": safe_condition_number(eigvals, eps),
        "num_points": float(J.shape[0]),
        "axis_alignment": axis_alignment,
        "weak_reliable": float(1 if reliable else 0),
        "num_weak_dims": float(extract_weak_subspace(eigvals, eigvecs, float(config.get("tau_w", 0.02))).shape[1]),
        "ODI_trans": compute_ODI(trans_eigvals, trans_eps),
        "AIS_trans_raw": compute_AIS(trans_info_raw, trans_eps * n_eff),
        "AIS_trans_normalized": compute_AIS(trans_info_normalized, trans_eps),
        "lambda_min_trans_raw": compute_lambda_min(trans_raw_eigvals),
        "lambda_min_trans_normalized": compute_lambda_min(trans_eigvals),
        "condition_number_trans": safe_condition_number(trans_eigvals, trans_eps),
        "trans_info_trace_raw": float(np.trace(trans_info_raw)),
        "trans_info_trace_normalized": float(np.trace(trans_info_normalized)),
        "effective_sample_size": n_eff,
        "weak_trans_subspace_dim": float(trans_weak.shape[1]),
        "weak_trans_subspace_alignment": trans_alignment,
        "weak_trans_primary_x": float(trans_primary[0]),
        "weak_trans_primary_y": float(trans_primary[1]),
        "weak_trans_primary_z": float(trans_primary[2]),
        "weak_trans_primary_reliable": float(1 if trans_primary_reliable else 0),
    }
    for idx, value in enumerate(eigvals, start=1):
        metrics[f"eig_{idx}"] = float(value)
    for idx, value in enumerate(primary_weak):
        metrics[f"weak_dir_{idx}"] = float(value)
    for key, value in zip(["weak_trans_x", "weak_trans_y", "weak_trans_z"], weak_trans):
        metrics[key] = float(value)
    for idx, value in enumerate(trans_eigvals, start=1):
        metrics[f"trans_eig_{idx}"] = float(value)
    return metrics


def compute_metrics_for_sequence(observations: Any, config: Dict[str, Any]) -> np.ndarray:
    J_all = np.asarray(observations["packed_J"], dtype=float)
    R_all = np.asarray(observations["R_diag_list"], dtype=float)
    timestamps = np.asarray(observations["timestamps"], dtype=float)

    dtype = [
        ("timestamp", "f8"),
        ("eig_1", "f8"),
        ("eig_2", "f8"),
        ("eig_3", "f8"),
        ("eig_4", "f8"),
        ("eig_5", "f8"),
        ("eig_6", "f8"),
        ("ODI", "f8"),
        ("AIS", "f8"),
        ("lambda_min", "f8"),
        ("lambda_min_clamped", "f8"),
        ("condition_number", "f8"),
        ("num_points", "i4"),
        ("weak_dir_0", "f8"),
        ("weak_dir_1", "f8"),
        ("weak_dir_2", "f8"),
        ("weak_dir_3", "f8"),
        ("weak_dir_4", "f8"),
        ("weak_dir_5", "f8"),
        ("weak_trans_x", "f8"),
        ("weak_trans_y", "f8"),
        ("weak_trans_z", "f8"),
        ("axis_alignment", "f8"),
        ("weak_reliable", "i4"),
        ("num_weak_dims", "i4"),
        ("trans_eig_1", "f8"),
        ("trans_eig_2", "f8"),
        ("trans_eig_3", "f8"),
        ("ODI_trans", "f8"),
        ("AIS_trans_raw", "f8"),
        ("AIS_trans_normalized", "f8"),
        ("lambda_min_trans_raw", "f8"),
        ("lambda_min_trans_normalized", "f8"),
        ("condition_number_trans", "f8"),
        ("trans_info_trace_raw", "f8"),
        ("trans_info_trace_normalized", "f8"),
        ("effective_sample_size", "f8"),
        ("weak_trans_subspace_dim", "i4"),
        ("weak_trans_subspace_alignment", "f8"),
        ("weak_trans_primary_x", "f8"),
        ("weak_trans_primary_y", "f8"),
        ("weak_trans_primary_z", "f8"),
        ("weak_trans_primary_reliable", "i4"),
    ]
    rows = np.zeros(J_all.shape[0], dtype=dtype)
    axes = np.asarray(observations["axis_per_frame"], dtype=float) if "axis_per_frame" in observations else None
    for idx in range(J_all.shape[0]):
        axis = axes[idx] if axes is not None else None
        metrics = compute_metrics_for_frame(J_all[idx], R_all[idx], config, axis=axis)
        rows["timestamp"][idx] = timestamps[idx]
        for key in [
            "eig_1",
            "eig_2",
            "eig_3",
            "eig_4",
            "eig_5",
            "eig_6",
            "ODI",
            "AIS",
            "lambda_min",
            "lambda_min_clamped",
            "condition_number",
            "weak_dir_0",
            "weak_dir_1",
            "weak_dir_2",
            "weak_dir_3",
            "weak_dir_4",
            "weak_dir_5",
            "weak_trans_x",
            "weak_trans_y",
            "weak_trans_z",
            "axis_alignment",
            "trans_eig_1",
            "trans_eig_2",
            "trans_eig_3",
            "ODI_trans",
            "AIS_trans_raw",
            "AIS_trans_normalized",
            "lambda_min_trans_raw",
            "lambda_min_trans_normalized",
            "condition_number_trans",
            "trans_info_trace_raw",
            "trans_info_trace_normalized",
            "effective_sample_size",
            "weak_trans_subspace_alignment",
            "weak_trans_primary_x",
            "weak_trans_primary_y",
            "weak_trans_primary_z",
        ]:
            rows[key][idx] = metrics[key]
        rows["num_points"][idx] = int(metrics["num_points"])
        rows["weak_reliable"][idx] = int(metrics["weak_reliable"])
        rows["num_weak_dims"][idx] = int(metrics["num_weak_dims"])
        rows["weak_trans_subspace_dim"][idx] = int(metrics["weak_trans_subspace_dim"])
        rows["weak_trans_primary_reliable"][idx] = int(metrics["weak_trans_primary_reliable"])
    return rows
