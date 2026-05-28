#!/usr/bin/env python3
"""Run Day 23 Route B analysis / pivot planning."""

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

from eval.day23_route_b_pivot import (  # noqa: E402
    BENCHMARK_FIELDNAMES,
    CLAIM_FIELDNAMES,
    FAILURE_FIELDNAMES,
    RECOMMENDATION_FIELDNAMES,
    REDESIGN_FIELDNAMES,
    build_claim_consolidation_table,
    build_diagnostic_benchmark_route,
    build_failure_taxonomy,
    derive_day24_recommendation,
    load_day18_to_day22_artifacts,
    propose_metric_redesign_candidates,
    write_csv,
    write_day23_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/validation/day23_route_b_pivot.yaml")
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--reports-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day23_route_b_pivot_report.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    config = load_config(args.config)
    try:
        artifacts = load_day18_to_day22_artifacts(args.out_root, args.reports_root)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    failures = build_failure_taxonomy(artifacts)
    claims = build_claim_consolidation_table(artifacts)
    candidates = propose_metric_redesign_candidates(artifacts)
    benchmark = build_diagnostic_benchmark_route(artifacts)
    recommendation = derive_day24_recommendation(artifacts)

    table_dir = args.out_root / "tables"
    manifest_dir = args.out_root / "manifests"
    failure_path = table_dir / "day23_failure_taxonomy.csv"
    claim_path = table_dir / "day23_claim_consolidation.csv"
    candidate_path = table_dir / "day23_metric_redesign_candidates.csv"
    benchmark_path = table_dir / "day23_diagnostic_benchmark_route.csv"
    recommendation_path = table_dir / "day23_day24_recommendation.csv"
    manifest_path = manifest_dir / "day23_route_b_pivot_manifest.json"

    write_csv(failure_path, FAILURE_FIELDNAMES, failures)
    write_csv(claim_path, CLAIM_FIELDNAMES, claims)
    write_csv(candidate_path, REDESIGN_FIELDNAMES, candidates)
    write_csv(benchmark_path, BENCHMARK_FIELDNAMES, benchmark)
    write_csv(recommendation_path, RECOMMENDATION_FIELDNAMES, recommendation)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(failures, claims, candidates, benchmark, recommendation), encoding="utf-8")

    outputs = [failure_path, claim_path, candidate_path, benchmark_path, recommendation_path, manifest_path, args.report]
    manifest = write_day23_manifest(
        manifest_path,
        inputs=artifacts["input_paths"] + [args.config],
        outputs=outputs,
        failures=failures,
        claims=claims,
        candidates=candidates,
        benchmark=benchmark,
        recommendation=recommendation,
        artifacts=artifacts,
        runtime_seconds=time.time() - start,
    )

    print(f"day23 failure taxonomy: {display_path(failure_path)}")
    print(f"day23 claim consolidation: {display_path(claim_path)}")
    print(f"day23 metric redesign candidates: {display_path(candidate_path)}")
    print(f"day23 diagnostic benchmark route: {display_path(benchmark_path)}")
    print(f"day23 recommendation: {display_path(recommendation_path)}")
    print(f"day23 manifest: {display_path(manifest_path)}")
    print(f"day23 report: {display_path(args.report)}")
    print(f"status: {manifest['status']}")
    print(f"recommended_day24_route: {manifest['recommended_day24_route']}")
    return 0 if manifest["status"] == "OK" else 1


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Day23 config must be a mapping: {path}")
    config.setdefault("route", "Route_B")
    config.setdefault("route_name", "metric_risk_redesign_or_diagnostic_benchmark_consolidation")
    return config


def build_report(
    failures: Sequence[Dict[str, str]],
    claims: Sequence[Dict[str, str]],
    candidates: Sequence[Dict[str, str]],
    benchmark: Sequence[Dict[str, str]],
    recommendation: Sequence[Dict[str, str]],
) -> str:
    selected = [row for row in recommendation if row["allowed"] == "true"]
    selected_text = "; ".join(f"{row['recommended_route']}: {row['task']}" for row in selected)
    forbidden_claims = [row["claim_id"] for row in claims if row["current_status"] == "forbidden"]
    high_failures = [row["failure_id"] for row in failures if row["severity"] in {"high", "critical"}]
    candidate_lines = "\n".join(
        f"| {row['candidate_id']} | {row['candidate_name']} | {row['priority']} | {row['required_next_test']} |"
        for row in candidates
    )
    benchmark_lines = "\n".join(
        f"| {row['route_item']} | {row['paper_claim_strength']} | {row['recommended_priority']} |"
        for row in benchmark
    )
    return f"""# Day 23 Route B Pivot Report

## Direct Answers

- Day 23 是否执行了 Route B？Yes. It follows Route B after the Day 22 No-Go gate.
- 为什么 Day 22 No-Go 不是项目失败？Because the negative gate preserves scientific validity and converts unsupported method claims into diagnostic benchmark evidence.
- ODI 单指标失败的主要原因是什么？The single-metric evidence remains weak after within-sequence, grouped/LOSO, and controlled partial screens.
- joint risk 失败的主要原因是什么？All fixed joint-risk features remain exploratory; no feature passed strict controlled validity, and no-ODI variants can be competitive.
- 当前还能支撑哪些论文 claim？Unbiased synthetic protocol, diagnostic benchmark construction, weak-direction geometry analysis, and bias audit lessons.
- 当前不能支撑哪些论文 claim？Forbidden claim IDs: `{', '.join(forbidden_claims)}`.
- 项目下一步应该走 diagnostic benchmark consolidation，还是 metric redesign？Selected Day 24 options: {selected_text}.
- Day 24 是否允许 weak-subspace update？No.

## Failure Taxonomy

High / critical failures: `{', '.join(high_failures)}`.

## Metric Redesign Candidates

| candidate_id | candidate_name | priority | required_next_test |
|---|---|---|---|
{candidate_lines}

## Diagnostic Benchmark Route

| route_item | paper_claim_strength | recommended_priority |
|---|---|---|
{benchmark_lines}

## Conclusion

Day 23 follows Route B after the Day 22 No-Go gate.
The project should not implement weak-subspace update yet.
The evidence supports a diagnostic benchmark / metric-redesign route, not a validated Degen-LIO method route.
Day 24 should continue with diagnostic consolidation or metric redesign review.
"""


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
