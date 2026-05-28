"""ODI computation utilities for Day 6."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

from .whitened_info import (
    compute_AIS,
    compute_H_tilde,
    compute_epsilon,
    compute_lambda_min,
    eigen_decompose,
    safe_condition_number,
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


def compute_metrics_for_frame(J: np.ndarray, R_diag: np.ndarray, config: Dict[str, Any]) -> Dict[str, float]:
    H_tilde = compute_H_tilde(
        J,
        R_diag,
        float(config["s_theta"]),
        float(config["s_p"]),
        str(config.get("epsilon_mode", "relative_trace")),
        float(config.get("epsilon_ratio", 1.0e-6)),
    )
    eigvals, _ = eigen_decompose(H_tilde)
    eps = compute_epsilon(eigvals, str(config.get("epsilon_mode", "relative_trace")), float(config.get("epsilon_ratio", 1.0e-6)))
    metrics: Dict[str, float] = {
        "ODI": compute_ODI(eigvals, eps),
        "AIS": compute_AIS(H_tilde, eps),
        "lambda_min": compute_lambda_min(eigvals),
        "condition_number": safe_condition_number(eigvals, eps),
        "num_points": float(J.shape[0]),
    }
    for idx, value in enumerate(eigvals, start=1):
        metrics[f"eig_{idx}"] = float(value)
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
        ("condition_number", "f8"),
        ("num_points", "i4"),
    ]
    rows = np.zeros(J_all.shape[0], dtype=dtype)
    for idx in range(J_all.shape[0]):
        metrics = compute_metrics_for_frame(J_all[idx], R_all[idx], config)
        rows["timestamp"][idx] = timestamps[idx]
        for key in ["eig_1", "eig_2", "eig_3", "eig_4", "eig_5", "eig_6", "ODI", "AIS", "lambda_min", "condition_number"]:
            rows[key][idx] = metrics[key]
        rows["num_points"][idx] = int(metrics["num_points"])
    return rows

