"""Frozen descriptive and exploratory statistics for Development."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np
from scipy.stats import spearmanr


TRANSLATION_VECTOR_FIELDS = ("translation_x_m", "translation_y_m", "translation_z_m")
ROTATION_VECTOR_FIELDS = ("rotation_x_rad", "rotation_y_rad", "rotation_z_rad")


def systematic_fraction_translation(
    translation_vectors: np.ndarray, epsilon: float = 1.0e-12
) -> float | None:
    values = np.asarray(translation_vectors, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 3 or values.shape[0] == 0:
        raise ValueError("translation_vectors must be non-empty Nx3")
    denominator = float(np.mean(np.linalg.norm(values, axis=1)))
    if denominator <= float(epsilon):
        return None
    return float(np.linalg.norm(np.mean(values, axis=0)) / denominator)


def repeatability_covariance(vectors: np.ndarray, ddof: int = 1) -> np.ndarray:
    values = np.asarray(vectors, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 3:
        raise ValueError("vectors must have shape [N,3]")
    if values.shape[0] <= ddof:
        return np.zeros((3, 3), dtype=np.float64)
    return np.asarray(np.cov(values, rowvar=False, ddof=ddof), dtype=np.float64)


def _summary_for_rows(rows: Sequence[Mapping[str, Any]], ddof: int, epsilon: float) -> dict[str, Any]:
    translation = np.asarray(
        [[float(row[field]) for field in TRANSLATION_VECTOR_FIELDS] for row in rows],
        dtype=np.float64,
    )
    rotation = np.asarray(
        [[float(row[field]) for field in ROTATION_VECTOR_FIELDS] for row in rows],
        dtype=np.float64,
    )
    translation_error = np.asarray([float(row["translation_error_m"]) for row in rows])
    rotation_error = np.asarray([float(row["rotation_error_rad"]) for row in rows])
    mean_t = np.mean(translation, axis=0)
    mean_r = np.mean(rotation, axis=0)
    cov_t = repeatability_covariance(translation, ddof=ddof)
    cov_r = repeatability_covariance(rotation, ddof=ddof)
    tq = np.quantile(translation_error, [0.25, 0.50, 0.75, 0.95])
    rq = np.quantile(rotation_error, [0.25, 0.50, 0.75, 0.95])
    return {
        "trial_count": len(rows),
        "mean_translation_x_m": float(mean_t[0]),
        "mean_translation_y_m": float(mean_t[1]),
        "mean_translation_z_m": float(mean_t[2]),
        "systematic_translation_offset_m": float(np.linalg.norm(mean_t)),
        "translation_repeatability_covariance": json.dumps(cov_t.tolist(), separators=(",", ":")),
        "translation_repeatability_rms_m": float(math.sqrt(max(float(np.trace(cov_t)), 0.0))),
        "mean_rotation_x_rad": float(mean_r[0]),
        "mean_rotation_y_rad": float(mean_r[1]),
        "mean_rotation_z_rad": float(mean_r[2]),
        "systematic_rotation_offset_rad": float(np.linalg.norm(mean_r)),
        "rotation_repeatability_covariance": json.dumps(cov_r.tolist(), separators=(",", ":")),
        "rotation_repeatability_rms_rad": float(math.sqrt(max(float(np.trace(cov_r)), 0.0))),
        "translation_error_q25_m": float(tq[0]),
        "translation_error_median_m": float(tq[1]),
        "translation_error_q75_m": float(tq[2]),
        "translation_error_iqr_m": float(tq[2] - tq[0]),
        "translation_error_q95_m": float(tq[3]),
        "rotation_error_q25_rad": float(rq[0]),
        "rotation_error_median_rad": float(rq[1]),
        "rotation_error_q75_rad": float(rq[2]),
        "rotation_error_iqr_rad": float(rq[2] - rq[0]),
        "rotation_error_q95_rad": float(rq[3]),
        "systematic_fraction_translation": systematic_fraction_translation(
            translation, epsilon=epsilon
        ),
    }


def aggregate_repeated_measurements(
    rows: Iterable[Mapping[str, Any]],
    group_fields: Sequence[str] = (
        "scene_variant",
        "geometry_seed",
        "noise_condition",
        "registration_backend",
    ),
    *,
    ddof: int = 1,
    denominator_epsilon: float = 1.0e-12,
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in group_fields)].append(row)
    output = []
    for key in sorted(groups, key=lambda value: tuple(str(item) for item in value)):
        result = {field: value for field, value in zip(group_fields, key)}
        result.update(_summary_for_rows(groups[key], ddof, denominator_epsilon))
        output.append(result)
    return output


def exploratory_block_bootstrap_interval(
    rows: Sequence[Mapping[str, Any]],
    value_field: str,
    *,
    block_field: str = "geometry_seed",
    repetitions: int = 1000,
    seed: int,
) -> tuple[float, float]:
    blocks: dict[Any, np.ndarray] = {}
    for block in sorted({row[block_field] for row in rows}, key=str):
        blocks[block] = np.asarray(
            [float(row[value_field]) for row in rows if row[block_field] == block],
            dtype=np.float64,
        )
    if not blocks:
        raise ValueError("bootstrap requires at least one geometry block")
    keys = list(blocks)
    rng = np.random.Generator(np.random.PCG64(int(seed)))
    values = np.empty(int(repetitions), dtype=np.float64)
    for index in range(int(repetitions)):
        selected = rng.integers(0, len(keys), size=len(keys))
        sample = np.concatenate([blocks[keys[int(item)]] for item in selected])
        values[index] = np.median(sample)
    lower, upper = np.quantile(values, [0.025, 0.975])
    return float(lower), float(upper)


def safe_spearman(x: Sequence[float], y: Sequence[float]) -> float | None:
    left = np.asarray(x, dtype=np.float64)
    right = np.asarray(y, dtype=np.float64)
    mask = np.isfinite(left) & np.isfinite(right)
    if int(np.sum(mask)) < 2:
        return None
    if np.unique(left[mask]).size < 2 or np.unique(right[mask]).size < 2:
        return None
    result = spearmanr(left[mask], right[mask])
    return float(result.statistic) if np.isfinite(result.statistic) else None


__all__ = [
    "aggregate_repeated_measurements",
    "exploratory_block_bootstrap_interval",
    "repeatability_covariance",
    "safe_spearman",
    "systematic_fraction_translation",
]
