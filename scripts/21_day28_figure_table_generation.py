#!/usr/bin/env python3
"""Run Day 28 paper-ready table conversion and pending figure planning."""

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

from eval.day28_figure_table_generation import (  # noqa: E402
    CAPTION_FIELDNAMES,
    GENERATED_INVENTORY_FIELDNAMES,
    PENDING_FIGURE_FIELDNAMES,
    RECOMMENDATION_FIELDNAMES,
    build_caption_bank,
    build_day29_recommendation,
    build_generated_table_inventory,
    build_pending_figure_plan,
    load_day28_inputs,
    load_figure_table_readiness,
    write_csv,
    write_day28_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/validation/day28_figure_table_generation.yaml")
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--reports-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs/paper")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day28_figure_table_generation_report.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    config = load_config(args.config)
    try:
        artifacts = load_day28_inputs(args.out_root, args.reports_root)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    readiness = load_figure_table_readiness(artifacts)
    generated_dir = args.docs_root / "generated_tables"
    pending_dir = args.docs_root / "pending_figures"
    caption_path = args.docs_root / "caption_bank.md"
    generated_inventory, generated_outputs = build_generated_table_inventory(
        readiness=readiness,
        day25_plan=artifacts["day25_figure_plan"],
        generated_dir=generated_dir,
        table_items=config["table_items"],
    )
    pending_figures, pending_outputs = build_pending_figure_plan(
        readiness=readiness,
        day25_plan=artifacts["day25_figure_plan"],
        pending_dir=pending_dir,
        pending_items=config["pending_figure_items"],
    )
    captions, caption_output = build_caption_bank(
        day25_plan=artifacts["day25_figure_plan"],
        generated_inventory=generated_inventory,
        pending_figures=pending_figures,
        caption_path=caption_path,
    )
    recommendation = build_day29_recommendation()

    table_dir = args.out_root / "tables"
    manifest_dir = args.out_root / "manifests"
    inventory_path = table_dir / "day28_generated_table_inventory.csv"
    pending_path = table_dir / "day28_pending_figure_plan.csv"
    caption_csv_path = table_dir / "day28_caption_bank.csv"
    recommendation_path = table_dir / "day28_day29_recommendation.csv"
    manifest_path = manifest_dir / "day28_figure_table_generation_manifest.json"

    write_csv(inventory_path, GENERATED_INVENTORY_FIELDNAMES, generated_inventory)
    write_csv(pending_path, PENDING_FIGURE_FIELDNAMES, pending_figures)
    write_csv(caption_csv_path, CAPTION_FIELDNAMES, captions)
    write_csv(recommendation_path, RECOMMENDATION_FIELDNAMES, recommendation)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(generated_inventory, pending_figures, captions, recommendation), encoding="utf-8")

    outputs = [
        *generated_outputs,
        *pending_outputs,
        caption_output,
        inventory_path,
        pending_path,
        caption_csv_path,
        recommendation_path,
        manifest_path,
        args.report,
    ]
    manifest = write_day28_manifest(
        manifest_path,
        inputs=artifacts["input_paths"] + [args.config],
        outputs=outputs,
        generated_inventory=generated_inventory,
        pending_figures=pending_figures,
        captions=captions,
        artifacts=artifacts,
        runtime_seconds=time.time() - start,
    )

    print(f"day28 generated table inventory: {display_path(inventory_path)}")
    print(f"day28 pending figure plan: {display_path(pending_path)}")
    print(f"day28 caption bank: {display_path(caption_csv_path)}")
    print(f"day28 recommendation: {display_path(recommendation_path)}")
    print(f"day28 manifest: {display_path(manifest_path)}")
    print(f"day28 report: {display_path(args.report)}")
    print(f"status: {manifest['status']}")
    print(f"generated_table_count: {manifest['generated_table_count']}")
    print(f"pending_figure_count: {manifest['pending_figure_count']}")
    return 0 if manifest["status"] == "OK" else 1


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Day28 config must be a mapping: {path}")
    config.setdefault("table_items", ["T01", "T02", "T03", "T04", "T05", "T06", "T07", "T08"])
    config.setdefault("pending_figure_items", ["F01", "F03"])
    return config


def build_report(
    generated_inventory: Sequence[Dict[str, str]],
    pending_figures: Sequence[Dict[str, str]],
    captions: Sequence[Dict[str, str]],
    recommendation: Sequence[Dict[str, str]],
) -> str:
    generated = [row["item_id"] for row in generated_inventory if row["generated"] == "true"]
    pending = [row["item_id"] for row in pending_figures]
    selected = [row for row in recommendation if row["allowed"] == "true"]
    selected_text = "; ".join(f"{row['recommended_route']}: {row['task']}" for row in selected[:2])
    return f"""# Day 28 Figure/Table Generation Report

## Direct Answers

- Day 28 是否生成了 paper-ready tables？Yes. Generated tables: `{', '.join(generated)}`.
- 哪些表格已经可直接进入论文草稿？`{', '.join(generated)}`.
- F01 / F03 为什么仍是 pending？They require real figure-generation scripts and cannot be replaced by fake PNG/PDF files.
- 是否生成了假图？No fake figures are generated.
- captions 是否遵守 claim boundary？Yes. {len(captions)} captions were written with diagnostic-only claim boundaries.
- 是否允许进入 weak-subspace update？No.
- Day 29 应该做什么？Selected options: {selected_text}.

## Conclusion

Day 28 converts existing validated artifacts into paper-ready tables and prepares explicit plans for pending figures.
No fake figures are generated.
The repository remains a diagnostic benchmark / failure-analysis package, not a validated Degen-LIO estimator method.
Weak-subspace update remains unauthorized.
Day 29 should proceed with paper section drafting or safe figure-generation script implementation, not method implementation.
"""


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
