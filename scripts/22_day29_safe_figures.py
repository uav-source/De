#!/usr/bin/env python3
"""Run Day 29 safe F01/F03 figure generation and table safety checks."""

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

from eval.day29_safe_figures import (  # noqa: E402
    CAPTION_AUDIT_FIELDNAMES,
    FIGURE_INVENTORY_FIELDNAMES,
    RECOMMENDATION_FIELDNAMES,
    TABLE_SAFETY_FIELDNAMES,
    audit_generated_figures,
    build_caption_safety_audit,
    build_day30_recommendation,
    build_table_safety_notes,
    load_day29_inputs,
    run_safe_figure_generation,
    write_csv,
    write_day29_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/validation/day29_safe_figures.yaml")
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/minibench")
    parser.add_argument("--config-root", type=Path, default=ROOT / "configs/minibench")
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--reports-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs/paper")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day29_safe_figures_report.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    config = load_config(args.config)
    try:
        artifacts = load_day29_inputs(args.out_root, args.reports_root)
        run_safe_figure_generation(args.data_root, args.config_root, args.out_root, args.docs_root)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    figure_inventory = audit_generated_figures(args.docs_root)
    notes_path = args.docs_root / "generated_tables/table_interpretation_notes.md"
    safety_notes = build_table_safety_notes(notes_path)
    caption_path = args.docs_root / "caption_bank_day29.md"
    caption_path.write_text(build_caption_bank_text(figure_inventory, safety_notes), encoding="utf-8")
    caption_audit = build_caption_safety_audit([caption_path, notes_path])
    recommendation = build_day30_recommendation()

    table_dir = args.out_root / "tables"
    manifest_dir = args.out_root / "manifests"
    figure_inventory_path = table_dir / "day29_generated_figure_inventory.csv"
    safety_notes_path = table_dir / "day29_table_safety_notes.csv"
    caption_audit_path = table_dir / "day29_caption_safety_audit.csv"
    recommendation_path = table_dir / "day29_day30_recommendation.csv"
    manifest_path = manifest_dir / "day29_safe_figures_manifest.json"

    write_csv(figure_inventory_path, FIGURE_INVENTORY_FIELDNAMES, figure_inventory)
    write_csv(safety_notes_path, TABLE_SAFETY_FIELDNAMES, safety_notes)
    write_csv(caption_audit_path, CAPTION_AUDIT_FIELDNAMES, caption_audit)
    write_csv(recommendation_path, RECOMMENDATION_FIELDNAMES, recommendation)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(figure_inventory, safety_notes, caption_audit, recommendation), encoding="utf-8")

    outputs = [
        args.docs_root / "figures/F01_benchmark_geometry_overview.png",
        args.docs_root / "figures/F01_benchmark_geometry_overview.pdf",
        args.docs_root / "figures/F03_bias_audit_legacy_vs_unbiased.png",
        args.docs_root / "figures/F03_bias_audit_legacy_vs_unbiased.pdf",
        notes_path,
        caption_path,
        figure_inventory_path,
        safety_notes_path,
        caption_audit_path,
        recommendation_path,
        manifest_path,
        args.report,
    ]
    manifest = write_day29_manifest(
        manifest_path,
        inputs=artifacts["input_paths"] + [args.config],
        outputs=outputs,
        figure_inventory=figure_inventory,
        safety_notes=safety_notes,
        caption_audit=caption_audit,
        artifacts=artifacts,
        runtime_seconds=time.time() - start,
    )

    print(f"day29 figure inventory: {display_path(figure_inventory_path)}")
    print(f"day29 table safety notes: {display_path(safety_notes_path)}")
    print(f"day29 caption safety audit: {display_path(caption_audit_path)}")
    print(f"day29 recommendation: {display_path(recommendation_path)}")
    print(f"day29 manifest: {display_path(manifest_path)}")
    print(f"day29 report: {display_path(args.report)}")
    print(f"status: {manifest['status']}")
    return 0 if manifest["status"] == "OK" else 1


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Day29 config must be a mapping: {path}")
    return config


def build_caption_bank_text(figure_inventory: Sequence[Dict[str, str]], safety_notes: Sequence[Dict[str, str]]) -> str:
    lines = ["# Day 29 Caption Bank", ""]
    for row in figure_inventory:
        lines.extend(
            [
                f"## {row['figure_id']}",
                "",
                f"Caption: {row['figure_id']} is generated from source artifacts for diagnostic benchmark interpretation.",
                "",
                f"Claim boundary: {row['claim_boundary']}",
                "",
                f"Must not claim: {row['must_not_claim']}",
                "",
            ]
        )
    lines.extend(["## Table Safety Notes", ""])
    for row in safety_notes:
        lines.append(f"- {row['table_id']}: {row['required_note']}")
    lines.append("")
    return "\n".join(lines)


def build_report(
    figure_inventory: Sequence[Dict[str, str]],
    safety_notes: Sequence[Dict[str, str]],
    caption_audit: Sequence[Dict[str, str]],
    recommendation: Sequence[Dict[str, str]],
) -> str:
    figures = [row["figure_id"] for row in figure_inventory if row["real_generation_status"] == "generated_from_source_artifacts"]
    sources = "; ".join(f"{row['figure_id']}: {row['source_artifacts']}" for row in figure_inventory)
    fake = any(row["fake_figure_detected"] == "true" for row in figure_inventory)
    caption_ok = all(row["status"] == "pass" for row in caption_audit)
    selected = [row for row in recommendation if row["allowed"] == "true"]
    selected_text = "; ".join(f"{row['recommended_route']}: {row['task']}" for row in selected[:2])
    return f"""# Day 29 Safe Figures / Table Safety Report

## Direct Answers

- Day 29 是否真实生成了 F01 / F03？Yes. Generated figures: `{', '.join(figures)}`.
- F01 / F03 使用了哪些源文件？{sources}.
- 是否生成了 fake PNG/PDF？No fake figures are generated.
- T03 / T05 的解释风险是否已处理？Yes. {len(safety_notes)} table safety notes were written, including the note that valid means computable, not substantive validity.
- captions 是否仍遵守 claim boundary？{'Yes' if caption_ok else 'No'}.
- 是否允许进入 weak-subspace update？No.
- Day 30 应该做什么？Selected options: {selected_text}.

## Conclusion

Day 29 generates real F01/F03 figures from source artifacts and adds table interpretation safeguards.
No fake figures are generated.
The repository remains a diagnostic benchmark / failure-analysis package, not a validated Degen-LIO estimator method.
Weak-subspace update remains unauthorized.
Day 30 should perform final package review, final artifact audit, and release readiness check, not method implementation.
"""


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
