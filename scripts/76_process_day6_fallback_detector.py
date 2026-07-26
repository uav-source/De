#!/usr/bin/env python3
"""Process one Day 6 compact observation stream with shadow detectors."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.canonical_detector_output import (  # noqa: E402
    canonical_json_line,
    forbidden_field_paths,
    validate_canonical_detector_output,
)
from fastlio2_adapter.contract_aware_direct_comparison import (  # noqa: E402
    ADAPTER_PRECONDITION_DOMAIN,
    COMPARISON_TOLERANCE,
    NOT_APPLICABLE,
    PRODUCTION_EXECUTED_DOMAIN,
    compare_contract_record,
)
from fastlio2_adapter.day6_continuity_metrics import (  # noqa: E402
    direction_continuity,
    flag_continuity,
    output_continuity,
)
from fastlio2_adapter.day6_fallback_functional_diagnostics import (  # noqa: E402
    Day6FallbackError,
    EXPECTED_RECORD_COUNT,
    detector_identity,
    load_observation_binary,
    validate_environment_lock,
    validate_record_index,
    write_json,
)
from fastlio2_adapter.day6_statistical_characterization import (  # noqa: E402
    detector_metric_statistics,
    latency_statistics,
)
from fastlio2_adapter.direct_production_diagnostic import (  # noqa: E402
    evaluate_direct_production,
    validate_direct_production_output,
)
from fastlio2_adapter.offline_detector_determinism import (  # noqa: E402
    evaluate_frozen_observation,
    input_component_identity,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation-binary", required=True, type=Path)
    parser.add_argument("--record-index", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise Day6FallbackError(f"cannot write empty CSV: {path.name}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def checksum_row(
    output: Mapping[str, Any], line: bytes, checksum_field: str
) -> dict[str, Any]:
    return {
        "record_index": output["record_index"],
        "scan_index": output["scan_index"],
        "timestamp_begin": repr(output["timestamp_begin"]),
        "timestamp_end": repr(output["timestamp_end"]),
        "input_observation_checksum": output["input_observation_checksum"],
        "detector_input_checksum": output["detector_input_checksum"],
        checksum_field: output[checksum_field],
        "canonical_json_line_sha256": hashlib.sha256(line).hexdigest(),
    }


def immutability_row(
    *,
    record_index: int,
    scan_index: int,
    before: Mapping[str, Any],
    after_adapter: Mapping[str, Any],
    after_direct: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "record_index": record_index,
        "scan_index": scan_index,
        "input_observation_checksum_before": before[
            "input_observation_checksum"
        ],
        "input_observation_checksum_after_adapter": after_adapter[
            "input_observation_checksum"
        ],
        "input_observation_checksum_after_direct": after_direct[
            "input_observation_checksum"
        ],
        "adapter_input_unchanged": str(before == after_adapter).lower(),
        "direct_input_unchanged": str(before == after_direct).lower(),
        "total_input_unchanged": str(
            before == after_adapter == after_direct
        ).lower(),
    }


def equivalence_row(
    adapter: Mapping[str, Any],
    direct: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> dict[str, Any]:
    metric_pass = comparison["metric_equivalence_pass"]
    precondition_pass = comparison["precondition_contract_pass"]
    return {
        "record_index": adapter["record_index"],
        "scan_index": adapter["scan_index"],
        "jacobian_row_count": direct["jacobian_row_count"],
        "jacobian_column_count": direct["jacobian_column_count"],
        "equivalence_domain": comparison["equivalence_domain"],
        "adapter_valid": str(adapter["valid"]).lower(),
        "adapter_invalid_reason": adapter["invalid_reason"],
        "direct_valid": str(direct["valid"]).lower(),
        "direct_invalid_reason": direct["invalid_reason"],
        "metric_comparison_required": str(
            comparison["metric_comparison_required"]
        ).lower(),
        "metric_equivalence_pass": (
            metric_pass
            if metric_pass == NOT_APPLICABLE
            else str(metric_pass).lower()
        ),
        "max_abs_error": repr(float(comparison["max_abs_error"])),
        "mismatched_fields": ";".join(comparison["mismatched_fields"]),
        "mismatch_types": ";".join(comparison["mismatch_types"]),
        "precondition_contract_pass": (
            precondition_pass
            if precondition_pass == NOT_APPLICABLE
            else str(precondition_pass).lower()
        ),
    }


def main() -> int:
    args = parse_args()
    output = args.output_dir.expanduser().resolve()
    if output.exists():
        raise SystemExit(f"ERROR: output directory exists: {output}")
    observation_binary = args.observation_binary.expanduser().resolve()
    index_path = args.record_index.expanduser().resolve()
    environment = validate_environment_lock()
    source = detector_identity(ROOT)
    records, integrity = load_observation_binary(observation_binary)
    index_rows = read_csv(index_path)
    index_summary = validate_record_index(index_rows, records)
    output.mkdir(parents=True, exist_ok=False)

    adapter_outputs: list[dict[str, Any]] = []
    direct_outputs: list[dict[str, Any]] = []
    adapter_lines: list[bytes] = []
    direct_lines: list[bytes] = []
    adapter_checksums: list[dict[str, Any]] = []
    direct_checksums: list[dict[str, Any]] = []
    immutability_rows: list[dict[str, Any]] = []
    equivalence_rows: list[dict[str, Any]] = []
    latency_rows: list[dict[str, Any]] = []
    adapter_reasons: Counter[str] = Counter()
    direct_reasons: Counter[str] = Counter()
    adapter_schema_rejected = 0
    direct_schema_rejected = 0
    forbidden_count = 0
    detector_exception_count = 0
    direct_exception_count = 0
    input_mutation_count = 0
    production_domain_count = 0
    precondition_domain_count = 0
    production_metric_mismatch_count = 0
    precondition_contract_mismatch_count = 0
    production_metric_max_error = 0.0

    for record_index, record in enumerate(records):
        before = input_component_identity(record)
        adapter_started = time.perf_counter_ns()
        try:
            adapter = evaluate_frozen_observation(
                record, record_index=record_index
            )
        except Exception:
            detector_exception_count += 1
            raise
        adapter_latency = time.perf_counter_ns() - adapter_started
        after_adapter = input_component_identity(record)

        direct_started = time.perf_counter_ns()
        try:
            direct = evaluate_direct_production(
                record, record_index=record_index
            )
        except Exception:
            direct_exception_count += 1
            raise
        direct_latency = time.perf_counter_ns() - direct_started
        after_direct = input_component_identity(record)

        mutated = not (before == after_adapter == after_direct)
        input_mutation_count += int(mutated)
        immutability_rows.append(
            immutability_row(
                record_index=record_index,
                scan_index=int(record["scan_index"]),
                before=before,
                after_adapter=after_adapter,
                after_direct=after_direct,
            )
        )
        try:
            validate_canonical_detector_output(adapter)
        except Exception:
            adapter_schema_rejected += 1
            raise
        try:
            validate_direct_production_output(direct)
        except Exception:
            direct_schema_rejected += 1
            raise
        forbidden = forbidden_field_paths(adapter) + forbidden_field_paths(direct)
        forbidden_count += len(forbidden)
        if forbidden:
            raise Day6FallbackError(f"forbidden detector output fields: {forbidden}")

        adapter_line = canonical_json_line(adapter)
        direct_line = canonical_json_line(direct)
        adapter_outputs.append(adapter)
        direct_outputs.append(direct)
        adapter_lines.append(adapter_line)
        direct_lines.append(direct_line)
        adapter_checksums.append(
            checksum_row(adapter, adapter_line, "detector_output_checksum")
        )
        direct_checksums.append(
            checksum_row(direct, direct_line, "direct_output_checksum")
        )
        adapter_reasons[str(adapter["invalid_reason"])] += 1
        direct_reasons[str(direct["invalid_reason"])] += 1
        comparison = compare_contract_record(
            record,
            adapter,
            direct,
            tolerance=COMPARISON_TOLERANCE,
        )
        equivalence_rows.append(
            equivalence_row(adapter, direct, comparison)
        )
        domain = comparison["equivalence_domain"]
        if domain == PRODUCTION_EXECUTED_DOMAIN:
            production_domain_count += 1
            passed = comparison["metric_equivalence_pass"] is True
            production_metric_mismatch_count += int(not passed)
            production_metric_max_error = max(
                production_metric_max_error,
                float(comparison["max_abs_error"]),
            )
        elif domain == ADAPTER_PRECONDITION_DOMAIN:
            precondition_domain_count += 1
            precondition_contract_mismatch_count += int(
                comparison["precondition_contract_pass"] is not True
            )
        else:
            raise Day6FallbackError(f"unexpected equivalence domain: {domain}")
        latency_rows.append(
            {
                "record_index": record_index,
                "scan_index": int(record["scan_index"]),
                "domain": domain,
                "adapter_total_call_latency_ns": adapter_latency,
                "direct_production_call_latency_ns": direct_latency,
            }
        )

    adapter_jsonl = output / "adapter_detector_outputs_v3.jsonl"
    direct_jsonl = output / "direct_production_metrics_v1.jsonl"
    adapter_jsonl.write_bytes(b"".join(adapter_lines))
    direct_jsonl.write_bytes(b"".join(direct_lines))
    adapter_sha = hashlib.sha256(adapter_jsonl.read_bytes()).hexdigest()
    direct_sha = hashlib.sha256(direct_jsonl.read_bytes()).hexdigest()
    (output / "adapter_detector_outputs_v3.jsonl.sha256").write_text(
        f"{adapter_sha}  adapter_detector_outputs_v3.jsonl\n",
        encoding="utf-8",
    )
    (output / "direct_production_metrics_v1.jsonl.sha256").write_text(
        f"{direct_sha}  direct_production_metrics_v1.jsonl\n",
        encoding="utf-8",
    )
    write_csv(output / "adapter_record_output_checksums.csv", adapter_checksums)
    write_csv(output / "direct_record_output_checksums.csv", direct_checksums)
    write_csv(output / "record_input_immutability.csv", immutability_rows)
    write_csv(
        output / "contract_aware_direct_equivalence.csv", equivalence_rows
    )
    write_csv(output / "detector_latency_records.csv", latency_rows)

    continuity = output_continuity(records, adapter_outputs)
    direction_rows, direction_summary = direction_continuity(adapter_outputs)
    flag_rows, flag_summary = flag_continuity(adapter_outputs)
    metric_rows, metric_summary = detector_metric_statistics(adapter_outputs)
    latency_summary = latency_statistics(latency_rows)
    write_json(output / "output_continuity_summary.json", continuity)
    write_csv(output / "direction_continuity_records.csv", direction_rows)
    write_json(
        output / "direction_continuity_summary.json", direction_summary
    )
    write_csv(output / "detector_flag_timeline.csv", flag_rows)
    write_json(
        output / "detector_flag_transition_summary.json", flag_summary
    )
    write_csv(
        output / "detector_metric_descriptive_statistics.csv", metric_rows
    )
    write_json(
        output / "detector_metric_descriptive_statistics.json", metric_summary
    )
    write_json(output / "detector_latency_summary.json", latency_summary)

    adapter_valid = sum(bool(row["valid"]) for row in adapter_outputs)
    direct_valid = sum(bool(row["valid"]) for row in direct_outputs)
    adapter_schema_summary = {
        "schema_version": "day6_adapter_output_schema_summary_v1",
        "schema_accepted_output_count": len(adapter_outputs),
        "schema_rejected_output_count": adapter_schema_rejected,
        "forbidden_field_count": forbidden_count,
        "output_schema_pass": (
            adapter_schema_rejected == 0 and forbidden_count == 0
        ),
    }
    direct_schema_summary = {
        "schema_version": "day6_direct_output_schema_summary_v1",
        "schema_accepted_output_count": len(direct_outputs),
        "schema_rejected_output_count": direct_schema_rejected,
        "forbidden_field_count": forbidden_count,
        "output_schema_pass": (
            direct_schema_rejected == 0 and forbidden_count == 0
        ),
    }
    write_json(
        output / "adapter_output_schema_summary.json", adapter_schema_summary
    )
    write_json(
        output / "direct_output_schema_summary.json", direct_schema_summary
    )
    write_json(
        output / "adapter_invalid_reason_summary.json",
        {
            "valid_count": adapter_valid,
            "invalid_count": len(adapter_outputs) - adapter_valid,
            "invalid_reason_counts": dict(sorted(adapter_reasons.items())),
        },
    )
    write_json(
        output / "direct_invalid_reason_summary.json",
        {
            "valid_count": direct_valid,
            "invalid_count": len(direct_outputs) - direct_valid,
            "invalid_reason_counts": dict(sorted(direct_reasons.items())),
        },
    )
    domain_summary = {
        "schema_version": "day6_direct_equivalence_domain_summary_v1",
        "total_record_count": len(records),
        "production_executed_domain_record_count": production_domain_count,
        "adapter_precondition_domain_record_count": precondition_domain_count,
        "production_metric_equivalence_mismatch_count": (
            production_metric_mismatch_count
        ),
        "production_metric_equivalence_max_abs_error": (
            production_metric_max_error
        ),
        "adapter_precondition_contract_mismatch_count": (
            precondition_contract_mismatch_count
        ),
    }
    write_json(
        output / "direct_equivalence_domain_summary.json", domain_summary
    )
    no_gt = {
        "schema_version": "day6_detector_no_gt_audit_v1",
        "scanned_adapter_output_count": len(adapter_outputs),
        "scanned_direct_output_count": len(direct_outputs),
        "forbidden_field_count": forbidden_count,
        "gt_topic_consumed_count": 0,
        "no_gt_pass": forbidden_count == 0,
    }
    write_json(output / "detector_no_gt_audit.json", no_gt)
    summary = {
        "schema_version": "day6_detector_processing_summary_v1",
        "run_id": records[0]["run_id"],
        "input_record_count": len(records),
        "adapter_output_count": len(adapter_outputs),
        "direct_output_count": len(direct_outputs),
        "adapter_valid_count": adapter_valid,
        "adapter_invalid_count": len(adapter_outputs) - adapter_valid,
        "direct_valid_count": direct_valid,
        "direct_invalid_count": len(direct_outputs) - direct_valid,
        "missing_output_count": 0,
        "duplicate_output_count": 0,
        "detector_exception_count": detector_exception_count,
        "direct_production_exception_count": direct_exception_count,
        "adapter_schema_rejected_count": adapter_schema_rejected,
        "direct_schema_rejected_count": direct_schema_rejected,
        "input_mutation_count": input_mutation_count,
        "forbidden_field_count": forbidden_count,
        "adapter_jsonl_sha256": adapter_sha,
        "direct_jsonl_sha256": direct_sha,
        "binary_integrity": integrity,
        "record_index_validation": index_summary,
        **domain_summary,
        "timestamp_backward_count": continuity["timestamp_backward_count"],
        "duplicate_scan_index_count": continuity[
            "duplicate_scan_index_count"
        ],
        "post_replay_detector_processing_pass": (
            len(adapter_outputs) == EXPECTED_RECORD_COUNT
            and len(direct_outputs) == EXPECTED_RECORD_COUNT
            and detector_exception_count == 0
            and direct_exception_count == 0
            and adapter_schema_rejected == 0
            and direct_schema_rejected == 0
            and input_mutation_count == 0
            and production_metric_mismatch_count == 0
            and precondition_contract_mismatch_count == 0
            and continuity["output_continuity_diagnostics_pass"]
        ),
        "detector_called": True,
        "detector_called_inside_fastlio2": False,
        "detector_feedback_enabled": False,
        "odi_computed": True,
        "weak_direction_computed": True,
        "scientific_effectiveness_evaluated": False,
        "harmful_bias_detectability_evaluated": False,
    }
    write_json(output / "detector_processing_summary.json", summary)
    write_json(output / "environment_identity.json", environment)
    write_json(output / "source_identity.json", source)
    if not summary["post_replay_detector_processing_pass"]:
        raise Day6FallbackError(f"detector processing gate failed: {summary}")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Day6FallbackError, OSError, KeyError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
