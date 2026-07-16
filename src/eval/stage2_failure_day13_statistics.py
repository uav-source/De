"""Preregistered AUROC, threshold, FPR, bootstrap, and effect statistics."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

import numpy as np


PRIMARY_STATISTIC = "huber_cusum_max"
SECONDARY_STATISTICS = (
    "abs_weak_innovation_z_huber",
    "abs_huber_window_mean",
    "huber_window_energy",
    "huber_dominant_sign_ratio",
    "huber_current_same_sign_run_length",
    "abs_huber_lag1_autocorrelation",
    "abs_huber_skewness",
)


def tie_aware_auroc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Compute Mann-Whitney AUROC with average ranks for tied scores."""

    values = np.asarray(scores, dtype=float)
    classes = np.asarray(labels, dtype=int)
    if values.ndim != 1 or classes.shape != values.shape or values.size == 0:
        raise ValueError("AUROC expects equal nonempty one-dimensional arrays")
    if not np.all(np.isfinite(values)) or not np.all(np.isin(classes, [0, 1])):
        raise ValueError("AUROC scores must be finite and labels binary")
    positive_count = int(np.count_nonzero(classes == 1))
    negative_count = int(np.count_nonzero(classes == 0))
    if positive_count == 0 or negative_count == 0:
        raise ValueError("AUROC requires positive and negative samples")
    order = np.argsort(values, kind="mergesort")
    sorted_values = values[order]
    ranks = np.empty(values.size, dtype=float)
    start = 0
    while start < values.size:
        stop = start + 1
        while stop < values.size and sorted_values[stop] == sorted_values[start]:
            stop += 1
        ranks[order[start:stop]] = 0.5 * ((start + 1) + stop)
        start = stop
    rank_sum = float(np.sum(ranks[classes == 1]))
    return float(
        (rank_sum - positive_count * (positive_count + 1) / 2.0)
        / (positive_count * negative_count)
    )


def nearest_rank_threshold(scores: Sequence[float], quantile: float = 0.90) -> float:
    """Return s_(ceil(q*n)) using the preregistered one-based nearest rank."""

    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("threshold calibration requires finite nonempty scores")
    if not 0.0 < float(quantile) <= 1.0:
        raise ValueError("nearest-rank quantile must lie in (0, 1]")
    ordered = np.sort(values, kind="mergesort")
    index = int(math.ceil(float(quantile) * ordered.size)) - 1
    return float(ordered[index])


def threshold_false_positive_rate(scores: Sequence[float], threshold: float) -> Mapping[str, Any]:
    values = np.asarray(scores, dtype=float)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("FPR requires finite nonempty scores")
    if not math.isfinite(float(threshold)):
        raise ValueError("FPR threshold must be finite")
    false_count = int(np.count_nonzero(values > float(threshold)))
    return {
        "eligible_frame_count": int(values.size),
        "false_positive_frame_count": false_count,
        "fpr": float(false_count / values.size),
    }


def calibrate_diagnostic_threshold(
    rows: Sequence[Mapping[str, Any]], quantile: float = 0.90
) -> Mapping[str, Any]:
    """Calibrate only from clean calibration rows that pass primary eligibility."""

    if any(str(row.get("role")) != "calibration" for row in rows):
        raise ValueError("calibration threshold received a non-calibration row")
    if any(str(row.get("stress")) != "clean" for row in rows):
        raise ValueError("calibration threshold received coherent or gross scores")
    forbidden = {"pose_gt", "axis_per_frame", "gt_axis", "oracle_axis"}
    if any(forbidden & set(row) for row in rows):
        raise ValueError("calibration threshold received a forbidden GT field")
    scores = [float(row["primary_score"]) for row in rows if primary_score_eligible(row)]
    threshold = nearest_rank_threshold(scores, quantile)
    fpr = threshold_false_positive_rate(scores, threshold)
    return {
        "primary_statistic": PRIMARY_STATISTIC,
        "threshold_quantile": float(quantile),
        "threshold_quantile_rule": "nearest_rank",
        "threshold_comparison_operator": ">",
        "threshold_value": threshold,
        "calibration_score_count": len(scores),
        "calibration_empirical_fpr": fpr["fpr"],
    }


