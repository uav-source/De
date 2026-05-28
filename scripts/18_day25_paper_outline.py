#!/usr/bin/env python3
"""Run Day 25 diagnostic benchmark paper outline / figure-table plan."""

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

from eval.day25_paper_outline import (  # noqa: E402
    CLAIM_BOUNDARY_FIELDNAMES,
    CONTRIBUTION_FIELDNAMES,
    FIGURE_TABLE_FIELDNAMES,
    RECOMMENDATION_FIELDNAMES,
    REPRO_FIELDNAMES,
    REVIEWER_FIELDNAMES,
    SECTION_FIELDNAMES,
    STORYLINE_FIELDNAMES,
    TITLE_FIELDNAMES,
    build_claim_boundary_for_paper,
    build_contribution_map,
    build_experiment_storyline,
    build_figure_table_plan,
    build_reproducibility_plan,
    build_reviewer_response_plan,
    build_section_outline,
    build_title_positioning_candidates,
    derive_day26_recommendation,
    load_day14_to_day24_artifacts,
    write_csv,
    write_day25_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/validation/day25_paper_outline.yaml")
    parser.add_argument("--day14-root", type=Path, default=ROOT / "results/day14")
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--reports-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day25_paper_outline_report.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    config = load_config(args.config)
    try:
        artifacts = load_day14_to_day24_artifacts(args.day14_root, args.out_root, args.reports_root)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    titles = build_title_positioning_candidates(artifacts)
    contributions = build_contribution_map(artifacts)
    sections = build_section_outline(artifacts)
    figures = build_figure_table_plan(artifacts)
    storyline = build_experiment_storyline(artifacts)
    claims = build_claim_boundary_for_paper(artifacts)
    repro = build_reproducibility_plan(artifacts)
    reviewer = build_reviewer_response_plan(artifacts)
    recommendation = derive_day26_recommendation(artifacts)

    table_dir = args.out_root / "tables"
    manifest_dir = args.out_root / "manifests"
    title_path = table_dir / "day25_title_positioning_candidates.csv"
    contribution_path = table_dir / "day25_contribution_map.csv"
    section_path = table_dir / "day25_section_outline.csv"
    figure_path = table_dir / "day25_figure_table_plan.csv"
    storyline_path = table_dir / "day25_experiment_storyline.csv"
    claim_path = table_dir / "day25_claim_boundary_for_paper.csv"
    repro_path = table_dir / "day25_reproducibility_plan.csv"
    reviewer_path = table_dir / "day25_reviewer_response_plan.csv"
    recommendation_path = table_dir / "day25_day26_recommendation.csv"
    manifest_path = manifest_dir / "day25_paper_outline_manifest.json"

    write_csv(title_path, TITLE_FIELDNAMES, titles)
    write_csv(contribution_path, CONTRIBUTION_FIELDNAMES, contributions)
    write_csv(section_path, SECTION_FIELDNAMES, sections)
    write_csv(figure_path, FIGURE_TABLE_FIELDNAMES, figures)
    write_csv(storyline_path, STORYLINE_FIELDNAMES, storyline)
    write_csv(claim_path, CLAIM_BOUNDARY_FIELDNAMES, claims)
    write_csv(repro_path, REPRO_FIELDNAMES, repro)
    write_csv(reviewer_path, REVIEWER_FIELDNAMES, reviewer)
    write_csv(recommendation_path, RECOMMENDATION_FIELDNAMES, recommendation)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(titles, contributions, sections, figures, claims, reviewer, recommendation), encoding="utf-8")

    outputs = [
        title_path,
        contribution_path,
        section_path,
        figure_path,
        storyline_path,
        claim_path,
        repro_path,
        reviewer_path,
        recommendation_path,
        manifest_path,
        args.report,
    ]
    manifest = write_day25_manifest(
        manifest_path,
        inputs=artifacts["input_paths"] + [args.config],
        outputs=outputs,
        titles=titles,
        contributions=contributions,
        sections=sections,
        figures=figures,
        claims=claims,
        recommendation=recommendation,
        artifacts=artifacts,
        runtime_seconds=time.time() - start,
    )

    print(f"day25 title candidates: {display_path(title_path)}")
    print(f"day25 contribution map: {display_path(contribution_path)}")
    print(f"day25 section outline: {display_path(section_path)}")
    print(f"day25 figure/table plan: {display_path(figure_path)}")
    print(f"day25 experiment storyline: {display_path(storyline_path)}")
    print(f"day25 claim boundary: {display_path(claim_path)}")
    print(f"day25 reproducibility plan: {display_path(repro_path)}")
    print(f"day25 reviewer response plan: {display_path(reviewer_path)}")
    print(f"day25 recommendation: {display_path(recommendation_path)}")
    print(f"day25 manifest: {display_path(manifest_path)}")
    print(f"day25 report: {display_path(args.report)}")
    print(f"status: {manifest['status']}")
    print(f"recommended_day26_route: {manifest['recommended_day26_route']}")
    return 0 if manifest["status"] == "OK" else 1


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Day25 config must be a mapping: {path}")
    config.setdefault("paper_route", "diagnostic_benchmark_failure_analysis")
    return config


