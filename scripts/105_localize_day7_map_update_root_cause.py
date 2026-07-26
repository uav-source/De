#!/usr/bin/env python3
"""Select the earliest bounded Day 7 divergence and materialize root evidence."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def _json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        rows = [{"status": "NO_MAP_UPDATE_DIVERGENCE_REPRODUCED"}]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
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
            args.comparison_dir / "pairwise_day7_first_divergence.json"
        ).read_text(encoding="utf-8")
    )
    pairs = pair_doc["pairs"]
    divergent = [
        row for row in pairs
        if row["map_insertion_divergence_reproduced"]
    ]
    localized = [
        row for row in divergent
        if row["root_cause_classification"] not in {
            "EVIDENCE_GAP",
            "SAME_EVENT_TRACE_DIFFERENT_MAP_AFTER",
        }
    ]
    first = min(
        localized or divergent,
        key=lambda row: (
            row["scan_index"] if row["scan_index"] is not None else 10**9,
            row["run_pair"],
        ),
        default={
            "run_pair": None,
            "scan_index": None,
            "root_cause_classification":
                "NO_MAP_UPDATE_DIVERGENCE_REPRODUCED",
            "map_after_only_run_a": [],
            "map_after_only_run_b": [],
            "event_explains_symmetric_difference": False,
            "unexplained_map_point_identities": [],
        },
    )
    _json(
        args.output_dir / "first_divergent_map_mutation_event.json",
        {
            "schema_version": "first_divergent_map_mutation_event_v1",
            **first,
            "explanation": (
                "Earliest complete pairwise event difference in the fixed "
                "scan window; hashes only, no point coordinates."
                if first["scan_index"] is not None
                else "NO_MAP_UPDATE_DIVERGENCE_REPRODUCED"
            ),
        },
    )
    symmetric_rows = []
    for row in divergent:
        for side, values in (
            ("ONLY_RUN_A", row["map_after_only_run_a"]),
            ("ONLY_RUN_B", row["map_after_only_run_b"]),
        ):
            for point_hash in values:
                symmetric_rows.append({
                    "run_pair": row["run_pair"],
                    "scan_index": row["scan_index"],
                    "side": side,
                    "point_sha256": point_hash,
                    "event_backlink_pass":
                        point_hash not in row[
                            "unexplained_map_point_identities"
                        ],
                })
    _csv(
        args.output_dir / "map_after_symmetric_difference.csv",
        symmetric_rows,
    )
    delta_rows = []
    delta_failure_count = 0
    for run_dir in sorted(args.runtime_root.glob(
        "multihyp_day7_map_update_r*"
    )):
        summary = json.loads(
            (
                run_dir / "map_mutation_delta_accounting_summary.json"
            ).read_text(encoding="utf-8")
        )
        delta_failure_count += int(summary["failure_count"])
        delta_rows.append({
            "run_id": run_dir.name,
            "call_count": summary["call_count"],
            "failure_count": summary["failure_count"],
            "map_delta_accounting_pass":
                summary["map_delta_accounting_pass"],
        })
    _csv(
        args.output_dir / "map_mutation_delta_accounting.csv",
        delta_rows,
    )
    delta_summary = {
        "schema_version": "day7_cross_run_delta_accounting_v1",
        "run_count": len(delta_rows),
        "failure_count": delta_failure_count,
        "unexplained_map_count_delta_count": delta_failure_count,
        "map_delta_accounting_pass": delta_failure_count == 0,
    }
    _json(
        args.output_dir / "map_mutation_delta_accounting_summary.json",
        delta_summary,
    )
    previous_source = (
        args.comparison_dir / "first_divergent_event_previous_identity.csv"
    )
    (
        args.output_dir / "first_divergent_event_previous_identity.csv"
    ).write_bytes(previous_source.read_bytes())
    classifications = sorted({
        row["root_cause_classification"] for row in divergent
    })
    unexplained = sorted({
        value
        for row in divergent
        for value in row["unexplained_map_point_identities"]
    })
    summary = {
        "schema_version": "day7_map_update_root_cause_summary_v1",
        "map_insertion_divergence_reproduced": bool(divergent),
        "divergent_pair_count": len(divergent),
        "first_divergent_scan": first["scan_index"],
        "first_divergent_call": first.get("call_index"),
        "first_divergent_batch_kind": first.get("batch_kind"),
        "first_divergent_batch_point_index":
            first.get("batch_point_index"),
        "first_divergent_point_sha256":
            first.get("candidate_point_sha256"),
        "first_divergent_voxel": first.get("voxel_identity"),
        "root_cause_classifications": classifications,
        "multiple_map_update_divergence_modes":
            len(classifications) > 1,
        "first_divergent_map_mutation_event_localized":
            bool(localized),
        "map_after_delta_explained_pass":
            bool(divergent) and not unexplained,
        "unexplained_map_point_identity_count": len(unexplained),
        "map_delta_accounting_pass": delta_failure_count == 0,
        "map_update_root_cause_localized":
            bool(localized)
            and not unexplained
            and delta_failure_count == 0,
        "data_race_proven": False,
        "formal_ikdtree_bug_proven": False,
        "instrumentation_timing_perturbation_present": True,
    }
    _json(args.output_dir / "root_cause_summary.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
