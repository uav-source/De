"""Descriptive statistics for Day 6 Fallback detector diagnostics."""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .day6_continuity_metrics import sign_invariant_angle_deg
from .day6_fallback_functional_diagnostics import FLAG_FIELDS, METRIC_FIELDS


PERCENTILES = (1, 5, 25, 50, 75, 95, 99)
PAIRWISE_PERCENTILES = (0, 50, 90, 95, 99, 100)


def finite_values(values: Iterable[Any]) -> list[float]:
    result = []
    for value in values:
        if value is None:
            continue
        numeric = float(value)
        if math.isfinite(numeric):
            result.append(numeric)
    return result


def describe(values: Iterable[Any]) -> dict[str, Any]:
    finite = finite_values(values)
    if not finite:
        return {
            "count": 0,
            "min": None,
            "p01": None,
            "p05": None,
            "p25": None,
            "median": None,
            "p75": None,
            "p95": None,
            "p99": None,
            "max": None,
            "mean": None,
            "std": None,
        }
    array = np.asarray(finite, dtype=np.float64)
    return {
        "count": len(finite),
        "min": float(np.min(array)),
        "p01": float(np.percentile(array, 1)),
        "p05": float(np.percentile(array, 5)),
        "p25": float(np.percentile(array, 25)),
        "median": float(np.percentile(array, 50)),
        "p75": float(np.percentile(array, 75)),
        "p95": float(np.percentile(array, 95)),
        "p99": float(np.percentile(array, 99)),
        "max": float(np.max(array)),
        "mean": float(np.mean(array)),
        "std": float(np.std(array)),
    }