def build_report(
    titles: Sequence[Dict[str, str]],
    contributions: Sequence[Dict[str, str]],
    sections: Sequence[Dict[str, str]],
    figures: Sequence[Dict[str, str]],
    claims: Sequence[Dict[str, str]],
    reviewer: Sequence[Dict[str, str]],
    recommendation: Sequence[Dict[str, str]],
) -> str:
    recommended_title = next(row for row in titles if row["recommended"] == "true")
    allowed_claims = [row["claim_id"] for row in claims if row["status"] in {"allowed", "conditional", "diagnostic_only"}]
    forbidden_claims = [row["claim_id"] for row in claims if row["status"] == "forbidden"]
    selected = [row for row in recommendation if row["allowed"] == "true"]
    selected_text = "; ".join(f"{row['recommended_route']}: {row['task']}" for row in selected[:3])
    contribution_lines = "\n".join(
        f"| {row['contribution_id']} | {row['contribution_text']} | {row['claim_status']} |"
        for row in contributions
    )
    figure_lines = "\n".join(
        f"| {row['item_id']} | {row['item_type']} | {row['paper_section']} | {row['priority']} |"
        for row in figures
    )
    reviewer_lines = "\n".join(
        f"| {row['risk_id']} | {row['reviewer_attack']} | {row['short_response']} |"
        for row in reviewer[:5]
    )
    section_names = ", ".join(row["section_title"] for row in sections)
    return f"""# Day 25 Diagnostic Benchmark Paper Outline Report

## Direct Answers

- Day 25 是否完成 diagnostic benchmark paper outline？Yes. It creates title candidates, contribution mapping, section outline, figure/table plan, experiment storyline, claim boundary, reproducibility plan, reviewer response plan, and Day 26 route recommendations.
- 推荐论文标题/定位是什么？Recommended title: "{recommended_title['title_candidate']}". Positioning: {recommended_title['positioning']}.
- 当前论文的核心贡献应该怎么写？Use contribution IDs with scoped wording: `{', '.join(row['contribution_id'] for row in contributions if row['claim_status'] != 'forbidden')}`.
- 哪些 claim 可以写？Allowed or scoped claim IDs: `{', '.join(allowed_claims)}`.
- 哪些 claim 绝对不能写？Forbidden claim IDs: `{', '.join(forbidden_claims)}`.
- 论文图表主线是什么？Start from benchmark geometry and weak-direction diagnostics, then bias audit, unbiased probe, strict metric validity stress tests, gate decision, claim boundary, and reproducibility commands.
- 最大审稿风险是什么？Synthetic-only scope, toy_lio not being real LIO, no estimator method, failed metric validity, and overclaiming risk.
- Day 26 应该做什么？Selected Day 26 options: {selected_text}.
- 是否允许进入 weak-subspace update？No.

## Section Outline

Planned sections: {section_names}.

## Contribution Map

| contribution_id | contribution_text | claim_status |
|---|---|---|
{contribution_lines}

## Figure / Table Plan

| item_id | item_type | paper_section | priority |
|---|---|---|---|
{figure_lines}

## Reviewer Response Snapshot

| risk_id | reviewer_attack | short_response |
|---|---|---|
{reviewer_lines}

## Conclusion

Day 25 converts the diagnostic benchmark evidence into a paper outline and figure-table plan.
The paper should be positioned as a diagnostic benchmark / failure-analysis contribution, not a validated Degen-LIO estimator method.
Weak-subspace update remains unauthorized.
Day 26 should proceed with paper skeleton drafting, figure/table planning, and README/release cleanup.
"""


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
