#!/usr/bin/env python3
"""Evaluate real v3 records twice with the post-replay production detector."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.detector_output_schema import canonical_json_bytes
from fastlio2_adapter.runtime_observation_v3 import (
    validate_runtime_observation_v3,
)
from fastlio2_adapter.runtime_detector_adapter_v3 import (
    DETECTOR_EXECUTION_MODE,
    evaluate_runtime_observation_v3,
    validate_runtime_detector_output_v3,
)
from fastlio2_adapter.readonly_runtime_observation_schema import (
    validate_runtime_observation as validate_runtime_observation_v2,
)
from fastlio2_adapter.runtime_detector_adapter import (
    evaluate_runtime_observation as evaluate_runtime_observation_v2,
    validate_runtime_detector_output as validate_runtime_detector_output_v2,
)


def evaluate_file(input_path: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    valid_records: list[dict[str, Any]] = []
    invalid_records: list[dict[str, Any]] = []
    nonfinite_count = 0
    for line_number, line in enumerate(
        input_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        try:
            record = json.loads(line)
            _validate_observation(record)
            valid_records.append(record)
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            message = f"{type(error).__name__}: {error}"
            nonfinite_count += int("nonfinite" in message.lower())
            invalid_records.append(
                {
                    "line_number": line_number,
                    "input_line_sha256": hashlib.sha256(
                        line.encode("utf-8")
                    ).hexdigest(),
                    "error": message,
                }
            )

    outputs: list[list[dict[str, Any]]] = [[], []]
    runtimes_ns: list[float] = []
    detector_start = time.perf_counter_ns()
    for pass_index in range(2):
        for record in valid_records:
            start = time.perf_counter_ns()
            output = _evaluate_observation(record)
            elapsed = time.perf_counter_ns() - start
            _validate_output(output)
            outputs[pass_index].append(output)
            if pass_index == 0:
                runtimes_ns.append(float(elapsed))
    detector_total_runtime_ns = time.perf_counter_ns() - detector_start

    output_bytes = [
        b"".join(canonical_json_bytes(output) + b"\n" for output in pass_outputs)
        for pass_outputs in outputs
    ]
    checksums = [hashlib.sha256(value).hexdigest() for value in output_bytes]
    (output_dir / "detector_outputs_pass1.jsonl").write_bytes(output_bytes[0])
    (output_dir / "detector_outputs_pass2.jsonl").write_bytes(output_bytes[1])
    with (output_dir / "invalid_runtime_records.jsonl").open(
        "w", encoding="utf-8"
    ) as handle:
        for invalid in invalid_records:
            handle.write(
                json.dumps(invalid, sort_keys=True, separators=(",", ":")) + "\n"
            )

    first_outputs = outputs[0]
    valid_detector_outputs = [output for output in first_outputs if output["valid"]]
    odi = [float(output["odi_trans"]) for output in valid_detector_outputs]
    summary = {
        "detector_execution_mode": DETECTOR_EXECUTION_MODE,
        "record_count": len(valid_records) + len(invalid_records),
        "observation_record_count": len(valid_records),
        "valid_observation_record_count": len(valid_records),
        "invalid_observation_record_count": len(invalid_records),
        "schema_rejected_record_count": len(invalid_records),
        "nonfinite_count": nonfinite_count,
        "detector_output_count": len(first_outputs),
        "detector_output_missing_count": len(valid_records) - len(first_outputs),
        "detector_valid_count": len(valid_detector_outputs),
        "detector_invalid_count": sum(not output["valid"] for output in first_outputs),
        "degeneracy_trigger_count": sum(
            bool(output["degeneracy_triggered"]) for output in first_outputs
        ),
        "stable_direction_count": sum(
            bool(output["primary_direction_stable"]) for output in first_outputs
        ),
        "actionable_count": sum(
            bool(output["actionable_direction"]) for output in first_outputs
        ),
        "odi_min": min(odi) if odi else None,
        "odi_max": max(odi) if odi else None,
        "odi_median": statistics.median(odi) if odi else None,
        "runtime_mean_ns": statistics.fmean(runtimes_ns) if runtimes_ns else None,
        "runtime_q95_ns": _quantile(runtimes_ns, 0.95),
        "post_replay_detector_total_runtime_ns": detector_total_runtime_ns,
        "pass1_sha256": checksums[0],
        "pass2_sha256": checksums[1],
        "detector_repeat_checksum_mismatch_count": int(
            checksums[0] != checksums[1]
        ),
        "input_bag_read": False,
        "deferred_information_read": False,
        "fastlio2_modified": False,
    }
    (output_dir / "detector_runtime_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def _validate_observation(record: dict[str, Any]) -> None:
    if record.get("schema_version") == "readonly_observation_v3":
        validate_runtime_observation_v3(record)
    else:
        validate_runtime_observation_v2(record)


def _evaluate_observation(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("schema_version") == "readonly_observation_v3":
        return evaluate_runtime_observation_v3(record)
    return evaluate_runtime_observation_v2(record)


def _validate_output(record: dict[str, Any]) -> None:
    if record.get("schema_version") == "readonly_detector_output_v3":
        validate_runtime_detector_output_v3(record)
    else:
        validate_runtime_detector_output_v2(record)


def _quantile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Post-replay read-only production detector evaluation"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = evaluate_file(args.input, args.output_dir)
    print(json.dumps(summary, sort_keys=True))
    return int(
        summary["invalid_observation_record_count"] != 0
        or summary["detector_repeat_checksum_mismatch_count"] != 0
        or summary["detector_output_count"]
        != summary["valid_observation_record_count"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