def primary_score_eligible(row: Mapping[str, Any]) -> bool:
    try:
        score = float(row.get("primary_score", row.get(PRIMARY_STATISTIC, float("nan"))))
    except (TypeError, ValueError):
        return False
    return bool(row.get("stat_input_valid")) and bool(row.get("window_ready")) and math.isfinite(score)


def statistic_score(row: Mapping[str, Any], statistic: str) -> float:
    if statistic == PRIMARY_STATISTIC:
        return float(row.get("primary_score", row.get(PRIMARY_STATISTIC)))
    sources = {
        "abs_weak_innovation_z_huber": ("weak_innovation_z_huber", True),
        "abs_huber_window_mean": ("huber_window_mean", True),
        "huber_window_energy": ("huber_window_energy", False),
        "huber_dominant_sign_ratio": ("huber_dominant_sign_ratio", False),
        "huber_current_same_sign_run_length": (
            "huber_current_same_sign_run_length", False
        ),
        "abs_huber_lag1_autocorrelation": ("huber_lag1_autocorrelation", True),
        "abs_huber_skewness": ("huber_skewness", True),
    }
    if statistic not in sources:
        raise ValueError(f"unregistered Day 13 statistic: {statistic}")
    source, absolute = sources[statistic]
    value = float(row[source])
    return abs(value) if absolute else value


def analysis_population_rows(
    frame_scores: Sequence[Mapping[str, Any]], sweep: str, statistic: str
) -> Sequence[Mapping[str, Any]]:
    """Select only held-out matched clean/coherent rows for one sweep AUROC."""

    if sweep not in {"geometry", "observation"}:
        raise ValueError("AUROC sweep must be geometry or observation")
    selected = []
    for row in frame_scores:
        if str(row.get("role")) != "evaluation" or str(row.get("sweep")) != sweep:
            continue
        stress = str(row.get("stress"))
        if stress == "coherent_subhuber_slip":
            include = bool(row.get("stress_active")) and primary_score_eligible(row)
            label = 1
        elif stress == "clean":
            include = primary_score_eligible(row)
            label = 0
        else:
            include = False
            label = -1
        if not include:
            continue
        value = statistic_score(row, statistic)
        if math.isfinite(value):
            selected.append({**row, "analysis_score": value, "analysis_label": label})
    if not selected or not {int(row["analysis_label"]) for row in selected} == {0, 1}:
        raise ValueError(f"Day 13 {sweep} AUROC population is incomplete")
    return selected


def block_bootstrap_auroc(
    rows: Sequence[Mapping[str, Any]],
    repetitions: int = 5000,
    seed: int = 23131,
    block_field: str = "geometry_seed",
) -> Mapping[str, Any]:
    """Bootstrap AUROC by resampling complete geometry blocks."""

    if block_field != "geometry_seed":
        raise ValueError("Day 13 forbids frame bootstrap")
    if int(repetitions) != 5000 or int(seed) != 23131:
        raise ValueError("Day 13 bootstrap settings are frozen")
    blocks = sorted({int(row[block_field]) for row in rows})
    if len(blocks) != 10:
        raise ValueError("Day 13 evaluation bootstrap requires 10 geometry blocks")
    positives = {
        block: np.asarray([
            float(row["analysis_score"]) for row in rows
            if int(row[block_field]) == block and int(row["analysis_label"]) == 1
        ], dtype=float)
        for block in blocks
    }
    negatives = {
        block: np.asarray([
            float(row["analysis_score"]) for row in rows
            if int(row[block_field]) == block and int(row["analysis_label"]) == 0
        ], dtype=float)
        for block in blocks
    }
    contribution = np.zeros((len(blocks), len(blocks)), dtype=float)
    positive_counts = np.zeros(len(blocks), dtype=float)
    negative_counts = np.zeros(len(blocks), dtype=float)
    for i, first in enumerate(blocks):
        positive_counts[i] = positives[first].size
        for j, second in enumerate(blocks):
            if i == 0:
                negative_counts[j] = negatives[second].size
            p = positives[first][:, None]
            n = negatives[second][None, :]
            contribution[i, j] = float(np.sum(p > n) + 0.5 * np.sum(p == n))
    rng = np.random.default_rng(int(seed))
    values = []
    invalid = 0
    for _ in range(int(repetitions)):
        sampled = rng.integers(0, len(blocks), size=len(blocks))
        counts = np.bincount(sampled, minlength=len(blocks)).astype(float)
        positive_count = float(counts @ positive_counts)
        negative_count = float(counts @ negative_counts)
        if positive_count <= 0.0 or negative_count <= 0.0:
            invalid += 1
            continue
        numerator = float(counts @ contribution @ counts)
        values.append(numerator / (positive_count * negative_count))
    if not values:
        raise ValueError("Day 13 AUROC bootstrap produced no valid samples")
    array = np.asarray(values, dtype=float)
    point = tie_aware_auroc(
        [float(row["analysis_score"]) for row in rows],
        [int(row["analysis_label"]) for row in rows],
    )
    return {
        "point_estimate": point,
        "bootstrap_median": float(np.median(array)),
        "ci95_lower": float(np.quantile(array, 0.025)),
        "ci95_upper": float(np.quantile(array, 0.975)),
        "valid_bootstrap_count": int(array.size),
        "invalid_bootstrap_count": int(invalid),
    }


