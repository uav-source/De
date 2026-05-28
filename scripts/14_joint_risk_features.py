#!/usr/bin/env python3
"""Run Day 21 interpretable joint-risk feature analysis."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, Sequence

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.joint_risk_features import (  # noqa: E402
    BASE_RISK_COMPONENTS,
    COMPARISON_FIELDNAMES,
    CONTROLLED_FIELDNAMES,
    CORRELATION_FIELDNAMES,
    DEFAULT_JOINT_FEATURES,
    DEFAULT_TARGETS,
    FEATURE_FIELDNAMES,
    compare_joint_risk_with_single_metrics,
    compute_joint_risk_controlled_validity,
    compute_joint_risk_correlations,
    compute_joint_risk_features,
    load_day21_inputs,
    to_float,
    write_csv,
    write_day21_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/validation/day21_joint_risk.yaml")
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day21_report.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    config = load_config(args.config)
    try:
        inputs = load_day21_inputs(args.out_root)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    targets = list(config.get("targets", DEFAULT_TARGETS))
    joint_features = list(config.get("risk_features", DEFAULT_JOINT_FEATURES))
    all_feature_names = BASE_RISK_COMPONENTS + joint_features
    feature_rows = compute_joint_risk_features(inputs["window_metrics"])
    correlation_rows = compute_joint_risk_correlations(
        feature_rows,
        all_feature_names,
        targets,
        expected_sign=dict(config.get("expected_sign", {})),
        effect_size_threshold=float(config.get("effect_size_threshold", 0.10)),
    )
    controlled_rows = compute_joint_risk_controlled_validity(
        feature_rows,
        joint_features,
        targets,
        expected_sign=dict(config.get("expected_sign", {})),
        effect_size_threshold=float(config.get("effect_size_threshold", 0.10)),
        n_permutations=int(config.get("n_permutations", 200)),
        seed=int(config.get("seed", 21000)),
    )
    comparison_rows = compare_joint_risk_with_single_metrics(
        correlation_rows,
        controlled_rows,
        joint_features,
        targets,
        effect_size_threshold=float(config.get("effect_size_threshold", 0.10)),
    )

    table_dir = args.out_root / "tables"
    manifest_dir = args.out_root / "manifests"
    feature_path = table_dir / "day21_joint_risk_window_features.csv"
    correlation_path = table_dir / "day21_joint_risk_correlations.csv"
    controlled_path = table_dir / "day21_joint_risk_controlled_validity.csv"
    comparison_path = table_dir / "day21_joint_risk_comparison.csv"
    manifest_path = manifest_dir / "day21_joint_risk_manifest.json"

    write_csv(feature_path, FEATURE_FIELDNAMES, feature_rows)
    write_csv(correlation_path, CORRELATION_FIELDNAMES, correlation_rows)
    write_csv(controlled_path, CONTROLLED_FIELDNAMES, controlled_rows)
    write_csv(comparison_path, COMPARISON_FIELDNAMES, comparison_rows)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(correlation_rows, controlled_rows, comparison_rows), encoding="utf-8")

    outputs = [feature_path, correlation_path, controlled_path, comparison_path, manifest_path, args.report]
    manifest = write_day21_manifest(
        manifest_path,
        config=config,
        inputs=inputs["input_paths"] + [args.config],
        outputs=outputs,
        comparison_rows=comparison_rows,
        runtime_seconds=time.time() - start,
    )

    print(f"day21 feature table: {display_path(feature_path)}")
    print(f"day21 correlations: {display_path(correlation_path)}")
    print(f"day21 controlled validity: {display_path(controlled_path)}")
    print(f"day21 comparison: {display_path(comparison_path)}")
    print(f"day21 manifest: {display_path(manifest_path)}")
    print(f"day21 report: {display_path(args.report)}")
    print(f"status: {manifest['status']}")
    return 0 if manifest["status"] == "OK" else 1


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Day21 config must be a mapping: {path}")
    config.setdefault("source_validation", "day18_day20")
    config.setdefault("targets", DEFAULT_TARGETS)
    config.setdefault("risk_features", DEFAULT_JOINT_FEATURES)
    config.setdefault("normalization", "rank_percentile")
    config.setdefault("effect_size_threshold", 0.10)
    config.setdefault("n_permutations", 200)
    config.setdefault("seed", 21000)
    config.setdefault("expected_sign", {})
    return config


def build_report(
    correlation_rows: Sequence[Dict[str, str]],
    controlled_rows: Sequence[Dict[str, str]],
    comparison_rows: Sequence[Dict[str, str]],
) -> str:
    best = best_row(comparison_rows)
    no_odi = [row for row in comparison_rows if row["feature_name"] == "joint_risk_no_odi"]
    odi_features = [row for row in comparison_rows if row["feature_name"] != "joint_risk_no_odi"]
    no_odi_best = max([to_float(row["merged_abs_rho"]) for row in no_odi], default=float("nan"))
    with_odi_best = max([to_float(row["merged_abs_rho"]) for row in odi_features], default=float("nan"))
    controlled_candidates = [row for row in controlled_rows if row["controlled_validity_status"] == "controlled_candidate"]
    supported = [row for row in comparison_rows if row["final_day21_status"] == "candidate_supported"]
    comparison_lines = "\n".join(
        f"| {row['feature_name']} | {row['target_name']} | {row['merged_abs_rho']} | "
        f"{row['mean_within_sequence_abs_rho']} | {row['controlled_abs_partial_rho']} | "
        f"{row['beats_single_metrics']} | {row['beats_no_odi_baseline']} | {row['final_day21_status']} |"
        for row in comparison_rows
    )
    controlled_lines = "\n".join(
        f"| {row['feature_name']} | {row['target_name']} | {row['partial_spearman_rho']} | "
        f"{row['permutation_p_value']} | {row['controlled_validity_status']} |"
        for row in controlled_rows
    )
    return f"""# Day 21 Report - Joint Risk Feature Analysis

