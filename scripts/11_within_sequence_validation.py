#!/usr/bin/env python3
"""Run Day 18 window-level within-sequence validation."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.within_sequence_validation import (  # noqa: E402
    CORRELATION_FIELDNAMES,
    SUMMARY_FIELDNAMES,
    WINDOW_FIELDNAMES,
    all_rows_unbiased,
    build_window_level_table,
    compute_sequence_aggregate_validity,
    compute_within_sequence_correlations,
    load_day17_probe_inputs,
    read_csv_rows,
    to_float,
    write_csv,
    write_day18_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/validation/day18_within_sequence.yaml")
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/minibench")
    parser.add_argument("--day14-results", type=Path, default=ROOT / "results/day14")
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day18_report.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    config = load_config(args.config)
    try:
        inputs = load_day17_probe_inputs(config, args.data_root, args.day14_results, args.out_root)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    table_dir = args.out_root / "tables"
    manifest_dir = args.out_root / "manifests"
    window_path = table_dir / "day18_window_metrics.csv"
    correlation_path = table_dir / "day18_within_sequence_correlations.csv"
    summary_path = table_dir / "day18_sequence_validity_summary.csv"
    manifest_path = manifest_dir / "day18_within_sequence_manifest.json"

    window_rows = build_window_level_table(
        inputs,
        window_size=int(config.get("window_size", 20)),
        stride=int(config.get("stride", 5)),
    )
    correlation_rows = compute_within_sequence_correlations(
        window_rows,
        metrics=list(config.get("metrics", [])),
        targets=list(config.get("targets", [])),
        min_windows_per_sequence=int(config.get("min_windows_per_sequence", 3)),
    )
    summary_rows = compute_sequence_aggregate_validity(window_rows, correlation_rows)

    write_csv(window_path, WINDOW_FIELDNAMES, window_rows)
    write_csv(correlation_path, CORRELATION_FIELDNAMES, correlation_rows)
    write_csv(summary_path, SUMMARY_FIELDNAMES, summary_rows)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(config, window_rows, correlation_rows, summary_rows), encoding="utf-8")

    outputs = [window_path, correlation_path, summary_path, manifest_path, args.report]
    manifest = write_day18_manifest(
        manifest_path,
        config=config,
        inputs=inputs["inputs"] + [args.config],
        outputs=outputs,
        row_count=len(window_rows),
        sequence_count=len({row["sequence_id"] for row in window_rows}),
        all_unbiased_protocol=all_rows_unbiased(window_rows),
        runtime_seconds=time.time() - start,
    )

    print(f"day18 windows: {display_path(window_path)}")
    print(f"day18 correlations: {display_path(correlation_path)}")
    print(f"day18 summary: {display_path(summary_path)}")
    print(f"day18 manifest: {display_path(manifest_path)}")
    print(f"day18 report: {display_path(args.report)}")
    print(f"status: {manifest['status']}")
    return 0 if manifest["status"] == "OK" else 1


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Day18 config must be a mapping: {path}")
    config.setdefault("source_probe", "day17_unbiased")
    config.setdefault("window_size", 20)
    config.setdefault("stride", 5)
    config.setdefault("min_windows_per_sequence", 3)
    config.setdefault("metrics", ["ODI", "AIS", "lambda_min_clamped", "condition_number"])
    config.setdefault("targets", ["axis_drift_rate", "weak_drift_alignment"])
    return config


def build_report(
    config: Dict[str, Any],
    window_rows: Sequence[Dict[str, str]],
    correlation_rows: Sequence[Dict[str, str]],
    summary_rows: Sequence[Dict[str, str]],
) -> str:
    undefined_constant = sum(row["validity_status"] == "undefined_constant_metric" for row in correlation_rows)
    valid_count = sum(row["validity_status"] == "valid" for row in correlation_rows)
    all_unbiased = all_rows_unbiased(window_rows)
    best_lines = "\n".join(
        f"| {row['sequence_id']} | {row['scene_family']} | {row['n_trials']} | {row['n_windows']} | "
        f"{row['best_metric_for_axis_drift']} | {row['best_abs_rho_for_axis_drift']} | "
        f"{row['ODI_axis_drift_rho']} | {row['AIS_axis_drift_rho']} | "
        f"{row['lambda_min_clamped_axis_drift_rho']} | {row['condition_number_axis_drift_rho']} |"
        for row in summary_rows
    )
    constant_lines = "\n".join(
        f"| {row['sequence_id']} | {row['metric_name']} | {row['target_name']} | {row['validity_status']} |"
        for row in correlation_rows
        if row["validity_status"] != "valid"
    )
    if not constant_lines:
        constant_lines = "| none | none | none | none |"
    odi_best_count = sum(row["best_metric_for_axis_drift"] == "ODI_median" for row in summary_rows)
    stronger_competitors = [
        row["sequence_id"]
        for row in summary_rows
        if row["best_metric_for_axis_drift"] not in {"ODI_median", "none"}
    ]
    metric_answer = (
        "ODI is not consistently superior to AIS / lambda_min_clamped / condition_number."
        if stronger_competitors or odi_best_count < len(summary_rows)
        else "ODI is strongest in this run, but this is still within-sequence exploratory evidence only."
    )
    return f"""# Day 18 Report - Within-Sequence Window Validation

## Direct Answers

- Day 18 是否真正做了 window-level within-sequence validation？Yes. It produced `{len(window_rows)}` window rows from Day 17 unbiased trial trajectories.
- Day 17 的 sequence-level per-family undefined 问题是否被修正？Partially. Day 18 evaluates windows inside each sequence, but metrics that remain constant within a sequence are still marked as undefined instead of forced into a correlation.
- 在每条序列内部，ODI / AIS / lambda_min_clamped / condition_number 哪些指标对 axis_drift_rate 有解释趋势？See `results/day30/tables/day18_sequence_validity_summary.csv`; the best metric is reported per sequence rather than merged.
- 是否存在 metric constant 导致无法验证的情况？Yes. `undefined_constant_metric` rows: `{undefined_constant}`.
- ODI 是否优于 AIS / lambda_min_clamped？{metric_answer}
- Day 18 是否可以证明 ODI 有效？No. Day 18 does not yet prove ODI robustness.
- 是否允许进入 Day 19 的 LOSO / grouped validation？Yes, but only for grouped / LOSO validation; no weak-subspace update is allowed.
- Day 17 unbiased protocol 是否保持？{'Yes' if all_unbiased else 'No'}; all window rows must have `applied_axis_bias=0` and `is_unbiased_protocol=true`.

## Sequence Summary

| sequence_id | scene_family | n_trials | n_windows | best_metric_for_axis_drift | best_abs_rho | ODI rho | AIS rho | lambda_min_clamped rho | condition_number rho |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|
{best_lines}

## Undefined / Limited Correlations

| sequence_id | metric_name | target_name | validity_status |
|---|---|---|---|
{constant_lines}

Valid within-sequence correlations: `{valid_count}`.

## Conclusion

Day 18 performs window-level within-sequence validation.
It does not yet prove ODI robustness.
Day 19 must perform grouped / LOSO validation before any weak-subspace update is implemented.
"""


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
