#!/usr/bin/env python3
"""Run Day 26 paper skeleton and release-plan generation."""

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

from eval.day26_paper_skeleton import (  # noqa: E402
    FIGURE_EXEC_FIELDNAMES,
    README_FIELDNAMES,
    RECOMMENDATION_FIELDNAMES,
    RELEASE_FIELDNAMES,
    SECTION_TASK_FIELDNAMES,
    build_figure_table_execution_plan,
    build_paper_skeleton_markdown,
    build_readme_scope_update_plan,
    build_release_cleanup_plan,
    build_section_writing_tasks,
    derive_day27_recommendation,
    load_day14_to_day25_artifacts,
    write_csv,
    write_day26_manifest,
    write_markdown_table,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/validation/day26_paper_skeleton.yaml")
    parser.add_argument("--day14-root", type=Path, default=ROOT / "results/day14")
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--reports-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs/paper")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day26_paper_skeleton_report.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    config = load_config(args.config)
    try:
        artifacts = load_day14_to_day25_artifacts(args.day14_root, args.out_root, args.reports_root)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    skeleton = build_paper_skeleton_markdown(artifacts)
    section_tasks = build_section_writing_tasks(artifacts)
    figure_tasks = build_figure_table_execution_plan(artifacts)
    readme_plan = build_readme_scope_update_plan(artifacts)
    cleanup_plan = build_release_cleanup_plan(artifacts)
    recommendation = derive_day27_recommendation(artifacts)

    table_dir = args.out_root / "tables"
    manifest_dir = args.out_root / "manifests"
    skeleton_path = args.docs_root / "diagnostic_benchmark_paper_skeleton.md"
    section_doc_path = args.docs_root / "section_writing_tasks.md"
    figure_doc_path = args.docs_root / "figure_table_execution_plan.md"
    readme_doc_path = args.docs_root / "readme_scope_update_plan.md"
    cleanup_doc_path = args.docs_root / "release_cleanup_plan.md"

    section_path = table_dir / "day26_section_writing_tasks.csv"
    figure_path = table_dir / "day26_figure_table_execution_plan.csv"
    readme_path = table_dir / "day26_readme_scope_update_plan.csv"
    cleanup_path = table_dir / "day26_release_cleanup_plan.csv"
    recommendation_path = table_dir / "day26_day27_recommendation.csv"
    manifest_path = manifest_dir / "day26_paper_skeleton_manifest.json"

    skeleton_path.parent.mkdir(parents=True, exist_ok=True)
    skeleton_path.write_text(skeleton, encoding="utf-8")
    write_markdown_table(section_doc_path, "Section Writing Tasks", SECTION_TASK_FIELDNAMES, section_tasks)
    write_markdown_table(figure_doc_path, "Figure/Table Execution Plan", FIGURE_EXEC_FIELDNAMES, figure_tasks)
    write_markdown_table(readme_doc_path, "README Scope Update Plan", README_FIELDNAMES, readme_plan)
    write_markdown_table(cleanup_doc_path, "Release Cleanup Plan", RELEASE_FIELDNAMES, cleanup_plan)

    write_csv(section_path, SECTION_TASK_FIELDNAMES, section_tasks)
    write_csv(figure_path, FIGURE_EXEC_FIELDNAMES, figure_tasks)
    write_csv(readme_path, README_FIELDNAMES, readme_plan)
    write_csv(cleanup_path, RELEASE_FIELDNAMES, cleanup_plan)
    write_csv(recommendation_path, RECOMMENDATION_FIELDNAMES, recommendation)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(section_tasks, figure_tasks, readme_plan, cleanup_plan, recommendation), encoding="utf-8")

    outputs = [
        skeleton_path,
        section_doc_path,
        figure_doc_path,
        readme_doc_path,
        cleanup_doc_path,
        section_path,
        figure_path,
        readme_path,
        cleanup_path,
        recommendation_path,
        manifest_path,
        args.report,
    ]
    manifest = write_day26_manifest(
        manifest_path,
        inputs=artifacts["input_paths"] + [args.config],
        outputs=outputs,
        skeleton_path=skeleton_path,
        sections=section_tasks,
        figures=figure_tasks,
        readme=readme_plan,
        cleanup=cleanup_plan,
        recommendation=recommendation,
        artifacts=artifacts,
        runtime_seconds=time.time() - start,
    )

    print(f"day26 paper skeleton: {display_path(skeleton_path)}")
    print(f"day26 section tasks: {display_path(section_path)}")
    print(f"day26 figure/table plan: {display_path(figure_path)}")
    print(f"day26 readme plan: {display_path(readme_path)}")
    print(f"day26 release cleanup plan: {display_path(cleanup_path)}")
    print(f"day26 recommendation: {display_path(recommendation_path)}")
    print(f"day26 manifest: {display_path(manifest_path)}")
    print(f"day26 report: {display_path(args.report)}")
    print(f"status: {manifest['status']}")
    print(f"recommended_day27_route: {manifest['recommended_day27_route']}")
    return 0 if manifest["status"] == "OK" else 1


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Day26 config must be a mapping: {path}")
    config.setdefault("paper_route", "diagnostic_benchmark_failure_analysis")
    return config


def build_report(
    section_tasks: Sequence[Dict[str, str]],
    figure_tasks: Sequence[Dict[str, str]],
    readme_plan: Sequence[Dict[str, str]],
    cleanup_plan: Sequence[Dict[str, str]],
    recommendation: Sequence[Dict[str, str]],
) -> str:
    direct_figures = [row["item_id"] for row in figure_tasks if row["generation_status"] == "source_available"]
    pending_figures = [row["item_id"] for row in figure_tasks if row["generation_status"] == "pending"]
    selected = [row for row in recommendation if row["allowed"] == "true"]
    selected_text = "; ".join(f"{row['recommended_route']}: {row['task']}" for row in selected[:3])
    readme_sections = ", ".join(row["readme_section"] for row in readme_plan)
    cleanup_items = ", ".join(row["path_or_pattern"] for row in cleanup_plan)
    return f"""# Day 26 Paper Skeleton / Release Plan Report

## Direct Answers

- Day 26 是否生成 paper skeleton？Yes. `docs/paper/diagnostic_benchmark_paper_skeleton.md` was generated with editable sections and claim boundaries.
- 论文定位是什么？The project remains a diagnostic benchmark package, not a validated Degen-LIO estimator method.
- 哪些章节已经有证据支撑？All {len(section_tasks)} sections are linked to Day14-Day25 evidence through `day26_section_writing_tasks.csv`.
- 哪些图表可以直接从现有 artifact 生成？Source-available items: `{', '.join(direct_figures)}`.
- 哪些图表仍是 pending？Pending items: `{', '.join(pending_figures)}`.
- README 需要怎么更新？Required README sections: {readme_sections}.
- release 包需要清理哪些内容？Cleanup plan covers: {cleanup_items}.
- 是否允许进入 weak-subspace update？No.
- Day 27 应该做什么？Selected Day 27 options: {selected_text}.

## Conclusion

Day 26 creates a paper skeleton and release plan for the diagnostic benchmark / failure-analysis route.
The project remains a diagnostic benchmark package, not a validated Degen-LIO estimator method.
Weak-subspace update remains unauthorized.
Day 27 should proceed with README/release cleanup and figure/table generation planning, not method implementation.
"""


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
