#!/usr/bin/env python3
"""Compare three immutable fresh-process detector output directories."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_RECORD_COUNT = 487


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-1", required=True, type=Path)
    parser.add_argument("--run-2", required=True, type=Path)
    parser.add_argument("--run-3", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def load_run(root: Path) -> tuple[list[dict[str, Any]], list[bytes], dict[str, Any]]:
    jsonl = root / "detector_outputs_v3.jsonl"
    raw_lines = jsonl.read_bytes().splitlines(keepends=True)
    records = [json.loads(line) for line in raw_lines]
    summary = json.loads((root / "run_summary.json").read_text(encoding="utf-8"))
    expected_sha = (root / "detector_outputs_v3.jsonl.sha256").read_text(
        encoding="utf-8"
    ).split()[0]
    actual_sha = hashlib.sha256(jsonl.read_bytes()).hexdigest()
    if expected_sha != actual_sha or summary["detector_outputs_jsonl_sha256"] != actual_sha:
        raise ValueError(f"run JSONL SHA mismatch: {root.name}")
    if len(records) != EXPECTED_RECORD_COUNT:
        raise ValueError(f"run record count mismatch: {root.name}")
    if [record["record_index"] for record in records] != list(
        range(EXPECTED_RECORD_COUNT)
    ):
        raise ValueError(f"run record index is not contiguous: {root.name}")
    return records, raw_lines, summary


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    output = args.output_dir.resolve()
    if output.exists():
        raise SystemExit(f"ERROR: comparison output exists: {output}")
    roots = [args.run_1.resolve(), args.run_2.resolve(), args.run_3.resolve()]
    loaded = [load_run(root) for root in roots]
    output.mkdir(parents=True, exist_ok=False)

    rows: list[dict[str, Any]] = []
    checksum_mismatches = 0
    line_mismatches = 0
    identity_mismatches = 0
    pair_names = ("run_1_vs_run_2", "run_1_vs_run_3", "run_2_vs_run_3")
    pairs = ((0, 1), (0, 2), (1, 2))
    for record_index in range(EXPECTED_RECORD_COUNT):
        row: dict[str, Any] = {"record_index": record_index}
        for pair_name, (left_index, right_index) in zip(pair_names, pairs):
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
                    "valid",
                    "invalid_reason",
                )
            )
            checksum_equal = (
                left["detector_output_checksum"]
                == right["detector_output_checksum"]
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

    jsonl_shas = [
        item[2]["detector_outputs_jsonl_sha256"] for item in loaded
    ]
    whole_file_sha_mismatch_count = 0 if len(set(jsonl_shas)) == 1 else 1
    environment_equal = loaded[0][0] and all(
        json.loads((root / "environment_identity.json").read_text(encoding="utf-8"))
        == json.loads(
            (roots[0] / "environment_identity.json").read_text(encoding="utf-8")
        )
        for root in roots[1:]
    )
    summary = {
        "schema_version": "fallback_detector_cross_run_summary_v1",
        "fresh_process_run_count": 3,
        "record_count_per_run": [
            item[2]["detector_output_count"] for item in loaded
        ],
        "valid_count_per_run": [item[2]["valid_count"] for item in loaded],
        "invalid_count_per_run": [item[2]["invalid_count"] for item in loaded],
        "nonfinite_count_per_run": [
            item[2]["nonfinite_output_count"] for item in loaded
        ],
        "jsonl_sha256_per_run": jsonl_shas,
        "environment_identity_equal": bool(environment_equal),
        "record_identity_mismatch_count": identity_mismatches,
        "record_checksum_mismatch_count": checksum_mismatches,
        "json_line_mismatch_count": line_mismatches,
        "whole_file_sha_mismatch_count": whole_file_sha_mismatch_count,
        "per_record_checksum_determinism_pass": checksum_mismatches == 0,
        "canonical_json_byte_determinism_pass": line_mismatches == 0,
        "whole_file_sha_determinism_pass": whole_file_sha_mismatch_count == 0,
    }
    with (output / "cross_run_record_comparison.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_json(output / "cross_run_summary.json", summary)
    if not (
        summary["environment_identity_equal"]
        and summary["record_identity_mismatch_count"] == 0
        and summary["record_checksum_mismatch_count"] == 0
        and summary["json_line_mismatch_count"] == 0
        and summary["whole_file_sha_mismatch_count"] == 0
    ):
        raise SystemExit("ERROR: fresh-process detector outputs differ")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
