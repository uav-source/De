#!/usr/bin/env python3
"""Render the fixed Day 8 diagnostic plot set from compact evidence."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


RUN_IDS = tuple(
    f"multihyp_day8_range_query_r{index}" for index in range(1, 5)
)


def _csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _save(path: Path, title: str, x, series, ylabel: str) -> None:
    fig, axis = plt.subplots(figsize=(10, 5.5))
    for label, values in series:
        series_x = x if len(x) == len(values) else range(len(values))
        axis.plot(
            series_x, values, marker=".", linewidth=1, label=label
        )
    axis.set_title(title)
    axis.set_xlabel("query index")
    axis.set_ylabel(ylabel)
    axis.grid(alpha=0.25)
    if len(series) > 1:
        axis.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _bar(path: Path, title: str, labels, values, ylabel: str) -> None:
    fig, axis = plt.subplots(figsize=(10, 5.5))
    axis.bar(range(len(labels)), values)
    axis.set_xticks(range(len(labels)), labels, rotation=25, ha="right")
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--root-cause-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    queries = {
        run_id: _csv(
            args.runtime_root / run_id
            / "day8_range_query_summary_index.csv"
        )
        for run_id in RUN_IDS
    }
    shadow = _csv(
        args.comparison_dir / "day8_shadow_voxel_query_comparison.csv"
    )
    shadow_by_run = {
        run_id: [row for row in shadow if row["run_id"] == run_id]
        for run_id in RUN_IDS
    }
    pair_doc = json.loads(
        (
            args.comparison_dir
            / "pairwise_day8_first_range_query_divergence.json"
        ).read_text(encoding="utf-8")
    )
    root_doc = json.loads(
        (
            args.root_cause_dir
            / "pairwise_day8_root_cause_classification.json"
        ).read_text(encoding="utf-8")
    )
    formal_clusters = json.loads(
        (args.comparison_dir / "formal_query_result_clusters.json").read_text(
            encoding="utf-8"
        )
    )
    traversal_clusters = json.loads(
        (
            args.comparison_dir / "range_traversal_trace_clusters.json"
        ).read_text(encoding="utf-8")
    )
    _bar(
        args.output_dir / "day8_formal_query_result_clusters.png",
        "Formal query-result trace clusters",
        [item["cluster_id"] for item in formal_clusters["clusters"]],
        [len(item["runs"]) for item in formal_clusters["clusters"]],
        "run count",
    )
    _bar(
        args.output_dir / "day8_range_traversal_trace_clusters.png",
        "Range traversal-token trace clusters",
        [item["cluster_id"] for item in traversal_clusters["clusters"]],
        [len(item["runs"]) for item in traversal_clusters["clusters"]],
        "run count",
    )
    pair_labels = [
        f"{item['left_run_id'][-2:]}-{item['right_run_id'][-2:]}"
        for item in pair_doc["pairs"]
    ]
    pair_indices = [
        -1 if item.get("aligned_query_index") is None
        else int(item["aligned_query_index"])
        for item in pair_doc["pairs"]
    ]
    _bar(
        args.output_dir / "day8_first_query_divergence_by_pair.png",
        "First formal range-query divergence by run pair",
        pair_labels, pair_indices, "aligned query index (-1 = none)",
    )
    reference = shadow_by_run[RUN_IDS[0]]
    x = list(range(len(reference)))
    _save(
        args.output_dir / "day8_shadow_vs_formal_member_count.png",
        "Shadow logical members vs formal Search_by_range results",
        x,
        [
            ("shadow", [int(row["shadow_member_count"]) for row in reference]),
            ("formal", [int(row["formal_result_count"]) for row in reference]),
        ],
        "member count",
    )
    _save(
        args.output_dir / "day8_missing_expected_member_timeline.png",
        "Missing expected formal members",
        x,
        [(
            "missing",
            [
                len([v for v in row["missing_from_formal_result"].split(";") if v])
                for row in reference
            ],
        )],
        "missing count",
    )
    for filename, title, field, ylabel in (
        (
            "day8_query_result_count_timeline.png",
            "Formal query result count", "formal_result_count", "result count",
        ),
        (
            "day8_visited_node_count_timeline.png",
            "Visited node count", "visited_node_count", "visited nodes",
        ),
        (
            "day8_deleted_skip_timeline.png",
            "Deleted-point skips", "point_deleted_skip_count", "skip count",
        ),
        (
            "day8_rebuild_generation_timeline.png",
            "Rebuild generation observed at formal query",
            "rebuild_generation", "generation",
        ),
    ):
        _save(
            args.output_dir / filename, title,
            list(range(len(queries[RUN_IDS[0]]))),
            [
                (
                    run_id[-2:],
                    [int(row[field]) for row in queries[run_id]],
                )
                for run_id in RUN_IDS
            ],
            ylabel,
        )
    _save(
        args.output_dir / "day8_pruning_count_timeline.png",
        "Range-search pruning counters",
        list(range(len(queries[RUN_IDS[0]]))),
        [
            (
                field,
                [int(row[field]) for row in queries[RUN_IDS[0]]],
            )
            for field in (
                "no_intersection_prune_count", "full_cover_subtree_count",
                "partial_intersection_node_count",
            )
        ],
        "counter",
    )
    witness = json.loads(
        (
            args.comparison_dir / "known_day7_witness_query_comparison.json"
        ).read_text(encoding="utf-8")
    )
    _bar(
        args.output_dir / "day8_known_witness_query_context.png",
        "Known Day 7 witness: shadow and formal members",
        [row["run_id"][-2:] for row in witness["per_run"]],
        [
            int(row["shadow_member_count"]) - int(row["formal_result_count"])
            for row in witness["per_run"]
        ],
        "shadow minus formal member count",
    )
    traversal_diff = _csv(
        args.root_cause_dir / "first_divergent_query_traversal_diff.csv"
    )
    _bar(
        args.output_dir / "day8_first_divergent_traversal_tokens.png",
        "First divergent query traversal-token differences",
        [str(row["token_index"]) for row in traversal_diff]
        or ["NO_RANGE_SEARCH_DIVERGENCE_REPRODUCED"],
        [
            len(row["differing_fields"].split(";"))
            for row in traversal_diff
        ] or [0],
        "differing fields",
    )
    complete = sum(
        int(row["formal_query_completeness_pass"]) for row in shadow
    )
    _bar(
        args.output_dir / "day8_query_completeness_summary.png",
        "Formal query completeness against shadow membership",
        ["complete", "violation"], [complete, len(shadow) - complete],
        "query count",
    )
    classifications = Counter(
        item["classification"] for item in root_doc["pairs"]
    )
    _bar(
        args.output_dir / "day8_root_cause_classification_summary.png",
        "Pairwise Day 8 root-cause classifications",
        list(classifications), list(classifications.values()), "pair count",
    )
    query_counts = [len(queries[run_id]) for run_id in RUN_IDS]
    token_counts = [
        len(_csv(
            args.runtime_root / run_id
            / "day8_range_traversal_token_index.csv"
        ))
        for run_id in RUN_IDS
    ]
    _bar(
        args.output_dir / "day8_instrumentation_cost.png",
        "Bounded diagnostic record volume (timing perturbation present)",
        [f"{run_id[-2:]} queries" for run_id in RUN_IDS]
        + [f"{run_id[-2:]} tokens" for run_id in RUN_IDS],
        query_counts + token_counts,
        "record count",
    )
    summary = {
        "schema_version": "day8_plot_summary_v1",
        "plot_count": 15,
        "plot_files": sorted(path.name for path in args.output_dir.glob("*.png")),
        "no_range_search_divergence_reproduced_label_used":
            all(value == -1 for value in pair_indices),
        "instrumentation_timing_perturbation_present": True,
    }
    (
        args.output_dir / "day8_plot_summary.json"
    ).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