def block_bootstrap_fpr(
    rows: Sequence[Mapping[str, Any]],
    threshold: float,
    repetitions: int = 5000,
    seed: int = 23131,
    block_field: str = "geometry_seed",
) -> Mapping[str, Any]:
    if block_field != "geometry_seed":
        raise ValueError("Day 13 forbids frame bootstrap")
    if int(repetitions) != 5000 or int(seed) != 23131:
        raise ValueError("Day 13 bootstrap settings are frozen")
    blocks = sorted({int(row[block_field]) for row in rows})
    if len(blocks) != 10:
        raise ValueError("Day 13 FPR bootstrap requires 10 geometry blocks")
    eligible = np.asarray([
        sum(1 for row in rows if int(row[block_field]) == block)
        for block in blocks
    ], dtype=float)
    false = np.asarray([
        sum(
            int(float(row["primary_score"]) > float(threshold))
            for row in rows if int(row[block_field]) == block
        )
        for block in blocks
    ], dtype=float)
    rng = np.random.default_rng(int(seed))
    values = []
    invalid = 0
    for _ in range(int(repetitions)):
        sampled = rng.integers(0, len(blocks), size=len(blocks))
        counts = np.bincount(sampled, minlength=len(blocks)).astype(float)
        denominator = float(counts @ eligible)
        if denominator <= 0.0:
            invalid += 1
            continue
        values.append(float(counts @ false) / denominator)
    array = np.asarray(values, dtype=float)
    if not array.size:
        raise ValueError("Day 13 FPR bootstrap produced no valid samples")
    point = threshold_false_positive_rate(
        [float(row["primary_score"]) for row in rows], threshold
    )
    return {
        **point,
        "bootstrap_median": float(np.median(array)),
        "ci95_lower": float(np.quantile(array, 0.025)),
        "ci95_upper": float(np.quantile(array, 0.975)),
        "valid_bootstrap_count": int(array.size),
        "invalid_bootstrap_count": int(invalid),
    }


