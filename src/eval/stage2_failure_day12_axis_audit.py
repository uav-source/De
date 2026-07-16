"""Matplotlib-axis contract audit for Stage 2 Day 12 v3 figures."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib.pyplot as plt

from eval.stage2_failure_day12_figures import (
    FIGURE4_METRICS,
    FIGURE_NAMES,
    METHODS,
    SWEEPS,
    build_figure,
    nonnegative_integer_limits,
)
from eval.stage2_failure_day12_schema import padded_limits, write_csv
from eval.synthetic_pipeline_common import write_json


AXIS_AUDIT_FIELDS = (
    "figure_id", "panel_id", "metric_name", "actual_finite_min",
    "actual_finite_max", "ylim_lower", "ylim_upper", "expected_lower",
    "expected_upper", "lower_match", "upper_match", "data_not_clipped", "pass",
)


def audit_axis_contracts(
    figure_data: Mapping[str, Sequence[Mapping[str, Any]]],
) -> Mapping[str, Any]:
    """Rebuild Figure 3/4 and inspect their live Matplotlib y-axis contracts."""

    records = []
    figure3_id = FIGURE_NAMES[2]
    figure3_rows = figure_data[figure3_id]
    figure3_values = _finite_values(
        row["huber_current_same_sign_run_length"] for row in figure3_rows
    )
    figure3_expected = nonnegative_integer_limits(figure3_values)
    figure3 = build_figure(figure3_id, figure3_rows)
    try:
        for axis, (sweep, method) in zip(
            figure3.axes,
            ((sweep, method) for sweep in SWEEPS for method in METHODS),
        ):
            panel_values = _finite_values(
                row["huber_current_same_sign_run_length"]
                for row in figure3_rows
                if row["sweep"] == sweep and row["method"] == method
            )
            records.append(_record(
                figure3_id, f"{sweep}/{method}",
                "huber_current_same_sign_run_length", panel_values,
                axis.get_ylim(), figure3_expected,
            ))
    finally:
        plt.close(figure3)

    figure4_id = FIGURE_NAMES[3]
    figure4_rows = figure_data[figure4_id]
    figure4 = build_figure(figure4_id, figure4_rows)
    try:
        for metric_index, (metric, _) in enumerate(FIGURE4_METRICS):
            global_values = _finite_values(
                row["metric_value"] for row in figure4_rows
                if row["metric_name"] == metric and _as_bool(row["included"])
            )
            expected = (
                nonnegative_integer_limits(global_values)
                if metric == "huber_current_same_sign_run_length"
                else padded_limits(global_values)
            )
            for column, sweep in enumerate(SWEEPS):
                axis = figure4.axes[metric_index * len(SWEEPS) + column]
                panel_values = _finite_values(
                    row["metric_value"] for row in figure4_rows
                    if row["metric_name"] == metric and row["sweep"] == sweep
                    and _as_bool(row["included"])
                )
                records.append(_record(
                    figure4_id, f"{metric}/{sweep}", metric,
                    panel_values, axis.get_ylim(), expected,
                ))
    finally:
        plt.close(figure4)

    failures = sum(int(not row["pass"]) for row in records)
    run_row = [
        row for row in records
        if row["figure_id"] == figure4_id
        and row["metric_name"] == "huber_current_same_sign_run_length"
    ]
    return {
        "schema_version": "stage2_failure_day12_axis_contract_v3",
        "records": records,
        "axis_contract_comparison_count": len(records),
        "axis_contract_failure_count": failures,
        "figure3_ylim_lower": float(figure3_expected[0]),
        "figure3_ylim_upper": float(figure3_expected[1]),
        "figure3_actual_run_max": max(figure3_values) if figure3_values else float("nan"),
        "figure4_run_row_ylim_lower": float(run_row[0]["expected_lower"]),
        "figure4_run_row_ylim_upper": float(run_row[0]["expected_upper"]),
        "figure4_run_row_actual_max": max(
            float(row["actual_finite_max"]) for row in run_row
        ),
        "audit_pass": failures == 0,
    }


def write_axis_contract_audit(output_dir: Path, audit: Mapping[str, Any]) -> None:
    output_dir = Path(output_dir)
    write_csv(output_dir / "axis_contract_audit.csv", audit["records"], AXIS_AUDIT_FIELDS)
    write_json(output_dir / "axis_contract_audit.json", audit)


def _record(
    figure_id: str,
    panel_id: str,
    metric_name: str,
    values: Sequence[float],
    actual_limits: Sequence[float],
    expected_limits: Sequence[float],
) -> Mapping[str, Any]:
    actual_min = min(values) if values else float("nan")
    actual_max = max(values) if values else float("nan")
    lower, upper = (float(actual_limits[0]), float(actual_limits[1]))
    expected_lower, expected_upper = (
        float(expected_limits[0]), float(expected_limits[1])
    )
    lower_match = math.isclose(lower, expected_lower, rel_tol=0.0, abs_tol=1.0e-12)
    upper_match = math.isclose(upper, expected_upper, rel_tol=0.0, abs_tol=1.0e-12)
    data_not_clipped = (
        not values or (lower <= actual_min + 1.0e-12 and upper >= actual_max - 1.0e-12)
    )
    passed = lower_match and upper_match and data_not_clipped
    return {
        "figure_id": figure_id,
        "panel_id": panel_id,
        "metric_name": metric_name,
        "actual_finite_min": actual_min,
        "actual_finite_max": actual_max,
        "ylim_lower": lower,
        "ylim_upper": upper,
        "expected_lower": expected_lower,
        "expected_upper": expected_upper,
        "lower_match": lower_match,
        "upper_match": upper_match,
        "data_not_clipped": data_not_clipped,
        "pass": passed,
    }


def _finite_values(values: Sequence[Any]) -> list[float]:
    return [float(value) for value in values if math.isfinite(float(value))]


def _as_bool(value: Any) -> bool:
    return value is True or str(value) == "True"