def detector_metric_statistics(
    outputs: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    series: dict[str, list[Any]] = {
        field: [row.get(field) for row in outputs] for field in METRIC_FIELDS
    }
    for index, name in enumerate(("lambda_1", "lambda_2", "lambda_3")):
        series[name] = [
            (
                row["translation_eigenvalues_ascending"][index]
                if row.get("translation_eigenvalues_ascending") is not None
                else None
            )
            for row in outputs
        ]
    series["log10_condition_number"] = [
        (
            math.log10(float(row["condition_number_trans"]))
            if row.get("condition_number_trans") is not None
            and float(row["condition_number_trans"]) > 0.0
            else None
        )
        for row in outputs
    ]
    rows: list[dict[str, Any]] = []
    statistics: dict[str, Any] = {}
    for metric, values in series.items():
        summary = describe(values)
        statistics[metric] = summary
        rows.append(
            {
                "metric": metric,
                "total_record_count": len(outputs),
                "invalid_record_count": sum(
                    row.get("valid") is not True for row in outputs
                ),
                **summary,
            }
        )
    result = {
        "schema_version": "day6_detector_metric_statistics_v1",
        "total_record_count": len(outputs),
        "invalid_record_count": sum(
            row.get("valid") is not True for row in outputs
        ),
        "statistics": statistics,
        "threshold_tuning_performed": False,
        "scientific_accuracy_interpretation": False,
        "metric_descriptive_statistics_pass": len(outputs) > 0,
    }
    return rows, result


def latency_statistics(
    latency_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    def one(values: Sequence[int]) -> dict[str, Any]:
        if not values:
            return {
                "count": 0,
                "min": None,
                "median": None,
                "p90": None,
                "p95": None,
                "p99": None,
                "max": None,
                "mean": None,
                "std": None,
            }
        array = np.asarray(values, dtype=np.float64)
        return {
            "count": len(values),
            "min": int(np.min(array)),
            "median": float(np.percentile(array, 50)),
            "p90": float(np.percentile(array, 90)),
            "p95": float(np.percentile(array, 95)),
            "p99": float(np.percentile(array, 99)),
            "max": int(np.max(array)),
            "mean": float(np.mean(array)),
            "std": float(np.std(array)),
        }

    result: dict[str, Any] = {
        "schema_version": "day6_detector_latency_summary_v1",
        "LATENCY_INTERPRETATION": (
            "POST_REPLAY_OFFLINE_LOCKED_ENVIRONMENT_ONLY"
        ),
        "online_end_to_end_latency_evaluated": False,
        "real_time_threshold_applied": False,
    }
    for field in (
        "adapter_total_call_latency_ns",
        "direct_production_call_latency_ns",
    ):
        all_values = [int(row[field]) for row in latency_rows]
        result[field] = {
            "all_records": one(all_values),
            "excluding_first_10_records": one(all_values[10:]),
        }
    result["latency_characterization_pass"] = (
        len(latency_rows) > 10
        and all(
            int(row["adapter_total_call_latency_ns"]) >= 0
            and int(row["direct_production_call_latency_ns"]) >= 0
            for row in latency_rows
        )
    )
    return result


def quantile_summary(values: Iterable[Any]) -> dict[str, Any]:
    finite = finite_values(values)
    if not finite:
        return {"count": 0}
    array = np.asarray(finite, dtype=np.float64)
    result: dict[str, Any] = {"count": len(finite)}
    names = ("min", "median", "p90", "p95", "p99", "max")
    for name, percentile in zip(names, PAIRWISE_PERCENTILES):
        result[name] = float(np.percentile(array, percentile))
    return result


def relative_difference(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    lvalue = float(left)
    rvalue = float(right)
    denominator = max(abs(lvalue), abs(rvalue), np.finfo(np.float64).tiny)
    return abs(lvalue - rvalue) / denominator


def aligned_output_differences(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> dict[str, Any]:
    result = {
        "valid_agreement": bool(left["valid"]) == bool(right["valid"]),
        "degeneracy_flag_agreement": bool(left["degeneracy_triggered"])
        == bool(right["degeneracy_triggered"]),
        "stable_flag_agreement": bool(left["primary_direction_stable"])
        == bool(right["primary_direction_stable"]),
        "actionable_flag_agreement": bool(left["actionable_direction"])
        == bool(right["actionable_direction"]),
    }
    for field in (
        "odi_trans",
        "ais_trans",
        "lambda_min_trans",
        "primary_eigengap_ratio",
    ):
        lvalue = left.get(field)
        rvalue = right.get(field)
        result[f"{field}_absolute_difference"] = (
            abs(float(lvalue) - float(rvalue))
            if lvalue is not None and rvalue is not None
            else None
        )
    result["condition_number_relative_difference"] = relative_difference(
        left.get("condition_number_trans"),
        right.get("condition_number_trans"),
    )
    ldir = left.get("primary_weak_direction")
    rdir = right.get("primary_weak_direction")
    result["weak_direction_sign_invariant_angle_deg"] = (
        sign_invariant_angle_deg(ldir, rdir)
        if ldir is not None and rdir is not None
        else None
    )
    return result


def summarize_aligned_differences(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    metric_fields = (
        "odi_trans_absolute_difference",
        "ais_trans_absolute_difference",
        "lambda_min_trans_absolute_difference",
        "condition_number_relative_difference",
        "primary_eigengap_ratio_absolute_difference",
        "weak_direction_sign_invariant_angle_deg",
    )
    return {
        "aligned_record_count": len(rows),
        "valid_agreement_fraction": (
            sum(bool(row["valid_agreement"]) for row in rows) / len(rows)
            if rows
            else None
        ),
        "flag_agreement": {
            field: (
                sum(bool(row[field]) for row in rows) / len(rows)
                if rows
                else None
            )
            for field in (
                "degeneracy_flag_agreement",
                "stable_flag_agreement",
                "actionable_flag_agreement",
            )
        },
        "difference_quantiles": {
            field: quantile_summary(row.get(field) for row in rows)
            for field in metric_fields
        },
    }


def run_level_summary(
    run_id: str, outputs: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "run_id": run_id,
        "record_count": len(outputs),
    }
    for field in FLAG_FIELDS:
        row[f"{field}_true_fraction"] = (
            sum(bool(item[field]) for item in outputs) / len(outputs)
            if outputs
            else None
        )
    for field in METRIC_FIELDS:
        row[f"{field}_median"] = describe(
            item.get(field) for item in outputs
        )["median"]
    return row
