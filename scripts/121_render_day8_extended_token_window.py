#!/usr/bin/env python3
"""Render the fixed fifteen-figure Day 8 extended-token evidence set."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
RUN_IDS = tuple(
    "multihyp_day8_extended_token_r%d" % index
    for index in range(1, 5)
)


def _load(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(
        "day8_extended_plot_base", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import Day 8 plotter")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _bar(path: Path, title: str, labels, values, ylabel: str) -> None:
    figure, axis = plt.subplots(figsize=(10, 5.5))
    axis.bar(range(len(labels)), values)
    axis.set_xticks(range(len(labels)), labels, rotation=25, ha="right")
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=160)
    plt.close(figure)


def _compatibility_inputs(
    comparison_dir: Path,
    root_cause_dir: Path,
) -> None:
    aliases = {
        comparison_dir / "pairwise_day8_first_range_query_divergence.json":
            comparison_dir
            / "pairwise_extended_first_query_divergence.json",
        comparison_dir / "formal_query_result_clusters.json":
            comparison_dir / "extended_query_result_clusters.json",
        comparison_dir / "range_traversal_trace_clusters.json":
            comparison_dir / "extended_traversal_trace_clusters.json",
        root_cause_dir / "pairwise_day8_root_cause_classification.json":
            root_cause_dir
            / "pairwise_extended_root_cause_classification.json",
    }
    for target, source in aliases.items():
        shutil.copy2(source, target)
    shadow = _csv(
        comparison_dir / "day8_shadow_voxel_query_comparison.csv"
    )
    first = json.loads(
        (
            comparison_dir
            / "pairwise_extended_first_query_divergence.json"
        ).read_text(encoding="utf-8")
    )
    divergent = [
        item for item in first["pairs"]
        if item.get("aligned_query_index") is not None
    ]
    per_run: list[dict[str, Any]] = []
    if divergent:
        item = min(
            divergent,
            key=lambda value: (
                int(value["aligned_query_index"]),
                value["left_run_id"],
                value["right_run_id"],
            ),
        )
        query = item["left_query"]
        for run_id in RUN_IDS:
            match = next(
                (
                    row for row in shadow
                    if row["run_id"] == run_id
                    and int(row["scan_index"]) == int(query["scan_index"])
                    and int(row["call_index"])
                    == int(query["map_mutation_call_index"])
                    and int(row["batch_point_index"])
                    == int(query["batch_point_index"])
                    and row["candidate_point_sha256"]
                    == query["candidate_point_sha256"]
                    and row["voxel_identity"] == query["voxel_identity"]
                    and int(row["query_box_checksum"])
                    == int(query["query_box_checksum"])
                ),
                None,
            )
            if match is not None:
                per_run.append(match)
    if not per_run:
        per_run = [
            next(row for row in shadow if row["run_id"] == run_id)
            for run_id in RUN_IDS
        ]
    (
        comparison_dir / "known_day7_witness_query_comparison.json"
    ).write_text(
        json.dumps({
            "schema_version": "extended_plot_witness_compatibility_v1",
            "per_run": per_run,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--root-cause-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _compatibility_inputs(args.comparison_dir, args.root_cause_dir)
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
        "extended_query_result_clusters.png":
            "day8_formal_query_result_clusters.png",
        "extended_first_query_divergence.png":
            "day8_first_query_divergence_by_pair.png",
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
        "query_completeness_summary.png":
            "day8_query_completeness_summary.png",
        "instrumentation_cost.png":
            "day8_instrumentation_cost.png",
    }
    for target, source in aliases.items():
        shutil.copy2(args.output_dir / source, args.output_dir / target)

    for scan in (157, 162):
        counts = []
        captured = []
        for run_id in RUN_IDS:
            summary = json.loads(
                (
                    args.runtime_root / run_id
                    / "day8_token_capture_coverage_summary.json"
                ).read_text(encoding="utf-8")
            )
            counts.append(summary["scan%d_query_count" % scan])
            captured.append(
                summary[
                    "scan%d_query_with_detailed_token_count" % scan
                ]
            )
        _bar(
            args.output_dir / ("scan%d_token_coverage.png" % scan),
            "Scan %d detailed-token coverage" % scan,
            [run_id[-2:] for run_id in RUN_IDS],
            [
                100.0 * value / total if total else 0.0
                for value, total in zip(captured, counts)
            ],
            "coverage percent",
        )
    null_audit = json.loads(
        (
            args.root_cause_dir / "null_token_semantics_audit.json"
        ).read_text(encoding="utf-8")
    )
    labels = list(null_audit["document_record_counts"])
    values = [
        null_audit["document_record_counts"][label] for label in labels
    ]
    _bar(
        args.output_dir / "null_token_semantics_audit.png",
        "TOKEN_CAPTURE_SEMANTICS_V2 output-layer audit",
        labels or ["no comparison records"],
        values or [0],
        "validated comparison records",
    )
    targets = {
        "extended_query_result_clusters.png",
        "extended_first_query_divergence.png",
        "scan157_token_coverage.png",
        "scan162_token_coverage.png",
        "shadow_vs_formal_members.png",
        "first_query_visited_nodes.png",
        "first_query_prune_counts.png",
        "first_query_token_sequence_diff.png",
        "missing_expected_point_path.png",
        "deleted_flag_visibility.png",
        "rebuild_generation_context.png",
        "traversal_root_cause_summary.png",
        "query_completeness_summary.png",
        "null_token_semantics_audit.png",
        "instrumentation_cost.png",
    }
    for path in args.output_dir.glob("*.png"):
        if path.name not in targets:
            path.unlink()
    if {path.name for path in args.output_dir.glob("*.png")} != targets:
        raise RuntimeError("extended plot set is incomplete")
    (
        args.output_dir / "day8_extended_plot_summary.json"
    ).write_text(
        json.dumps({
            "schema_version": "day8_extended_plot_summary_v1",
            "plot_count": len(targets),
            "plot_files": sorted(targets),
            "instrumentation_timing_perturbation_present": True,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        raise SystemExit(1)