## Direct Answers

- Day 21 是否完成 joint risk feature construction？Yes. It built fixed, interpretable with-ODI and no-ODI joint risk features from Day 18 windows.
- 哪个 joint risk feature 最强？`{best.get('feature_name', 'none')}` for `{best.get('target_name', 'none')}` by controlled/merged comparison.
- joint risk 是否优于单一指标？See `results/day30/tables/day21_joint_risk_comparison.csv`; this is decided per feature and target, not globally.
- 加入 ODI 是否优于 no-ODI joint risk？with-ODI best merged abs rho `{with_odi_best:.6g}` vs no-ODI best `{no_odi_best:.6g}`.
- joint risk 是否通过 controlled / permutation screen？Controlled candidates: `{len(controlled_candidates)}`; final supported joint-risk rows: `{len(supported)}`.
- Day 21 是否可以证明 ODI 的稳健性？No. Day 21 does not prove ODI robustness.
- Day 21 是否授权 weak-subspace update？No.
- 是否允许进入 Day 22 gate review？Yes. Day 22 must review whether any joint risk evidence is strong enough for a later method gate.

## Controlled Joint Risk Screen

| feature_name | target_name | partial_spearman_rho | permutation_p_value | controlled_validity_status |
|---|---|---:|---:|---|
{controlled_lines}

## Joint Risk Comparison

| feature_name | target_name | merged_abs_rho | mean_within_sequence_abs_rho | controlled_abs_partial_rho | beats_single_metrics | beats_no_odi_baseline | final_day21_status |
|---|---|---:|---:|---:|---|---|---|
{comparison_lines}

## Conclusion

Day 21 builds and screens interpretable joint risk features.
Day 21 does not prove ODI robustness.
Weak-subspace update is not authorized unless a joint risk feature passes strict controlled validity.
Day 22 must perform a go/no-go gate review before any method update is implemented.
"""


def best_row(rows: Sequence[Dict[str, str]]) -> Dict[str, str]:
    finite = [row for row in rows if np.isfinite(to_float(row.get("controlled_abs_partial_rho")))]
    if not finite:
        return {}
    return sorted(finite, key=lambda row: (-to_float(row["controlled_abs_partial_rho"]), row["feature_name"]))[0]


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
