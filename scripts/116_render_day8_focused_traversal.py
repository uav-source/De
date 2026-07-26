#!/usr/bin/env python3
"""Render the fixed fourteen-figure focused traversal evidence set."""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUN_IDS = tuple(
    f"multihyp_day8_focused_traversal_r{index}" for index in range(1, 5)
)


def _load(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(
        "day8_focused_plot_base", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import Day 8 plotter")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--root-cause-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    base = _load(ROOT / "scripts/111_render_day8_plots.py")
    base.RUN_IDS = RUN_IDS
    prior = sys.argv
    sys.argv = [
        str(ROOT / "scripts/111_render_day8_plots.py"),
        "--runtime-root", str(args.runtime_root),
        "--comparison-dir", str(args.comparison_dir),
        "--root-cause-dir", str(args.root_cause_dir),
        "--output-dir", str(args.output_dir),
    ]
    try:
        code = int(base.main())
    finally:
        sys.argv = prior
    if code != 0:
        return code
    aliases = {
        "focused_query_result_clusters.png":
            "day8_formal_query_result_clusters.png",
        "focused_first_query_divergence.png":
            "day8_first_query_divergence_by_pair.png",
        "scan157_token_coverage.png":
            "day8_range_traversal_trace_clusters.png",
        "shadow_vs_formal_members.png":
            "day8_shadow_vs_formal_member_count.png",
        "first_query_visited_nodes.png":
            "day8_visited_node_count_timeline.png",
        "first_query_prune_counts.png":
            "day8_pruning_count_timeline.png",
        "first_query_token_sequence_diff.png":
            "day8_first_divergent_traversal_tokens.png",
        "missing_expected_point_path.png":
            "day8_missing_expected_member_timeline.png",
        "deleted_flag_visibility.png":
            "day8_deleted_skip_timeline.png",
        "rebuild_generation_context.png":
            "day8_rebuild_generation_timeline.png",
        "traversal_root_cause_summary.png":
            "day8_root_cause_classification_summary.png",
        "shadow_accounting_summary.png":
            "day8_known_witness_query_context.png",
        "query_completeness_summary.png":
            "day8_query_completeness_summary.png",
        "instrumentation_cost.png":
            "day8_instrumentation_cost.png",
    }
    for target, source in aliases.items():
        shutil.copy2(args.output_dir / source, args.output_dir / target)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
