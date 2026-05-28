#!/usr/bin/env python3
"""Run the Day 17 unbiased multi-trial metric probe."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.unbiased_probe import (  # noqa: E402
    CORRELATION_FIELDNAMES,
    SUMMARY_FIELDNAMES,
    TRIAL_FIELDNAMES,
    compute_metric_drift_correlations,
    read_csv_rows,
    run_unbiased_trials,
    summarize_trial_results,
    validate_no_scene_family_bias,
    write_csv,
    write_unbiased_probe_manifest,
)


SEQUENCES = ["OC-L0-S01-M1", "ST-L3-S01-M1", "CT-L2-S01-M2", "RT-L4-S01-M1"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/toy_lio/unbiased_day17.yaml")
    parser.add_argument("--detector-config", type=Path, default=ROOT / "configs/detector/odi_default.yaml")
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/minibench")
    parser.add_argument("--day14-results", type=Path, default=ROOT / "results/day14")
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day17_report.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    config = load_config(args.config)
    inputs = collect_inputs(args)
    missing = [f"{name}: {path}" for name, path in inputs.items() if not path.exists()]
    if missing:
        print("Missing required Day17 input file(s): " + "; ".join(missing), file=sys.stderr)
        return 2

    table_dir = args.out_root / "tables"
    manifest_dir = args.out_root / "manifests"
    raw_dir = args.out_root / "raw/unbiased_day17"
    trials_path = table_dir / "day17_unbiased_probe_trials.csv"
    summary_path = table_dir / "day17_unbiased_probe_summary.csv"
    correlation_path = table_dir / "day17_metric_drift_correlations.csv"
    manifest_path = manifest_dir / "day17_unbiased_probe_manifest.json"

    trial_rows = run_unbiased_trials(config, args.data_root, args.day14_results, args.detector_config, raw_dir)
    summary_rows = summarize_trial_results(trial_rows)
    correlation_rows = compute_metric_drift_correlations(trial_rows)
    write_csv(trials_path, TRIAL_FIELDNAMES, trial_rows)
    write_csv(summary_path, SUMMARY_FIELDNAMES, summary_rows)
    write_csv(correlation_path, CORRELATION_FIELDNAMES, correlation_rows)

    unbiased_passed = validate_no_scene_family_bias(trial_rows)
    expected_rows = int(config.get("n_trials", 1)) * len(SEQUENCES)
    no_scene_family_bias_passed = unbiased_passed and len(trial_rows) == expected_rows
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(config, trial_rows, summary_rows, correlation_rows), encoding="utf-8")
    outputs = [trials_path, summary_path, correlation_path, manifest_path, args.report]
    manifest = write_unbiased_probe_manifest(
        manifest_path,
        config=config,
        inputs=list(inputs.values()),
        outputs=outputs,
        row_count=len(trial_rows),
        unbiased_protocol_passed=unbiased_passed,
        no_scene_family_bias_passed=no_scene_family_bias_passed,
        runtime_seconds=time.time() - start,
    )

    print(f"day17 trials: {display_path(trials_path)}")
    print(f"day17 summary: {display_path(summary_path)}")
    print(f"day17 correlations: {display_path(correlation_path)}")
    print(f"day17 manifest: {display_path(manifest_path)}")
    print(f"day17 report: {display_path(args.report)}")
    print(f"status: {manifest['status']}")
    return 0 if manifest["status"] == "OK" else 1


def load_config(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Day17 config must be a mapping: {path}")
    return config


def collect_inputs(args: argparse.Namespace) -> Dict[str, Path]:
    inputs = {
        "toy_config": args.config,
        "detector_config": args.detector_config,
        "toy_lio": ROOT / "src/minibench/toy_lio.py",
        "day15_bias_audit": args.out_root / "tables/day15_bias_audit.csv",
        "day15_bias_manifest": args.out_root / "manifests/day15_bias_audit_manifest.json",
        "day16_summary": args.out_root / "tables/day16_unbiased_toy_lio_summary.csv",
        "day16_manifest": args.out_root / "manifests/day16_unbiased_toy_lio_manifest.json",
        "day10_metric_validity_per_sequence": args.day14_results / "tables/day10_metric_validity_per_sequence.csv",
        "day10_metric_validity_loso": args.day14_results / "tables/day10_metric_validity_loso.csv",
    }
    for sequence_id in SEQUENCES:
        seq_dir = args.data_root / sequence_id
        inputs[f"{sequence_id}_metadata"] = seq_dir / "scene_metadata.json"
        inputs[f"{sequence_id}_gt"] = seq_dir / "gt.tum"
        inputs[f"{sequence_id}_axis"] = seq_dir / "axis.csv"
        inputs[f"{sequence_id}_observations"] = seq_dir / "observations.npz"
        inputs[f"{sequence_id}_odi"] = args.day14_results / "raw" / f"{sequence_id}_odi.csv"
    return inputs


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def build_report(config, trial_rows, summary_rows, correlation_rows) -> str:
    all_zero = all(row["applied_axis_bias"] == "0" for row in trial_rows)
    per_family = [row for row in correlation_rows if row["scope"] == "per_scene_family"]
    merged = [row for row in correlation_rows if row["scope"] == "merged"]
    summary_lines = "\n".join(
        f"| {row['sequence_id']} | {row['scene_family']} | {row['n_trials']} | "
        f"{row['final_axis_error_median']} | {row['axis_drift_rate_median']} | {row['all_applied_axis_bias_zero']} |"
        for row in summary_rows
    )
    merged_lines = "\n".join(
        f"| {row['metric_name']} | {row['target_name']} | {row['spearman_rho']} | {row['n']} |"
        for row in merged
    )
    undefined_per_family = sum(1 for row in per_family if row["spearman_rho"] == "nan")
    return f"""# Day 17 Report - Unbiased Multi-Trial Metric Probe

## Direct Answers

- Day 17 是否真正运行了 multi-trial unbiased probe？Yes. It ran `{config.get('n_trials')}` trials for each of OC/ST/CT/RT.
- 所有 applied_axis_bias 是否为 0？{'Yes' if all_zero else 'No'}.
- 去掉 scene-family axis_bias 后，ODI / AIS / lambda_min_clamped / condition_number 哪些指标仍然和 drift 有相关趋势？See `results/day30/tables/day17_metric_drift_correlations.csv`; these are exploratory correlations only.
- merged correlation 是否仍可能误导？Yes. Even without axis_bias, merged correlation can still reflect scene-family grouping and static geometry differences.
- per-scene-family correlation 是否稳定？No conclusion yet. Many per-scene-family correlations are undefined because spectral metrics are constant within a single scene family across trials.
- Day 17 是否可以证明 ODI 有效？No. Day 17 does not yet validate ODI.
- 是否允许进入 Day 18 的 within-sequence validation？Yes, but only for stricter validation; no method update is allowed.

## Trial Summary

| sequence_id | scene_family | n_trials | final_axis_error_median | axis_drift_rate_median | all_applied_axis_bias_zero |
|---|---|---:|---:|---:|---|
{summary_lines}

## Merged Exploratory Correlations

| metric_name | target_name | spearman_rho | n |
|---|---|---:|---:|
{merged_lines}

Per-scene-family correlation rows with undefined rho: `{undefined_per_family}`.

## Conclusion

Day 17 runs an unbiased multi-trial toy probe and provides exploratory metric-drift evidence.
It does not yet validate ODI.
Day 18 must perform stricter within-sequence validation before any method update is implemented.
"""


if __name__ == "__main__":
    raise SystemExit(main())
