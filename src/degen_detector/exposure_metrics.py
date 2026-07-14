"""Cumulative weak-constraint exposure metrics retained for Stage 1c reproduction."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

import numpy as np


def harmonic_axis_information(
    axis_information: Sequence[float],
    timestamps: Sequence[float] | None = None,
    epsilon: float = 1.0e-12,
) -> float:
    values = _positive_information(axis_information)
    weights = _time_weights(values.size, timestamps)
    return float(np.sum(weights) / np.sum(weights / (values + epsilon)))


def cumulative_inverse_axis_information(
    axis_information: Sequence[float],
    timestamps: Sequence[float] | None = None,
    epsilon: float = 1.0e-12,
) -> float:
    values = _positive_information(axis_information)
    weights = _time_weights(values.size, timestamps)
    return float(np.sum(weights / (values + epsilon)))


def mean_inverse_axis_information(
    axis_information: Sequence[float],
    timestamps: Sequence[float] | None = None,
    epsilon: float = 1.0e-12,
) -> float:
    values = _positive_information(axis_information)
    weights = _time_weights(values.size, timestamps)
    return float(np.sum(weights / (values + epsilon)) / np.sum(weights))


def low_axis_information_ratio(axis_information: Sequence[float], threshold: float) -> float:
    values = _positive_information(axis_information)
    return float(np.mean(values < float(threshold)))


def longest_condition_duration(
    condition: Sequence[bool],
    timestamps: Sequence[float] | None = None,
) -> float:
    mask = np.asarray(condition, dtype=bool)
    if mask.ndim != 1 or mask.size == 0:
        raise ValueError("condition must be a non-empty 1-D sequence")
    weights = _time_weights(mask.size, timestamps)
    longest = current = 0.0
    for active, duration in zip(mask, weights):
        current = current + float(duration) if active else 0.0
        longest = max(longest, current)
    return float(longest)


def weak_subspace_persistence(projectors: np.ndarray) -> np.ndarray:
    matrices = np.asarray(projectors, dtype=float)
    if matrices.ndim != 3 or matrices.shape[1:] != (3, 3):
        raise ValueError("projectors must have shape [N, 3, 3]")
    if matrices.shape[0] < 2:
        return np.asarray([], dtype=float)
    similarities = []
    for previous, current in zip(matrices[:-1], matrices[1:]):
        previous_dim = max(int(round(float(np.trace(previous)))), 0)
        current_dim = max(int(round(float(np.trace(current)))), 0)
        denominator = max(1, min(previous_dim, current_dim))
        similarities.append(float(np.clip(np.trace(current @ previous) / denominator, 0.0, 1.0)))
    return np.asarray(similarities, dtype=float)


def summarize_exposure_metrics(
    metric_rows: Any,
    low_information_threshold: float,
    epsilon: float = 1.0e-12,
    weak_axis_alignment_threshold: float = 0.8,
) -> Dict[str, float]:
    information = _field(metric_rows, "axis_information_normalized")
    timestamps = _field(metric_rows, "timestamp")
    alignments = _field(metric_rows, "weak_trans_subspace_alignment")
    projectors = np.zeros((information.size, 3, 3), dtype=float)
    for row in range(3):
        for column in range(3):
            projectors[:, row, column] = _field(metric_rows, f"weak_trans_projector_{row}{column}")
    persistence = weak_subspace_persistence(projectors)
    low_mask = information < float(low_information_threshold)
    aligned = np.isfinite(alignments) & (alignments >= float(weak_axis_alignment_threshold))
    return {
        "cumulative_inverse_axis_information": cumulative_inverse_axis_information(
            information, timestamps, epsilon
        ),
        "mean_inverse_axis_information": mean_inverse_axis_information(information, timestamps, epsilon),
        "harmonic_axis_information": harmonic_axis_information(information, timestamps, epsilon),
        "low_axis_information_ratio": float(np.mean(low_mask)),
        "longest_low_information_duration_s": longest_condition_duration(low_mask, timestamps),
        "axis_information_p05": float(np.percentile(information, 5.0)),
        "axis_information_p10": float(np.percentile(information, 10.0)),
        "axis_information_p25": float(np.percentile(information, 25.0)),
        "weak_subspace_persistence_mean": float(np.mean(persistence)) if persistence.size else float("nan"),
        "weak_subspace_persistence_p10": float(np.percentile(persistence, 10.0)) if persistence.size else float("nan"),
        "weak_axis_aligned_frame_ratio": float(np.mean(aligned)),
        "longest_weak_axis_aligned_duration_s": longest_condition_duration(aligned, timestamps),
    }


def _field(rows: Any, name: str) -> np.ndarray:
    if isinstance(rows, np.ndarray) and rows.dtype.names:
        return np.asarray(rows[name], dtype=float)
    if isinstance(rows, Sequence):
        return np.asarray([float(row[name]) for row in rows if isinstance(row, Mapping)], dtype=float)
    raise TypeError("metric_rows must be a structured array or sequence of mappings")


def _positive_information(values: Sequence[float]) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size == 0:
        raise ValueError("axis_information must be a non-empty 1-D sequence")
    if not np.all(np.isfinite(array)) or np.any(array < 0.0):
        raise ValueError("axis_information must contain finite non-negative values")
    return array


def _time_weights(count: int, timestamps: Sequence[float] | None) -> np.ndarray:
    if timestamps is None:
        return np.ones(count, dtype=float)
    values = np.asarray(timestamps, dtype=float)
    if values.shape != (count,):
        raise ValueError("timestamps must match information length")
    if count == 1:
        return np.ones(1, dtype=float)
    deltas = np.diff(values)
    if np.any(deltas <= 0.0):
        raise ValueError("timestamps must be strictly increasing")
    return np.concatenate([deltas, deltas[-1:]])
