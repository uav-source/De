"""Statistical validity checks for Day 10 metric comparison."""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np


try:  # pragma: no cover - fallback is exercised when scipy is unavailable.
    from scipy import stats as scipy_stats
except Exception:  # pragma: no cover
    scipy_stats = None


def spearman_corr(x: Iterable[float], y: Iterable[float]) -> Tuple[float, float]:
    """Return Spearman rho and p-value, or NaN values when undefined."""

    clean_x, clean_y = finite_pair(x, y)
    if clean_x.size < 3 or is_constant(clean_x) or is_constant(clean_y):
        return float("nan"), float("nan")

    if scipy_stats is not None:
        result = scipy_stats.spearmanr(clean_x, clean_y)
        return float(result.statistic), float(result.pvalue)

    rho = pearson_corr(rankdata_average(clean_x), rankdata_average(clean_y))
    return rho, approximate_corr_p_value(rho, clean_x.size)


def pearson_corr(x: Iterable[float], y: Iterable[float]) -> float:
    """Return Pearson r, or NaN when undefined."""

    clean_x, clean_y = finite_pair(x, y)
    if clean_x.size < 3 or is_constant(clean_x) or is_constant(clean_y):
        return float("nan")
    return float(np.corrcoef(clean_x, clean_y)[0, 1])


def bootstrap_ci_corr(
    x: Iterable[float],
    y: Iterable[float],
    n_boot: int = 1000,
    random_seed: int = 42,
) -> Tuple[float, float]:
    """Bootstrap a 95% confidence interval for Spearman rho."""

    clean_x, clean_y = finite_pair(x, y)
    if clean_x.size < 3 or is_constant(clean_x) or is_constant(clean_y):
        return float("nan"), float("nan")
    rng = np.random.default_rng(int(random_seed))
    samples: List[float] = []
    for _ in range(int(n_boot)):
        indices = rng.integers(0, clean_x.size, size=clean_x.size)
        rho, _ = spearman_corr(clean_x[indices], clean_y[indices])
        if np.isfinite(rho):
            samples.append(float(rho))
    if not samples:
        return float("nan"), float("nan")
    low, high = np.percentile(np.asarray(samples, dtype=float), [2.5, 97.5])
    return float(low), float(high)


def safe_auc_if_binary_available(score: Iterable[float], label: Iterable[float]) -> float:
    """Return ROC AUC for binary labels, or NaN if labels are not binary usable."""

    clean_score, clean_label = finite_pair(score, label)
    if clean_score.size < 2:
        return float("nan")
    labels = clean_label.astype(int)
    if not np.all(np.isin(labels, [0, 1])):
        return float("nan")
    n_pos = int(np.sum(labels == 1))
    n_neg = int(np.sum(labels == 0))
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = rankdata_average(clean_score)
    rank_sum_pos = float(np.sum(ranks[labels == 1]))
    auc = (rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(np.clip(auc, 0.0, 1.0))


def rank_metrics_by_correlation(metric_table: Sequence[Mapping[str, object]], target: str) -> List[Dict[str, object]]:
    """Rank metric-result rows by absolute finite Spearman correlation."""

    candidates = [dict(row) for row in metric_table if row.get("target_name") == target]

    def sort_key(row: Mapping[str, object]) -> Tuple[int, float]:
        value = to_float(row.get("spearman_rho"))
        if not np.isfinite(value):
            return (1, float("inf"))
        return (0, -abs(float(value)))

    ranked = sorted(candidates, key=sort_key)
    for rank, row in enumerate(ranked, start=1):
        row["rank"] = rank
    return ranked


def leave_one_sequence_out_correlation(
    rows: Sequence[Mapping[str, object]],
    metric_name: str,
    target_name: str,
) -> List[Dict[str, object]]:
    """Compute train/test correlation by holding out each sequence."""

    sequences = sorted({str(row["sequence_id"]) for row in rows})
    outputs: List[Dict[str, object]] = []
    for held_out in sequences:
        train = [row for row in rows if str(row["sequence_id"]) != held_out]
        test = [row for row in rows if str(row["sequence_id"]) == held_out]
        train_metric, train_target = arrays_from_rows(train, metric_name, target_name)
        test_metric, test_target = arrays_from_rows(test, metric_name, target_name)
        train_rho, _ = spearman_corr(train_metric, train_target)
        test_rho, _ = spearman_corr(test_metric, test_target)
        outputs.append(
            {
                "held_out_sequence": held_out,
                "metric_name": metric_name,
                "target_name": target_name,
                "train_spearman_rho": train_rho,
                "test_spearman_rho_or_auc": test_rho,
                "valid_train_sample_count": int(finite_pair(train_metric, train_target)[0].size),
                "valid_test_sample_count": int(finite_pair(test_metric, test_target)[0].size),
            }
        )
    return outputs


def make_high_axis_drift_flag(axis_drift_rate: Iterable[float], percentile: float = 75.0) -> np.ndarray:
    """Flag windows whose axis drift rate is above the global percentile."""

    values = np.asarray(axis_drift_rate, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return np.zeros(values.shape, dtype=int)
    threshold = float(np.percentile(finite, float(percentile)))
    return np.where(np.isfinite(values) & (values > threshold), 1, 0).astype(int)


def finite_pair(x: Iterable[float], y: Iterable[float]) -> Tuple[np.ndarray, np.ndarray]:
    x_array = np.asarray(list(x), dtype=float)
    y_array = np.asarray(list(y), dtype=float)
    if x_array.shape != y_array.shape:
        raise ValueError(f"Input shapes differ: {x_array.shape} vs {y_array.shape}")
    finite = np.isfinite(x_array) & np.isfinite(y_array)
    return x_array[finite], y_array[finite]


def arrays_from_rows(
    rows: Sequence[Mapping[str, object]],
    metric_name: str,
    target_name: str,
) -> Tuple[np.ndarray, np.ndarray]:
    metric = np.asarray([to_float(row.get(metric_name)) for row in rows], dtype=float)
    target = np.asarray([to_float(row.get(target_name)) for row in rows], dtype=float)
    return metric, target


def rankdata_average(values: Iterable[float]) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.size, dtype=float)
    sorted_values = values[order]
    start = 0
    while start < values.size:
        end = start + 1
        while end < values.size and sorted_values[end] == sorted_values[start]:
            end += 1
        rank = 0.5 * (start + end - 1) + 1.0
        ranks[order[start:end]] = rank
        start = end
    return ranks


def is_constant(values: np.ndarray) -> bool:
    if values.size == 0:
        return True
    return bool(np.max(values) - np.min(values) <= 1.0e-12)


def approximate_corr_p_value(rho: float, n: int) -> float:
    if not np.isfinite(rho) or n < 3:
        return float("nan")
    if abs(rho) >= 1.0:
        return 0.0
    t_value = abs(rho) * math.sqrt((n - 2.0) / max(1.0 - rho * rho, 1.0e-12))
    return float(math.erfc(t_value / math.sqrt(2.0)))


def to_float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")

