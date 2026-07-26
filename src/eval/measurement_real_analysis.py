"""Preregistered statistics and gates for the Measurement real-data pilot."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy.stats import rankdata, spearmanr


CONTROL_MAX_TRIGGER_RATIO = 0.20
CONTROL_MAX_CONSECUTIVE_TRIGGERS = 5
VALID_DETECTOR_RATIO_MINIMUM = 0.90
DETECTOR_CORE_MEAN_TARGET_MS = 10.0
TOTAL_ADDED_Q95_TARGET_MS = 20.0
DIRECTION_MEDIAN_MAX_DEG = 30.0
ODI_AUROC_MINIMUM = 0.70
ODI_ABS_SPEARMAN_MINIMUM = 0.40


def summary_statistics(values: Sequence[float]) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    array = array[np.isfinite(array)]
    if array.size == 0:
        return {
            "count": 0,
            "median": float("nan"),
            "iqr": float("nan"),
            "mean": float("nan"),
            "standard_deviation": float("nan"),
            "q05": float("nan"),
            "q95": float("nan"),
        }
    q25, q75 = np.quantile(array, [0.25, 0.75])
    return {
        "count": int(array.size),
        "median": float(np.median(array)),
        "iqr": float(q75 - q25),
        "mean": float(np.mean(array)),
        "standard_deviation": float(np.std(array, ddof=1))
        if array.size > 1
        else 0.0,
        "q05": float(np.quantile(array, 0.05)),
        "q95": float(np.quantile(array, 0.95)),
    }


def spearman_correlation(values: Sequence[float], targets: Sequence[float]) -> dict[str, Any]:
    x = np.asarray(values, dtype=np.float64)
    y = np.asarray(targets, dtype=np.float64)
    valid = np.isfinite(x) & np.isfinite(y)
    if int(np.sum(valid)) < 3 or np.unique(x[valid]).size < 2 or np.unique(y[valid]).size < 2:
        return {"count": int(np.sum(valid)), "spearman_rho": float("nan"), "spearman_pvalue": float("nan")}
    result = spearmanr(x[valid], y[valid])
    return {
        "count": int(np.sum(valid)),
        "spearman_rho": float(result.statistic),
        "spearman_pvalue": float(result.pvalue),
    }


def binary_ranking_metrics(labels: Sequence[int], scores: Sequence[float]) -> dict[str, Any]:
    y = np.asarray(labels, dtype=np.int64)
    score = np.asarray(scores, dtype=np.float64)
    valid = np.isfinite(score) & np.isin(y, [0, 1])
    y, score = y[valid], score[valid]
    positive_count = int(np.sum(y == 1))
    negative_count = int(np.sum(y == 0))
    if positive_count == 0 or negative_count == 0:
        return {
            "count": int(y.size),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "auroc": float("nan"),
            "pr_auc_average_precision": float("nan"),
        }
    ranks = rankdata(score, method="average")
    positive_rank_sum = float(np.sum(ranks[y == 1]))
    auroc = (
        positive_rank_sum - positive_count * (positive_count + 1) / 2.0
    ) / (positive_count * negative_count)
    order = np.argsort(-score, kind="stable")
    ordered = y[order]
    true_positives = np.cumsum(ordered == 1)
    ranks_from_top = np.arange(1, ordered.size + 1)
    precision = true_positives / ranks_from_top
    average_precision = float(np.sum(precision[ordered == 1]) / positive_count)
    return {
        "count": int(y.size),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "auroc": float(auroc),
        "pr_auc_average_precision": average_precision,
    }


def maximum_consecutive_true(values: Sequence[bool]) -> int:
    maximum = current = 0
    for value in values:
        if bool(value):
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return maximum


def runtime_summary(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    fields = (
        ("capture_core_ms", None, None),
        ("detector_core_ms", DETECTOR_CORE_MEAN_TARGET_MS, "mean"),
        ("logging_ms", None, None),
        ("total_added_ms", TOTAL_ADDED_Q95_TARGET_MS, "q95"),
    )
    output = []
    for field, target, target_statistic in fields:
        statistics = summary_statistics([float(row[field]) for row in rows])
        if target is None:
            target_pass: bool | str = "NOT_GATED"
        elif target_statistic == "mean":
            target_pass = float(statistics["mean"]) <= target
        else:
            target_pass = float(statistics["q95"]) <= target
        output.append(
            {
                "component": field,
                "mean_ms": statistics["mean"],
                "q95_ms": statistics["q95"],
                "target_statistic": target_statistic or "NONE",
                "target_ms": target if target is not None else "",
                "target_pass": target_pass,
            }
        )
    return output


def evaluate_pilot_gates(inputs: Mapping[str, Any]) -> dict[str, Any]:
    engineering_conditions = {
        "python311_full_pytest_pass": bool(inputs["python311_full_pytest_pass"]),
        "bag_validation_pass": bool(inputs["bag_validation_pass"]),
        "point_time_unit_pass": bool(inputs["point_time_unit_pass"]),
        "extrinsic_direction_pass": bool(inputs["extrinsic_direction_pass"]),
        "no_reference_dependency_pass": int(inputs["reference_input_count"]) == 0,
        "same_call_mutation_pass": int(inputs["same_call_mutation_count"]) == 0,
        "detector_feedback_pass": int(inputs["detector_feedback_count"]) == 0,
        "frozen_detector_determinism_pass": int(inputs["frozen_mismatch_count"]) == 0,
        "finite_detector_output_pass": int(inputs["nonfinite_output_count"]) == 0,
        "fastlio2_crash_pass": int(inputs["fastlio2_crash_count"]) == 0,
        "valid_detector_ratio_pass": float(inputs["valid_detector_ratio"])
        >= VALID_DETECTOR_RATIO_MINIMUM,
    }
    runtime_conditions = {
        "detector_core_mean_target_pass": float(inputs["detector_core_mean_ms"])
        <= DETECTOR_CORE_MEAN_TARGET_MS,
        "total_added_q95_target_pass": float(inputs["total_added_q95_ms"])
        <= TOTAL_ADDED_Q95_TARGET_MS,
    }
    scientific_conditions = {
        "frozen_structural_and_control_intervals": bool(
            inputs["frozen_intervals_available"]
        ),
        "same_input_all_metrics": bool(inputs["same_input_all_metrics"]),
        "structural_direction_median_pass": math.isfinite(
            float(inputs["structural_direction_median_deg"])
        )
        and float(inputs["structural_direction_median_deg"])
        <= DIRECTION_MEDIAN_MAX_DEG,
        "reliable_better_than_unreliable": math.isfinite(
            float(inputs["reliable_direction_median_deg"])
        )
        and math.isfinite(float(inputs["unreliable_direction_median_deg"]))
        and float(inputs["reliable_direction_median_deg"])
        < float(inputs["unreliable_direction_median_deg"]),
        "odi_effectiveness_pass": (
            math.isfinite(float(inputs["odi_auroc"]))
            and float(inputs["odi_auroc"]) >= ODI_AUROC_MINIMUM
        )
        or (
            math.isfinite(float(inputs["odi_spearman_rho"]))
            and abs(float(inputs["odi_spearman_rho"]))
            >= ODI_ABS_SPEARMAN_MINIMUM
        ),
        "control_false_trigger_pass": float(inputs["control_trigger_ratio"])
        <= CONTROL_MAX_TRIGGER_RATIO
        and int(inputs["control_max_consecutive_triggers"])
        <= CONTROL_MAX_CONSECUTIVE_TRIGGERS,
        "no_reference_online": int(inputs["reference_input_count"]) == 0,
    }
    engineering_pass = all(engineering_conditions.values())
    runtime_target_pass = all(runtime_conditions.values())
    scientific_pass = all(scientific_conditions.values())
    # Runtime targets are reported as engineering targets, not a prerequisite
    # for the scientific decision in the user-frozen contract.
    pilot_pass = engineering_pass and scientific_pass
    return {
        "engineering_conditions": engineering_conditions,
        "engineering_gate_pass": engineering_pass,
        "runtime_conditions": runtime_conditions,
        "runtime_gate_target_pass": runtime_target_pass,
        "scientific_conditions": scientific_conditions,
        "scientific_pilot_gate_pass": scientific_pass,
        "MEASUREMENT_REAL_PILOT_PASS": pilot_pass,
        "SECOND_DATASET_EXPANSION_AUTHORIZED": pilot_pass,
    }
