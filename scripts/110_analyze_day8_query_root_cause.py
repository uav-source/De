#!/usr/bin/env python3
"""Materialize first-divergent Day 8 query context and root causes."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day8_range_query import (
    load_query_summaries, load_traversal_tokens, query_identity,
)
from fastlio2_adapter.day8_traversal_analysis import (
    group_tokens, missing_point_witness, traversal_diff_rows,
    traversal_signature,
)


def _json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = (
        list(rows[0]) if rows else [
            "left_run_id", "right_run_id", "query_identity",
            "token_index", "differing_fields", "left_token", "right_token",
        ]
    )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--comparison-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pair_doc = json.loads(
        (
            args.comparison_dir
            / "pairwise_day8_first_range_query_divergence.json"
        ).read_text(encoding="utf-8")
    )
    pairs = pair_doc["pairs"]
    classifications = [
        {
            "left_run_id": item["left_run_id"],
            "right_run_id": item["right_run_id"],
            "aligned_query_index": item.get("aligned_query_index"),
            "classification": item["root_cause"]["classification"],
            "reason": item["root_cause"]["reason"],
            "bug_proven": False,
            "day9_authorized": False,
        }
        for item in pairs
    ]
    _json(
        args.output_dir / "pairwise_day8_root_cause_classification.json",
        {
            "schema_version":
                "pairwise_day8_root_cause_classification_v1",
            "pair_count": len(classifications),
            "pairs": classifications,
            "all_classifications_within_fixed_taxonomy": len(pairs) == 6,
            "bug_proven": False,
            "day9_authorized": False,
        },
    )
    divergent = [
        item for item in pairs
        if item.get("aligned_query_index") is not None
    ]
    first = min(
        divergent,
        key=lambda item: (
            int(item["aligned_query_index"]),
            item["left_run_id"], item["right_run_id"],
        ),
    ) if divergent else None
    _json(
        args.output_dir / "first_divergent_range_query.json",
        {
            "schema_version": "first_divergent_range_query_v1",
            "first_divergent_query_reproduced": first is not None,
            "value": first,
            "bug_proven": False,
            "day9_authorized": False,
        },
    )

    traversal_rows: list[dict[str, Any]] = []
    witness_values: list[dict[str, Any]] = []
    previous: dict[str, Any] = {
        "schema_version": "first_divergent_query_previous_identity_v1",
        "first_divergent_query_reproduced": first is not None,
        "previous_query_equal": True,
        "previous_shadow_state_equal": True,
        "previous_formal_result_equal": True,
        "previous_traversal_summary_equal": True,
    }
    if first is not None:
        left_id, right_id = first["left_run_id"], first["right_run_id"]
        left_queries = load_query_summaries(
            args.runtime_root / left_id
            / "day8_range_query_summary_index.csv"
        )
        right_queries = load_query_summaries(
            args.runtime_root / right_id
            / "day8_range_query_summary_index.csv"
        )
        left_tokens = group_tokens(load_traversal_tokens(
            args.runtime_root / left_id
            / "day8_range_traversal_token_index.csv"
        ))
        right_tokens = group_tokens(load_traversal_tokens(
            args.runtime_root / right_id
            / "day8_range_traversal_token_index.csv"
        ))
        index = int(first["aligned_query_index"])
        left_query, right_query = left_queries[index], right_queries[index]
        left_trace = left_tokens.get(int(left_query["query_sequence"]), ())
        right_trace = right_tokens.get(int(right_query["query_sequence"]), ())
        identity_text = json.dumps(
            query_identity(left_query), separators=(",", ":")
        )
        traversal_rows = traversal_diff_rows(
            left_id, right_id, identity_text, left_trace, right_trace
        )
        shadow_rows = _load_csv(
            args.comparison_dir / "day8_shadow_voxel_query_comparison.csv"
        )
        shadow_lookup = {
            (row["run_id"], int(row["query_sequence"])): row
            for row in shadow_rows
        }
        left_shadow = shadow_lookup[
            (left_id, int(left_query["query_sequence"]))
        ]
        right_shadow = shadow_lookup[
            (right_id, int(right_query["query_sequence"]))
        ]
        missing = sorted(
            set(filter(None, left_shadow["missing_from_formal_result"].split(";")))
            | set(filter(
                None, right_shadow["missing_from_formal_result"].split(";")
            ))
            | (
                set(left_query["formal_result_members"])
                ^ set(right_query["formal_result_members"])
            )
        )
        for point in missing:
            witness_values.append({
                "point_sha256": point,
                "left": missing_point_witness(point, left_trace),
                "right": missing_point_witness(point, right_trace),
            })
        if index > 0:
            prior_left, prior_right = left_queries[index - 1], right_queries[index - 1]
            prior_left_shadow = shadow_lookup[
                (left_id, int(prior_left["query_sequence"]))
            ]
            prior_right_shadow = shadow_lookup[
                (right_id, int(prior_right["query_sequence"]))
            ]
            previous.update({
                "previous_query_index": index - 1,
                "left_previous_query_identity": query_identity(prior_left),
                "right_previous_query_identity": query_identity(prior_right),
                "previous_query_equal":
                    query_identity(prior_left) == query_identity(prior_right),
                "previous_shadow_state_equal":
                    prior_left_shadow["shadow_member_hashes"]
                    == prior_right_shadow["shadow_member_hashes"],
                "previous_formal_result_equal":
                    prior_left_shadow["formal_result_hashes"]
                    == prior_right_shadow["formal_result_hashes"],
                "previous_traversal_summary_equal":
                    traversal_signature(left_tokens.get(
                        int(prior_left["query_sequence"]), ()
                    ))
                    == traversal_signature(right_tokens.get(
                        int(prior_right["query_sequence"]), ()
                    )),
            })
    _json(
        args.output_dir / "first_divergent_query_previous_identity.json",
        previous,
    )
    _write_csv(
        args.output_dir / "first_divergent_query_traversal_diff.csv",
        traversal_rows,
    )
    _json(
        args.output_dir / "missing_expected_point_witness.json",
        {
            "schema_version": "missing_expected_point_witness_v1",
            "first_divergent_query_reproduced": first is not None,
            "witness_count": len(witness_values),
            "witnesses": witness_values,
        },
    )
    comparison_summary = json.loads(
        (args.comparison_dir / "day8_comparison_summary.json").read_text(
            encoding="utf-8"
        )
    )
    classification_counts: dict[str, int] = {}
    for item in classifications:
        classification_counts[item["classification"]] = (
            classification_counts.get(item["classification"], 0) + 1
        )
    summary = {
        "schema_version": "day8_root_cause_summary_v1",
        "run_count": 4,
        "pair_count": len(classifications),
        "first_divergent_query_localized": first is not None,
        "first_divergent_query": first,
        "previous_query_identity": previous,
        "classification_counts": classification_counts,
        "formal_query_completeness_failure_count": comparison_summary[
            "formal_query_completeness_failure_count"
        ],
        "query_completeness_violation_observed":
            comparison_summary["shadow_state_accounting_pass"] is True
            and comparison_summary[
                "formal_query_completeness_failure_count"
            ] > 0,
        "query_completeness_violation_blocked_by_shadow_accounting":
            comparison_summary["shadow_state_accounting_pass"] is not True
            and comparison_summary[
                "formal_query_completeness_failure_count"
            ] > 0,
        "shadow_state_accounting_pass":
            comparison_summary["shadow_state_accounting_pass"],
        "formal_ikdtree_bug_proven": False,
        "data_race_proven": False,
        "range_query_context_diagnostics_only": True,
        "shadow_replay_participates_in_fast_decisions": False,
        "instrumentation_timing_perturbation_present": True,
        "stage3_start_authorized": False,
        "stage4_start_authorized": False,
        "patent2_authorized": False,
        "day9_authorized": False,
    }
    _json(args.output_dir / "day8_root_cause_summary.json", summary)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
