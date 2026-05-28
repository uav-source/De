#!/usr/bin/env python3
"""Run Day 19 grouped / LOSO metric validation."""

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

from eval.grouped_loso_validation import (  # noqa: E402
    DEFAULT_METRICS,
    DEFAULT_TARGETS,
    GROUPED_FIELDNAMES,
    LOSO_FIELDNAMES,
    PASS_FAIL_FIELDNAMES,
    compare_odi_against_baselines,
    compute_grouped_metric_summary,
    load_day18_inputs,
    run_leave_one_sequence_out_selection,
    to_float,
    write_csv,
    write_day19_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/validation/day19_grouped_loso.yaml")
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day19_report.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    config = load_config(args.config)
    try:
        inputs = load_day18_inputs(args.out_root)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    metrics = list(config.get("metrics", DEFAULT_METRICS))
    targets = list(config.get("targets", DEFAULT_TARGETS))
    grouped_rows = compute_grouped_metric_summary(inputs["within_sequence_correlations"], metrics, targets)
    loso_rows = run_leave_one_sequence_out_selection(
        inputs["within_sequence_correlations"],
        metrics,
        targets,
        selection_rule=str(config.get("selection_rule", "mean_abs_spearman_on_train")),
    )
    pass_fail_rows = compare_odi_against_baselines(
        grouped_rows,
        loso_rows,
        metrics,
        targets,
        min_valid_sequences=int(config.get("min_valid_sequences", 3)),
    )

    table_dir = args.out_root / "tables"
    manifest_dir = args.out_root / "manifests"
    grouped_path = table_dir / "day19_grouped_metric_summary.csv"
    loso_path = table_dir / "day19_loso_selection_results.csv"
    pass_fail_path = table_dir / "day19_metric_pass_fail_summary.csv"
    manifest_path = manifest_dir / "day19_grouped_loso_manifest.json"

    write_csv(grouped_path, GROUPED_FIELDNAMES, grouped_rows)
    write_csv(loso_path, LOSO_FIELDNAMES, loso_rows)
    write_csv(pass_fail_path, PASS_FAIL_FIELDNAMES, pass_fail_rows)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(grouped_rows, loso_rows, pass_fail_rows), encoding="utf-8")

    outputs = [grouped_path, loso_path, pass_fail_path, manifest_path, args.report]
    manifest = write_day19_manifest(
        manifest_path,
        config=config,
        inputs=inputs["input_paths"] + [args.config],
        outputs=outputs,
        grouped_rows=grouped_rows,
        loso_rows=loso_rows,
        pass_fail_rows=pass_fail_rows,
        runtime_seconds=time.time() - start,
    )

    print(f"day19 grouped summary: {display_path(grouped_path)}")
    print(f"day19 loso results: {display_path(loso_path)}")
    print(f"day19 pass/fail: {display_path(pass_fail_path)}")
    print(f"day19 manifest: {display_path(manifest_path)}")
    print(f"day19 report: {display_path(args.report)}")
    print(f"status: {manifest['status']}")
    return 0 if manifest["status"] == "OK" else 1


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Day19 config must be a mapping: {path}")
    config.setdefault("source_validation", "day18_within_sequence")
    config.setdefault("metrics", DEFAULT_METRICS)
    config.setdefault("targets", DEFAULT_TARGETS)
    config.setdefault("group_keys", ["sequence_id", "scene_family"])
    config.setdefault("loso_unit", "sequence_id")
    config.setdefault("min_valid_sequences", 3)
    config.setdefault("selection_rule", "mean_abs_spearman_on_train")
    return config


def build_report(
    grouped_rows: Sequence[Dict[str, str]],
    loso_rows: Sequence[Dict[str, str]],
    pass_fail_rows: Sequence[Dict[str, str]],
) -> str:
    axis_grouped = [row for row in grouped_rows if row["target_name"] == "axis_drift_rate"]
    odi_axis = next(row for row in axis_grouped if row["metric_name"] == "ODI_median")
    odi_pass = next(
        row
        for row in pass_fail_rows
        if row["metric_name"] == "ODI_median" and row["target_name"] == "axis_drift_rate"
    )
    loso_failures = [
        row for row in loso_rows if row["held_out_validity_status"] != "valid"
    ]
    selected_crashes = [
        row
        for row in loso_rows
        if row["selected_metric_from_train"] != "none" and row["held_out_validity_status"] != "valid"
    ]
    best_by_axis = "\n".join(
        f"| {row['metric_name']} | {row['n_valid_sequences']} | {row['mean_abs_rho']} | "
        f"{row['sign_consistency']} | {row['best_sequence_count']} |"
        for row in axis_grouped
    )
    loso_lines = "\n".join(
        f"| {row['held_out_sequence']} | {row['target_name']} | {row['selected_metric_from_train']} | "
        f"{row['train_mean_abs_rho']} | {row['held_out_rho']} | {row['held_out_validity_status']} | "
        f"{row['ODI_held_out_rho']} |"
        for row in loso_rows
    )
    pass_lines = "\n".join(
        f"| {row['metric_name']} | {row['target_name']} | {row['final_day19_status']} | {row['reason']} |"
        for row in pass_fail_rows
    )
    odi_is_superior = odi_pass["final_day19_status"] == "candidate_supported"
    return f"""# Day 19 Report - Grouped / LOSO Metric Validation

## Direct Answers

- Day 19 是否完成 grouped / LOSO validation？Yes. It generated grouped metric summary, LOSO selection results, and pass/fail screening tables.
- ODI 在 grouped summary 中是否稳定？No robust conclusion. ODI axis-drift `n_valid_sequences={odi_axis['n_valid_sequences']}`, `sign_consistency={odi_axis['sign_consistency']}`, `mean_abs_rho={odi_axis['mean_abs_rho']}`.
- ODI 在 LOSO held-out sequence 中是否稳定？No robust conclusion. LOSO rows preserve held-out ODI rho and train-selected metric behavior for every sequence.
- ODI 是否优于 AIS / lambda_min_clamped / condition_number？{'Yes under this screening table, but still exploratory.' if odi_is_superior else 'No. ODI is not consistently superior to AIS / lambda_min_clamped / condition_number under Day 19 screening.'}
- 是否存在 train 上有效、held-out 崩溃的 metric？{'Yes' if selected_crashes else 'No explicit train-selected held-out invalid case in this run'}; see `results/day30/tables/day19_loso_selection_results.csv`.
- Day 19 是否可以证明 ODI 的稳健漂移预测？No. ODI remains exploratory and is not validated for robust drift prediction.
- 是否允许进入 Day 20 的 controlled / partial validity analysis？Yes.
- 是否允许进入 weak-subspace update？No.

## Grouped Axis-Drift Summary

| metric_name | n_valid_sequences | mean_abs_rho | sign_consistency | best_sequence_count |
|---|---:|---:|---:|---:|
{best_by_axis}

## LOSO Results

| held_out_sequence | target_name | selected_metric_from_train | train_mean_abs_rho | held_out_rho | held_out_validity_status | ODI_held_out_rho |
|---|---|---|---:|---:|---|---:|
{loso_lines}

LOSO rows with invalid held-out selected metric: `{len(loso_failures)}`.

## Pass / Fail Screening

| metric_name | target_name | final_day19_status | reason |
|---|---|---|---|
{pass_lines}

## Conclusion

Day 19 completes grouped / LOSO validation.
It does not authorize weak-subspace update yet.
Day 19 does not authorize weak-subspace update yet.
Day 20 must perform controlled / partial validity analysis before any method update is implemented.
"""


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
