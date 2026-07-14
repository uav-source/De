"""Pre-registered hierarchical statistics for Metric Redesign Stage 1b."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np
from scipy.stats import kendalltau, spearmanr


def safe_spearman(x: Sequence[float], y: Sequence[float]) -> float:
    first = np.asarray(x, dtype=float)
    second = np.asarray(y, dtype=float)
    valid = np.isfinite(first) & np.isfinite(second)
    first, second = first[valid], second[valid]
    if first.size < 3 or np.allclose(first, first[0]) or np.allclose(second, second[0]):
        return float("nan")
    return float(spearmanr(first, second).statistic)


def block_bootstrap_spearman(
    rows: Sequence[Mapping[str, Any]],
    x_field: str,
    y_field: str,
    repetitions: int = 5000,
    seed: int = 7861,
    block_field: str = "geometry_seed",
) -> Dict[str, Any]:
    blocks: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        blocks[str(row[block_field])].append(row)
    keys = sorted(blocks)
    rho = _row_spearman(rows, x_field, y_field)
    if len(keys) < 2:
        return {
            "rho": rho,
            "bootstrap_ci_low": float("nan"),
            "bootstrap_ci_high": float("nan"),
            "bootstrap_method": "geometry_seed_block_percentile",
            "bootstrap_blocks": len(keys),
            "bootstrap_repetitions": int(repetitions),
        }
    rng = np.random.default_rng(int(seed))
    samples = []
    for _ in range(int(repetitions)):
        selected = rng.choice(keys, size=len(keys), replace=True)
        sampled: List[Mapping[str, Any]] = []
        for key in selected:
            sampled.extend(blocks[str(key)])
        value = _row_spearman(sampled, x_field, y_field)
        if np.isfinite(value):
            samples.append(value)
    return {
        "rho": rho,
        "bootstrap_ci_low": float(np.percentile(samples, 2.5)) if samples else float("nan"),
        "bootstrap_ci_high": float(np.percentile(samples, 97.5)) if samples else float("nan"),
        "bootstrap_method": "geometry_seed_block_percentile",
        "bootstrap_blocks": len(keys),
        "bootstrap_repetitions": int(repetitions),
    }


def paired_monotonicity(
    rows: Sequence[Mapping[str, Any]],
    field: str,
    level_order: Sequence[str],
    risk_direction: int,
    tolerance: float = 1.0e-12,
) -> Dict[str, float]:
    groups: Dict[Tuple[int, int], Dict[str, float]] = defaultdict(dict)
    for row in rows:
        groups[(int(row["geometry_seed"]), int(row["sensor_seed"]))][str(row["level"])] = (
            float(row[field]) * int(risk_direction)
        )
    pair_checks: List[bool] = []
    group_taus: List[float] = []
    severity = np.arange(len(level_order), dtype=float)
    for values in groups.values():
        if not all(level in values for level in level_order):
            continue
        ordered = np.asarray([values[level] for level in level_order], dtype=float)
        pair_checks.extend(bool(right + tolerance >= left) for left, right in zip(ordered[:-1], ordered[1:]))
        tau = float(kendalltau(severity, ordered).statistic)
        if np.isfinite(tau):
            group_taus.append(tau)
    return {
        "monotonic_pair_rate": float(np.mean(pair_checks)) if pair_checks else float("nan"),
        "median_group_kendall_tau": float(np.median(group_taus)) if group_taus else float("nan"),
        "positive_tau_group_ratio": float(np.mean(np.asarray(group_taus) > 0.0)) if group_taus else float("nan"),
        "paired_group_count": len(group_taus),
    }


def within_level_residual_spearman(
    rows: Sequence[Mapping[str, Any]],
    train_rows: Sequence[Mapping[str, Any]],
    x_field: str,
    y_field: str,
) -> float:
    train_by_level: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in train_rows:
        train_by_level[str(row["level"])].append(row)
    medians = {
        level: (
            float(np.median([float(row[x_field]) for row in values])),
            float(np.median([float(row[y_field]) for row in values])),
        )
        for level, values in train_by_level.items()
    }
    x_residual, y_residual = [], []
    for row in rows:
        level = str(row["level"])
        if level not in medians:
            continue
        x_median, y_median = medians[level]
        x_residual.append(float(row[x_field]) - x_median)
        y_residual.append(float(row[y_field]) - y_median)
    return safe_spearman(x_residual, y_residual)


def _row_spearman(rows: Sequence[Mapping[str, Any]], x_field: str, y_field: str) -> float:
    return safe_spearman([float(row[x_field]) for row in rows], [float(row[y_field]) for row in rows])