def build_auroc_summary(frame_scores: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
    rows = []
    for statistic in (PRIMARY_STATISTIC,) + SECONDARY_STATISTICS:
        for sweep in ("geometry", "observation"):
            population = analysis_population_rows(frame_scores, sweep, statistic)
            bootstrap = block_bootstrap_auroc(population)
            rows.append({
                "statistic_name": statistic,
                "statistic_role": (
                    "primary" if statistic == PRIMARY_STATISTIC else "secondary_descriptive"
                ),
                "sweep": sweep,
                "positive_frame_count": sum(
                    int(row["analysis_label"] == 1) for row in population
                ),
                "negative_frame_count": sum(
                    int(row["analysis_label"] == 0) for row in population
                ),
                "auroc": bootstrap["point_estimate"],
                "bootstrap_median": bootstrap["bootstrap_median"],
                "ci95_lower": bootstrap["ci95_lower"],
                "ci95_upper": bootstrap["ci95_upper"],
                "valid_bootstrap_count": bootstrap["valid_bootstrap_count"],
                "invalid_bootstrap_count": bootstrap["invalid_bootstrap_count"],
                "analysis_population": "evaluation_matched_clean_vs_coherent_active",
                "threshold_used": False,
                "used_for_primary_day14_review": statistic == PRIMARY_STATISTIC,
            })
    return rows


def build_fpr_outputs(
    frame_scores: Sequence[Mapping[str, Any]], threshold: float
) -> Tuple[Sequence[Mapping[str, Any]], Sequence[Mapping[str, Any]]]:
    clean = [
        row for row in frame_scores
        if str(row.get("role")) == "evaluation"
        and str(row.get("stress")) == "clean"
        and primary_score_eligible(row)
    ]
    populations = {
        "clean_all": clean,
        "weak_clean": [row for row in clean if str(row["sweep"]) in {"geometry", "observation"}],
        "open_control": [row for row in clean if str(row["sweep"]) == "open_control"],
    }
    summary = []
    for name, values in populations.items():
        audit = block_bootstrap_fpr(values, threshold)
        summary.append({
            "population": name,
            "threshold_value": float(threshold),
            "comparison_operator": ">",
            "eligible_frame_count": audit["eligible_frame_count"],
            "false_positive_frame_count": audit["false_positive_frame_count"],
            "fpr": audit["fpr"],
            "bootstrap_median": audit["bootstrap_median"],
            "ci95_lower": audit["ci95_lower"],
            "ci95_upper": audit["ci95_upper"],
        })
    per_geometry = []
    for geometry_seed in sorted({int(row["geometry_seed"]) for row in clean}):
        for name, values in populations.items():
            selected = [row for row in values if int(row["geometry_seed"]) == geometry_seed]
            point = threshold_false_positive_rate(
                [float(row["primary_score"]) for row in selected], threshold
            )
            per_geometry.append({
                "geometry_seed": geometry_seed,
                "population": name,
                "threshold_value": float(threshold),
                "comparison_operator": ">",
                **point,
            })
    return summary, per_geometry


def build_geometry_effects(
    frame_scores: Sequence[Mapping[str, Any]]
) -> Sequence[Mapping[str, Any]]:
    index = {}
    for row in frame_scores:
        if str(row.get("role")) != "evaluation" or not primary_score_eligible(row):
            continue
        if str(row.get("sweep")) not in {"geometry", "observation"}:
            continue
        key = tuple(row[field] for field in (
            "sweep", "level", "geometry_seed", "sensor_seed", "process_seed", "frame_index"
        ))
        index[(str(row["stress"]),) + key] = row
    differences = defaultdict(list)
    for key, coherent in index.items():
        if key[0] != "coherent_subhuber_slip" or not bool(coherent.get("stress_active")):
            continue
        clean = index.get(("clean",) + key[1:])
        if clean is None:
            continue
        group = (int(coherent["geometry_seed"]), str(coherent["sweep"]))
        differences[group].append(float(coherent["primary_score"]) - float(clean["primary_score"]))
    output = []
    for group in sorted(differences):
        values = np.asarray(differences[group], dtype=float)
        output.append({
            "geometry_seed": group[0],
            "sweep": group[1],
            "matched_frame_count": int(values.size),
            "median_score_difference": float(np.median(values)),
            "q25_score_difference": float(np.quantile(values, 0.25)),
            "q75_score_difference": float(np.quantile(values, 0.75)),
            "positive_effect": bool(float(np.median(values)) > 0.0),
        })
    for sweep in ("geometry", "observation"):
        if len([row for row in output if row["sweep"] == sweep]) != 10:
            raise ValueError(f"Day 13 geometry effects dropped an evaluation geometry: {sweep}")
    return output


def build_primary_roc_points(
    frame_scores: Sequence[Mapping[str, Any]]
) -> Sequence[Mapping[str, Any]]:
    output = []
    for sweep in ("geometry", "observation"):
        population = analysis_population_rows(frame_scores, sweep, PRIMARY_STATISTIC)
        scores = np.asarray([float(row["analysis_score"]) for row in population])
        labels = np.asarray([int(row["analysis_label"]) for row in population])
        positives = int(np.sum(labels == 1))
        negatives = int(np.sum(labels == 0))
        for threshold in sorted(set(scores.tolist()), reverse=True):
            predicted = scores > float(threshold)
            output.append({
                "statistic_name": PRIMARY_STATISTIC,
                "sweep": sweep,
                "threshold": float(threshold),
                "comparison_operator": ">",
                "true_positive_rate": float(np.sum(predicted & (labels == 1)) / positives),
                "false_positive_rate": float(np.sum(predicted & (labels == 0)) / negatives),
                "positive_frame_count": positives,
                "negative_frame_count": negatives,
            })
    return output
