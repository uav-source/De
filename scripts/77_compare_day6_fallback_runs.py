#!/usr/bin/env python3
"""Compare three Day 6 Fallback runs and align them to the frozen reference."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day6_fallback_functional_diagnostics import (  # noqa: E402
    Day6FallbackError,
    EXPECTED_RECORD_COUNT,
    SUB_RUN_IDS,
    write_json,
)
from fastlio2_adapter.day6_reference_alignment import (  # noqa: E402
    align_reference_run,
    load_csv,
    load_frozen_reference,
    load_jsonl,
    record_key,
)
from fastlio2_adapter.day6_statistical_characterization import (  # noqa: E402
    aligned_output_differences,
    run_level_summary,
    summarize_aligned_differences,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-1", required=True, type=Path)
    parser.add_argument("--run-2", required=True, type=Path)
    parser.add_argument("--run-3", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument(
        "--authorization-audit",
        type=Path,
        default=(
            Path.home()
            / "Degen-LIO-multihyp-D5-fallback-offline-detector-"
            "determinism-remediation-audit.tar.gz"
        ),
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise Day6FallbackError(f"cannot write empty CSV: {path.name}")
    fieldnames: list[str] = []
    for row in rows:
        for name in row:
            if name not in fieldnames:
                fieldnames.append(name)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def diagnostic_dir(run: Path) -> Path:
    candidate = run / "detector_diagnostics"
    return candidate if candidate.is_dir() else run


def load_run(run: Path) -> dict[str, Any]:
    diagnostics = diagnostic_dir(run)
    index = load_csv(run / "observation_record_index.csv")
    outputs = load_jsonl(diagnostics / "adapter_detector_outputs_v3.jsonl")
    if len(index) != EXPECTED_RECORD_COUNT or len(outputs) != EXPECTED_RECORD_COUNT:
        raise Day6FallbackError(f"run count mismatch: {run}")
    return {
        "root": run,
        "diagnostics": diagnostics,
        "index": index,
        "outputs": outputs,
        "output_bytes": (
            diagnostics / "adapter_detector_outputs_v3.jsonl"
        ).read_bytes(),
    }


def pair_rows(
    pair_name: str,
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    left_map = {record_key(row): row for row in left["outputs"]}
    right_map = {record_key(row): row for row in right["outputs"]}
    shared = sorted(set(left_map) & set(right_map))
    rows = [
        {
            "pair": pair_name,
            "scan_index": key[0],
            "timestamp_begin": repr(key[1]),
            "timestamp_end": repr(key[2]),
            **aligned_output_differences(left_map[key], right_map[key]),
        }
        for key in shared
    ]
    summary = {
        "pair": pair_name,
        "left_count": len(left_map),
        "right_count": len(right_map),
        "left_only_count": len(set(left_map) - set(right_map)),
        "right_only_count": len(set(right_map) - set(left_map)),
        **summarize_aligned_differences(rows),
    }
    summary["alignment_pass"] = (
        summary["aligned_record_count"] == EXPECTED_RECORD_COUNT
        and summary["left_only_count"] == 0
        and summary["right_only_count"] == 0
    )
    return rows, summary


def spread(values: list[float | None]) -> float | None:
    finite = [float(value) for value in values if value is not None]
    return max(finite) - min(finite) if finite else None


def main() -> int:
    args = parse_args()
    output = args.output_dir.expanduser().resolve()
    if output.exists():
        raise SystemExit(f"ERROR: output directory exists: {output}")
    runs = [
        load_run(path.expanduser().resolve())
        for path in (args.run_1, args.run_2, args.run_3)
    ]
    output.mkdir(parents=True, exist_ok=False)
    reference_index, reference_outputs, reference_manifest = (
        load_frozen_reference(
            args.reference.expanduser().resolve(),
            args.authorization_audit.expanduser().resolve(),
        )
    )

    reference_summaries: dict[str, Any] = {}
    for expected_id, run in zip(SUB_RUN_IDS, runs):
        rows, summary = align_reference_run(
            reference_index,
            reference_outputs,
            run["index"],
            run["outputs"],
        )
        write_csv(output / f"reference_alignment_{expected_id}.csv", rows)
        write_json(
            output / f"reference_alignment_summary_{expected_id}.json",
            summary,
        )
        reference_summaries[expected_id] = summary

    all_pair_rows: list[dict[str, Any]] = []
    pair_summaries: dict[str, Any] = {}
    for pair_name, left_index, right_index in (
        ("r1-r2", 0, 1),
        ("r1-r3", 0, 2),
        ("r2-r3", 1, 2),
    ):
        rows, summary = pair_rows(
            pair_name, runs[left_index], runs[right_index]
        )
        all_pair_rows.extend(rows)
        pair_summaries[pair_name] = summary
    write_csv(output / "cross_run_aligned_metrics.csv", all_pair_rows)

    run_levels = [
        run_level_summary(run_id, run["outputs"])
        for run_id, run in zip(SUB_RUN_IDS, runs)
    ]
    write_csv(output / "cross_run_run_level_summary.csv", run_levels)
    spread_summary: dict[str, Any] = {
        "valid_fraction_spread": spread(
            [row["valid_true_fraction"] for row in run_levels]
        )
    }
    for flag in (
        "primary_direction_stable",
        "degeneracy_triggered",
        "actionable_direction",
    ):
        spread_summary[f"{flag}_true_fraction_spread"] = spread(
            [row[f"{flag}_true_fraction"] for row in run_levels]
        )
    for metric in (
        "odi_trans",
        "ais_trans",
        "lambda_min_trans",
        "condition_number_trans",
        "primary_eigengap_ratio",
    ):
        spread_summary[f"{metric}_median_spread"] = spread(
            [row[f"{metric}_median"] for row in run_levels]
        )
    exact_equality = (
        runs[0]["output_bytes"]
        == runs[1]["output_bytes"]
        == runs[2]["output_bytes"]
    )
    summary = {
        "schema_version": "day6_cross_run_pairwise_summary_v1",
        "pairwise": pair_summaries,
        "run_level_spreads": spread_summary,
        "reference_alignment": reference_summaries,
        "frozen_reference_run_id": reference_manifest["run_id"],
        "CROSS_RUN_STATISTICAL_COMPARISON_COMPLETE": all(
            row["alignment_pass"] for row in pair_summaries.values()
        ),
        "REFERENCE_COMPARISON_COMPLETE": all(
            row["reference_alignment_pass"]
            for row in reference_summaries.values()
        ),
        "CROSS_RUN_EXACT_OUTPUT_EQUALITY_REQUIRED": False,
        "CROSS_RUN_EXACT_OUTPUT_EQUALITY_OBSERVED": exact_equality,
        "CROSS_RUN_BITWISE_EQUIVALENCE_CLAIMED": False,
        "hard_statistical_difference_threshold_applied": False,
        "descriptive_only": True,
    }
    if not summary["CROSS_RUN_STATISTICAL_COMPARISON_COMPLETE"]:
        raise Day6FallbackError("cross-run alignment is incomplete")
    if not summary["REFERENCE_COMPARISON_COMPLETE"]:
        raise Day6FallbackError("reference comparison is incomplete")
    write_json(output / "cross_run_pairwise_summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Day6FallbackError, OSError, KeyError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
