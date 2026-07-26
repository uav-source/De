#!/usr/bin/env python3
"""Compare adapter and direct streams from three remediation processes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_RECORD_COUNT = 487
STREAMS = {
    "adapter": {
        "jsonl": "adapter_detector_outputs_v3.jsonl",
        "sha": "adapter_detector_outputs_v3.jsonl.sha256",
        "output_checksum": "detector_output_checksum",
        "summary_sha": "adapter_jsonl_sha256",
    },
    "direct": {
        "jsonl": "direct_production_metrics_v1.jsonl",
        "sha": "direct_production_metrics_v1.jsonl.sha256",
        "output_checksum": "direct_output_checksum",
        "summary_sha": "direct_jsonl_sha256",
    },
}
PAIRS = (
    ("run_1_vs_run_2", 0, 1),
    ("run_1_vs_run_3", 0, 2),
    ("run_2_vs_run_3", 1, 2),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-1", required=True, type=Path)
    parser.add_argument("--run-2", required=True, type=Path)
    parser.add_argument("--run-3", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_stream(
    root: Path,
    stream_name: str,
) -> tuple[list[dict[str, Any]], list[bytes], str]:
    spec = STREAMS[stream_name]
    jsonl = root / spec["jsonl"]
    lines = jsonl.read_bytes().splitlines(keepends=True)
    records = [json.loads(line) for line in lines]
    actual_sha = hashlib.sha256(jsonl.read_bytes()).hexdigest()
    sidecar_sha = (root / spec["sha"]).read_text(encoding="utf-8").split()[0]
    summary = json.loads((root / "run_summary.json").read_text(encoding="utf-8"))
    if sidecar_sha != actual_sha or summary[spec["summary_sha"]] != actual_sha:
        raise ValueError(f"{stream_name} SHA mismatch: {root.name}")
    if len(records) != EXPECTED_RECORD_COUNT:
        raise ValueError(f"{stream_name} record count mismatch: {root.name}")
    if [record["record_index"] for record in records] != list(
        range(EXPECTED_RECORD_COUNT)
    ):
        raise ValueError(f"{stream_name} record index mismatch: {root.name}")
    return records, lines, actual_sha


def compare_stream(
    stream_name: str,
    loaded: list[tuple[list[dict[str, Any]], list[bytes], str]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    spec = STREAMS[stream_name]
    rows: list[dict[str, Any]] = []
    identity_mismatches = 0
    checksum_mismatches = 0
    line_mismatches = 0
    for record_index in range(EXPECTED_RECORD_COUNT):
        row: dict[str, Any] = {"record_index": record_index}
        for pair_name, left_index, right_index in PAIRS:
            left = loaded[left_index][0][record_index]
            right = loaded[right_index][0][record_index]
            identity_equal = all(
                left[field] == right[field]
                for field in (
                    "record_index",
                    "scan_index",
                    "timestamp_begin",
                    "timestamp_end",
                    "measurement_call_index",
                    "input_observation_checksum",
                    "detector_input_checksum",
                    "valid",
                    "invalid_reason",
                )
            )
            checksum_equal = (
                left[spec["output_checksum"]] == right[spec["output_checksum"]]
            )
            line_equal = (
                loaded[left_index][1][record_index]
                == loaded[right_index][1][record_index]
            )
            identity_mismatches += int(not identity_equal)
            checksum_mismatches += int(not checksum_equal)
            line_mismatches += int(not line_equal)
            row[f"{pair_name}_identity_equal"] = str(identity_equal).lower()
            row[f"{pair_name}_checksum_equal"] = str(checksum_equal).lower()
            row[f"{pair_name}_json_line_equal"] = str(line_equal).lower()
        rows.append(row)
    shas = [item[2] for item in loaded]
    whole_file_mismatches = sum(
        int(shas[left] != shas[right])
        for _, left, right in PAIRS
    )
    return rows, {
        "record_identity_mismatch_count": identity_mismatches,
        "record_checksum_mismatch_count": checksum_mismatches,
        "json_line_mismatch_count": line_mismatches,
        "whole_file_sha_mismatch_count": whole_file_mismatches,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    roots = [args.run_1.resolve(), args.run_2.resolve(), args.run_3.resolve()]
    output = args.output_dir.resolve()
    if output.exists():
        raise SystemExit(f"ERROR: comparison output exists: {output}")
    summaries = [
        json.loads((root / "run_summary.json").read_text(encoding="utf-8"))
        for root in roots
    ]
    environments = [
        json.loads((root / "environment_identity.json").read_text(encoding="utf-8"))
        for root in roots
    ]
    environment_mismatches = sum(
        int(environments[left] != environments[right])
        for _, left, right in PAIRS
    )

    adapter_loaded = [load_stream(root, "adapter") for root in roots]
    direct_loaded = [load_stream(root, "direct") for root in roots]
    adapter_rows, adapter_counts = compare_stream("adapter", adapter_loaded)
    direct_rows, direct_counts = compare_stream("direct", direct_loaded)

    output.mkdir(parents=True, exist_ok=False)
    write_csv(
        output / "adapter_cross_run_record_comparison.csv",
        adapter_rows,
    )
    write_csv(
        output / "direct_cross_run_record_comparison.csv",
        direct_rows,
    )
    summary = {
        "schema_version": "fallback_c_remediation_cross_run_summary_v1",
        "fresh_process_run_count": 3,
        "input_count_per_run": [
            item["input_record_count"] for item in summaries
        ],
        "adapter_output_count_per_run": [
            item["adapter_output_count"] for item in summaries
        ],
        "direct_output_count_per_run": [
            item["direct_output_count"] for item in summaries
        ],
        "adapter_valid_count_per_run": [
            item["adapter_valid_count"] for item in summaries
        ],
        "adapter_invalid_count_per_run": [
            item["adapter_invalid_count"] for item in summaries
        ],
        "direct_valid_count_per_run": [
            item["direct_valid_count"] for item in summaries
        ],
        "direct_invalid_count_per_run": [
            item["direct_invalid_count"] for item in summaries
        ],
        "adapter_jsonl_sha256_per_run": [
            item[2] for item in adapter_loaded
        ],
        "direct_jsonl_sha256_per_run": [
            item[2] for item in direct_loaded
        ],
        "adapter_record_identity_mismatch_count": adapter_counts[
            "record_identity_mismatch_count"
        ],
        "adapter_record_checksum_mismatch_count": adapter_counts[
            "record_checksum_mismatch_count"
        ],
        "adapter_json_line_mismatch_count": adapter_counts[
            "json_line_mismatch_count"
        ],
        "adapter_whole_file_sha_mismatch_count": adapter_counts[
            "whole_file_sha_mismatch_count"
        ],
        "direct_record_identity_mismatch_count": direct_counts[
            "record_identity_mismatch_count"
        ],
        "direct_record_checksum_mismatch_count": direct_counts[
            "record_checksum_mismatch_count"
        ],
        "direct_json_line_mismatch_count": direct_counts[
            "json_line_mismatch_count"
        ],
        "direct_whole_file_sha_mismatch_count": direct_counts[
            "whole_file_sha_mismatch_count"
        ],
        "environment_identity_mismatch_count": environment_mismatches,
    }
    summary["adapter_three_process_determinism_pass"] = all(
        summary[name] == 0
        for name in (
            "adapter_record_identity_mismatch_count",
            "adapter_record_checksum_mismatch_count",
            "adapter_json_line_mismatch_count",
            "adapter_whole_file_sha_mismatch_count",
        )
    )
    summary["direct_three_process_determinism_pass"] = all(
        summary[name] == 0
        for name in (
            "direct_record_identity_mismatch_count",
            "direct_record_checksum_mismatch_count",
            "direct_json_line_mismatch_count",
            "direct_whole_file_sha_mismatch_count",
        )
    )
    write_json(output / "cross_run_summary.json", summary)
    if not (
        summary["adapter_three_process_determinism_pass"]
        and summary["direct_three_process_determinism_pass"]
        and environment_mismatches == 0
    ):
        raise SystemExit("ERROR: remediation fresh-process outputs differ")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
