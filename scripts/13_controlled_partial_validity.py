#!/usr/bin/env python3
"""Run Day 20 controlled / partial validity analysis."""

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

from eval.controlled_partial_validity import (  # noqa: E402
    DEFAULT_METRICS,
    DEFAULT_TARGETS,
    INCREMENTAL_FIELDNAMES,
    PARTIAL_FIELDNAMES,
    PERMUTATION_FIELDNAMES,
    REGRESSION_FIELDNAMES,
    build_partial_analyses,
    compute_controlled_regression_summary,
    compute_incremental_validity_summary,
    load_day20_inputs,
    run_within_sequence_permutation_tests,
    to_float,
    write_csv,
    write_day20_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/validation/day20_controlled_partial.yaml")
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day20_report.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    config = load_config(args.config)
    try:
        inputs = load_day20_inputs(args.out_root)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    analyses = build_partial_analyses(inputs["window_metrics"], config)
    partial_rows = [analysis["row"] for analysis in analyses]
    regression_rows = compute_controlled_regression_summary(analyses)
    permutation_rows = run_within_sequence_permutation_tests(
        analyses,
        n_permutations=int(config.get("n_permutations", 200)),
        seed=int(config.get("seed", 20000)),
    )
    incremental_rows = compute_incremental_validity_summary(
        partial_rows,
        permutation_rows,
        metrics=list(config.get("metrics", DEFAULT_METRICS)),
        targets=list(config.get("targets", DEFAULT_TARGETS)),
    )

    table_dir = args.out_root / "tables"
    manifest_dir = args.out_root / "manifests"
    partial_path = table_dir / "day20_partial_correlations.csv"
    regression_path = table_dir / "day20_controlled_regression_summary.csv"
    permutation_path = table_dir / "day20_permutation_tests.csv"
    incremental_path = table_dir / "day20_incremental_validity_summary.csv"
    manifest_path = manifest_dir / "day20_controlled_partial_manifest.json"

    write_csv(partial_path, PARTIAL_FIELDNAMES, partial_rows)
    write_csv(regression_path, REGRESSION_FIELDNAMES, regression_rows)
    write_csv(permutation_path, PERMUTATION_FIELDNAMES, permutation_rows)
    write_csv(incremental_path, INCREMENTAL_FIELDNAMES, incremental_rows)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(partial_rows, permutation_rows, incremental_rows), encoding="utf-8")

    outputs = [partial_path, regression_path, permutation_path, incremental_path, manifest_path, args.report]
    manifest = write_day20_manifest(
        manifest_path,
        config=config,
        inputs=inputs["input_paths"] + [args.config],
        outputs=outputs,
        incremental_rows=incremental_rows,
        runtime_seconds=time.time() - start,
    )

    print(f"day20 partial correlations: {display_path(partial_path)}")
    print(f"day20 regression summary: {display_path(regression_path)}")
    print(f"day20 permutation tests: {display_path(permutation_path)}")
    print(f"day20 incremental summary: {display_path(incremental_path)}")
    print(f"day20 manifest: {display_path(manifest_path)}")
    print(f"day20 report: {display_path(args.report)}")
    print(f"status: {manifest['status']}")
    return 0 if manifest["status"] == "OK" else 1


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Day20 config must be a mapping: {path}")
    config.setdefault("source_validation", "day18_day19")
    config.setdefault("metrics", DEFAULT_METRICS)
    config.setdefault("targets", DEFAULT_TARGETS)
    config.setdefault("controls", [])
    config.setdefault("group_controls", ["sequence_id", "scene_family"])
    config.setdefault("effect_size_threshold", 0.10)
    config.setdefault("n_permutations", 200)
    config.setdefault("seed", 20000)
    config.setdefault("expected_sign", {})
    return config


def build_report(
    partial_rows: Sequence[Dict[str, str]],
    permutation_rows: Sequence[Dict[str, str]],
    incremental_rows: Sequence[Dict[str, str]],
) -> str:
    merged_rows = [row for row in partial_rows if row["scope"] == "merged_controlled"]
    odi_axis = next(
        row
        for row in incremental_rows
        if row["metric_name"] == "ODI_median" and row["target_name"] == "axis_drift_rate"
    )
    odi_partial_axis = next(
        row
        for row in merged_rows
        if row["metric_name"] == "ODI_median" and row["target_name"] == "axis_drift_rate"
    )
    odi_perm_axis = next(
        row
        for row in permutation_rows
        if row["metric_name"] == "ODI_median"
        and row["target_name"] == "axis_drift_rate"
        and row["scope"] == "merged_controlled"
    )
    merged_lines = "\n".join(
        f"| {row['metric_name']} | {row['target_name']} | {row['partial_spearman_rho']} | "
        f"{row['expected_sign_match']} | {row['passes_effect_size']} | {row['substantive_validity_status']} |"
        for row in merged_rows
    )
    incremental_lines = "\n".join(
        f"| {row['metric_name']} | {row['target_name']} | {row['final_day20_status']} | {row['reason']} |"
        for row in incremental_rows
    )
    baselines = [row for row in incremental_rows if row["metric_name"] != "ODI_median"]
    baseline_supported = [row["metric_name"] for row in baselines if row["final_day20_status"] == "candidate_supported"]
    odi_candidate = odi_axis["final_day20_status"] == "candidate_supported"
    return f"""# Day 20 Report - Controlled / Partial Validity Analysis

## Direct Answers

- Day 20 是否完成 controlled / partial validity analysis？Yes. It produced partial correlations, controlled regression summaries, permutation tests, and incremental validity decisions.
- 控制 AIS、lambda_min、condition_number 后，ODI 是否还有增量解释力？{'Yes, but only as a candidate needing Day 21 joint-risk analysis.' if odi_candidate else 'No validated incremental ODI evidence under the Day 20 criteria.'}
- ODI 的 observed sign 是否符合 expected sign？For merged axis drift: `{odi_partial_axis['expected_sign_match']}` with rho `{odi_partial_axis['partial_spearman_rho']}`.
- Day 19 中“可计算 rho 很小”的问题是否被重新筛查？Yes. Day 20 requires `abs(partial rho) >= effect_size_threshold`; computable small effects are not treated as substantive.
- permutation test 是否支持 ODI？For merged axis drift: `{odi_perm_axis['passes_permutation_screen']}` with p-value `{odi_perm_axis['permutation_p_value']}`.
- ODI 是否优于或至少不弱于 AIS / lambda_min_clamped / condition_number？{'Yes in this controlled screen, but it remains a candidate only.' if odi_axis['beats_or_matches_baselines'] == 'true' else 'No. Baseline competition remains a limitation.'}
- Day 20 是否可以证明 ODI 的稳健漂移预测能力？No.
- 是否允许进入 weak-subspace update？No, unless a controlled-validity signal is later integrated and confirmed through joint-risk evidence.
- 是否允许进入 Day 21 joint risk feature analysis？Yes.

## Merged Controlled Partial Correlations

| metric_name | target_name | partial_spearman_rho | expected_sign_match | passes_effect_size | substantive_validity_status |
|---|---|---:|---|---|---|
{merged_lines}

## Incremental Validity Summary

| metric_name | target_name | final_day20_status | reason |
|---|---|---|---|
{incremental_lines}

Supported baseline candidates: `{', '.join(sorted(set(baseline_supported))) if baseline_supported else 'none'}`.

## Conclusion

Day 20 completes controlled / partial validity analysis.
Day 20 does not authorize weak-subspace update unless controlled validity passes.
Day 21 must build joint risk features using ODI + AIS + lambda_min + motion / weak-alignment evidence.
"""


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
