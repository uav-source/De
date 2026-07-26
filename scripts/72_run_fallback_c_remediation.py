#!/usr/bin/env python3
"""Run one fresh-process Fallback C remediation pass over frozen observations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import tarfile
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.canonical_detector_output import (  # noqa: E402
    CANONICAL_JSON_SPEC_VERSION,
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
from fastlio2_adapter.direct_production_diagnostic import (  # noqa: E402
    SCHEMA_PATH as DIRECT_SCHEMA_PATH,
    evaluate_direct_production,
    validate_direct_production_output,
)
from fastlio2_adapter.offline_detector_determinism import (  # noqa: E402
    EXPECTED_CORE_BINARY_SHA256,
    EXPECTED_FROZEN_ARCHIVE_SHA256,
    EXPECTED_RECORD_COUNT,
    detector_identity,
    evaluate_frozen_observation,
    file_sha256,
    input_component_identity,
    load_frozen_records,
    tree_sha256,
)


RUN_IDS = frozenset(
    {
        "fresh_process_remediation_run_1",
        "fresh_process_remediation_run_2",
        "fresh_process_remediation_run_3",
    }
)
EXPECTED_ADAPTER_JSONL_SHA256 = (
    "182b989aee619d83862cb45e9aef6fb0a50dd5b91d407e8d5ef13d694fd65232"
)
EXPECTED_ENVIRONMENT = {
    "PYTHONHASHSEED": "0",
    "OMP_NUM_THREADS": "1",
    "OMP_DYNAMIC": "FALSE",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "LC_ALL": "C",
    "LANG": "C",
    "TZ": "UTC",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-observation", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path.name}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def safe_extract(archive: Path, destination: Path) -> Path:
    with tarfile.open(archive, "r:gz") as handle:
        roots: set[str] = set()
        members = handle.getmembers()
        for member in members:
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("unsafe frozen archive path")
            if member.issym() or member.islnk():
                raise ValueError("frozen archive must not contain links")
            if path.parts:
                roots.add(path.parts[0])
        if len(roots) != 1:
            raise ValueError("frozen archive must contain one root")
        handle.extractall(destination)
    root = destination / next(iter(roots))
    if not root.is_dir():
        raise ValueError("frozen archive root missing")
    return root


def environment_identity() -> dict[str, Any]:
    actual = {name: os.environ.get(name) for name in EXPECTED_ENVIRONMENT}
    if actual != EXPECTED_ENVIRONMENT:
        raise ValueError(f"fresh-process environment mismatch: {actual}")
    blas = {
        name: np.__config__.get_info(name)
        for name in (
            "openblas64__info",
            "blas_ilp64_opt_info",
            "openblas64__lapack_info",
            "lapack_ilp64_opt_info",
        )
        if np.__config__.get_info(name)
    }
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "blas_identity": blas,
        "platform": platform.platform(),
        "environment_variables": actual,
    }


def _identity_row(
    *,
    record_index: int,
    scan_index: int,
    before: dict[str, Any],
    after_adapter: dict[str, Any],
    after_direct: dict[str, Any],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "record_index": record_index,
        "scan_index": scan_index,
    }
    names = (
        "input_observation_checksum",
        "detector_pose_jacobian_rows_checksum",
        "formal_filter_innovation_h_checksum",
        "prior_covariance_checksum",
        "measurement_variance_scalar_m2",
        "valid_correspondence_count",
    )
    for name in names:
        row[f"{name}_before"] = before[name]
        row[f"{name}_after_adapter"] = after_adapter[name]
        row[f"{name}_after_direct"] = after_direct[name]
    row["adapter_input_unchanged"] = str(before == after_adapter).lower()
    row["direct_input_unchanged"] = str(before == after_direct).lower()
    row["total_input_unchanged"] = str(
        before == after_adapter == after_direct
    ).lower()
    return row


def _adapter_checksum_row(
    output: dict[str, Any],
    line: bytes,
) -> dict[str, Any]:
    return {
        "record_index": output["record_index"],
        "scan_index": output["scan_index"],
        "timestamp_begin": repr(output["timestamp_begin"]),
        "timestamp_end": repr(output["timestamp_end"]),
        "input_observation_checksum": output["input_observation_checksum"],
        "detector_input_checksum": output["detector_input_checksum"],
        "adapter_output_checksum": output["detector_output_checksum"],
        "canonical_json_line_sha256": hashlib.sha256(line).hexdigest(),
    }


def _direct_checksum_row(
    output: dict[str, Any],
    line: bytes,
) -> dict[str, Any]:
    return {
        "record_index": output["record_index"],
        "scan_index": output["scan_index"],
        "timestamp_begin": repr(output["timestamp_begin"]),
        "timestamp_end": repr(output["timestamp_end"]),
        "input_observation_checksum": output["input_observation_checksum"],
        "detector_input_checksum": output["detector_input_checksum"],
        "direct_output_checksum": output["direct_output_checksum"],
        "canonical_json_line_sha256": hashlib.sha256(line).hexdigest(),
    }


def _equivalence_row(
    adapter_output: dict[str, Any],
    direct_output: dict[str, Any],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    rows = int(direct_output["jacobian_row_count"])
    columns = int(direct_output["jacobian_column_count"])
    metric_pass = comparison["metric_equivalence_pass"]
    precondition_pass = comparison["precondition_contract_pass"]
    return {
        "record_index": adapter_output["record_index"],
        "scan_index": adapter_output["scan_index"],
        "jacobian_row_count": rows,
        "jacobian_column_count": columns,
        "equivalence_domain": comparison["equivalence_domain"],
        "adapter_valid": str(adapter_output["valid"]).lower(),
        "adapter_invalid_reason": adapter_output["invalid_reason"],
        "direct_valid": str(direct_output["valid"]).lower(),
        "direct_invalid_reason": direct_output["invalid_reason"],
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
        "adapter_output_checksum": adapter_output["detector_output_checksum"],
        "direct_output_checksum": direct_output["direct_output_checksum"],
    }


def main() -> int:
    args = parse_args()
    if args.run_id not in RUN_IDS:
        raise SystemExit("ERROR: unexpected remediation run id")
    archive = args.frozen_observation.resolve()
    output = args.output_dir.resolve()
    if output.exists():
        raise SystemExit(f"ERROR: output directory exists: {output}")
    if file_sha256(archive) != EXPECTED_FROZEN_ARCHIVE_SHA256:
        raise SystemExit("ERROR: frozen observation archive SHA mismatch")

    environment = environment_identity()
    source = detector_identity(ROOT)
    source.update(
        {
            "detector_artifact_tree_sha256": tree_sha256(
                ROOT / "artifacts/current/detector_stage2a"
            ),
            "observation_schema_path_alias": (
                "schemas/harmful_bias/readonly_observation_v3.schema.json"
            ),
            "detector_output_schema_path_alias": (
                "schemas/harmful_bias/readonly_detector_output_v3.schema.json"
            ),
            "direct_output_schema_path_alias": (
                "schemas/harmful_bias/"
                "offline_direct_production_metrics_v1.schema.json"
            ),
            "direct_output_schema_sha256": file_sha256(DIRECT_SCHEMA_PATH),
            "adapter_guard_path_alias": (
                "src/fastlio2_adapter/detector_adapter.py"
            ),
            "adapter_guard_sha256": file_sha256(
                ROOT / "src/fastlio2_adapter/detector_adapter.py"
            ),
            "runtime_adapter_path_alias": (
                "src/fastlio2_adapter/runtime_detector_adapter_v3.py"
            ),
            "runtime_adapter_sha256": file_sha256(
                ROOT / "src/fastlio2_adapter/runtime_detector_adapter_v3.py"
            ),
            "canonical_output_path_alias": (
                "src/fastlio2_adapter/canonical_detector_output.py"
            ),
            "canonical_output_sha256": file_sha256(
                ROOT / "src/fastlio2_adapter/canonical_detector_output.py"
            ),
            "adapter_precondition_policy": (
                "ROWS_LESS_THAN_COLUMNS_RETURNS_TOO_FEW_CORRESPONDENCES"
            ),
        }
    )

    output.mkdir(parents=True, exist_ok=False)
    archive_sha_before = file_sha256(archive)
    with tempfile.TemporaryDirectory(
        prefix=f"degen_fallback_c_remediation_{args.run_id}_"
    ) as temporary:
        frozen_root = safe_extract(archive, Path(temporary))
        records, frozen_identity = load_frozen_records(frozen_root)
        binary = frozen_root / "binary/observation_records_v3.bin"
        binary_sha_before = file_sha256(binary)
        if binary_sha_before != EXPECTED_CORE_BINARY_SHA256:
            raise ValueError("frozen core binary SHA mismatch")

        adapter_lines: list[bytes] = []
        direct_lines: list[bytes] = []
        adapter_checksum_rows: list[dict[str, Any]] = []
        direct_checksum_rows: list[dict[str, Any]] = []
        immutability_rows: list[dict[str, Any]] = []
        equivalence_rows: list[dict[str, Any]] = []
        adapter_invalid_reasons: Counter[str] = Counter()
        direct_invalid_reasons: Counter[str] = Counter()
        adapter_valid_count = 0
        direct_valid_count = 0
        adapter_schema_rejected_count = 0
        direct_schema_rejected_count = 0
        adapter_input_mutation_count = 0
        direct_input_mutation_count = 0
        total_input_mutation_count = 0
        detector_exception_count = 0
        direct_production_exception_count = 0
        forbidden_count = 0
        production_domain_count = 0
        precondition_domain_count = 0
        precondition_indexes: list[int] = []
        precondition_scan_indexes: list[int] = []
        production_metric_required_count = 0
        production_metric_pass_count = 0
        production_metric_mismatch_count = 0
        production_metric_max_error = 0.0
        precondition_contract_pass_count = 0
        precondition_contract_mismatch_count = 0

        for record_index, record in enumerate(records):
            before = input_component_identity(record)
            try:
                adapter_output = evaluate_frozen_observation(
                    record,
                    record_index=record_index,
                )
            except Exception:
                detector_exception_count += 1
                raise
            after_adapter = input_component_identity(record)
            try:
                direct_output = evaluate_direct_production(
                    record,
                    record_index=record_index,
                )
            except Exception:
                direct_production_exception_count += 1
                raise
            after_direct = input_component_identity(record)

            adapter_changed = before != after_adapter
            direct_changed = before != after_direct
            total_changed = before != after_adapter or before != after_direct
            adapter_input_mutation_count += int(adapter_changed)
            direct_input_mutation_count += int(direct_changed)
            total_input_mutation_count += int(total_changed)
            immutability_rows.append(
                _identity_row(
                    record_index=record_index,
                    scan_index=int(record["scan_index"]),
                    before=before,
                    after_adapter=after_adapter,
                    after_direct=after_direct,
                )
            )

            try:
                validate_canonical_detector_output(adapter_output)
            except Exception:
                adapter_schema_rejected_count += 1
                raise
            try:
                validate_direct_production_output(direct_output)
            except Exception:
                direct_schema_rejected_count += 1
                raise

            adapter_forbidden = forbidden_field_paths(adapter_output)
            direct_forbidden = forbidden_field_paths(direct_output)
            forbidden_count += len(adapter_forbidden) + len(direct_forbidden)
            if adapter_forbidden or direct_forbidden:
                raise ValueError(
                    "forbidden output fields: "
                    f"{adapter_forbidden + direct_forbidden}"
                )

            adapter_line = canonical_json_line(adapter_output)
            direct_line = canonical_json_line(direct_output)
            adapter_lines.append(adapter_line)
            direct_lines.append(direct_line)
            adapter_checksum_rows.append(
                _adapter_checksum_row(adapter_output, adapter_line)
            )
            direct_checksum_rows.append(
                _direct_checksum_row(direct_output, direct_line)
            )
            adapter_valid_count += int(adapter_output["valid"])
            direct_valid_count += int(direct_output["valid"])
            adapter_invalid_reasons[adapter_output["invalid_reason"]] += 1
            direct_invalid_reasons[direct_output["invalid_reason"]] += 1
            direct_production_exception_count += int(
                direct_output["invalid_reason"] == "PRODUCTION_DETECTOR_EXCEPTION"
            )

            comparison = compare_contract_record(
                record,
                adapter_output,
                direct_output,
                tolerance=COMPARISON_TOLERANCE,
            )
            equivalence_rows.append(
                _equivalence_row(adapter_output, direct_output, comparison)
            )
            if comparison["equivalence_domain"] == PRODUCTION_EXECUTED_DOMAIN:
                production_domain_count += 1
                production_metric_required_count += 1
                metric_pass = comparison["metric_equivalence_pass"] is True
                production_metric_pass_count += int(metric_pass)
                production_metric_mismatch_count += int(not metric_pass)
                production_metric_max_error = max(
                    production_metric_max_error,
                    float(comparison["max_abs_error"]),
                )
            elif comparison["equivalence_domain"] == ADAPTER_PRECONDITION_DOMAIN:
                precondition_domain_count += 1
                precondition_indexes.append(record_index)
                precondition_scan_indexes.append(int(record["scan_index"]))
                contract_pass = comparison["precondition_contract_pass"] is True
                precondition_contract_pass_count += int(contract_pass)
                precondition_contract_mismatch_count += int(not contract_pass)
            else:
                raise ValueError("unexpected equivalence domain")

        if len(adapter_lines) != EXPECTED_RECORD_COUNT:
            raise ValueError("adapter output count is not 487")
        if len(direct_lines) != EXPECTED_RECORD_COUNT:
            raise ValueError("direct output count is not 487")

        adapter_jsonl = output / "adapter_detector_outputs_v3.jsonl"
        adapter_jsonl.write_bytes(b"".join(adapter_lines))
        adapter_sha = file_sha256(adapter_jsonl)
        (output / "adapter_detector_outputs_v3.jsonl.sha256").write_text(
            f"{adapter_sha}  adapter_detector_outputs_v3.jsonl\n",
            encoding="utf-8",
        )
        if adapter_sha != EXPECTED_ADAPTER_JSONL_SHA256:
            raise ValueError(
                "adapter output backward-compatibility SHA mismatch: "
                f"{adapter_sha}"
            )

        direct_jsonl = output / "direct_production_metrics_v1.jsonl"
        direct_jsonl.write_bytes(b"".join(direct_lines))
        direct_sha = file_sha256(direct_jsonl)
        (output / "direct_production_metrics_v1.jsonl.sha256").write_text(
            f"{direct_sha}  direct_production_metrics_v1.jsonl\n",
            encoding="utf-8",
        )
        write_csv(
            output / "adapter_record_output_checksums.csv",
            adapter_checksum_rows,
        )
        write_csv(
            output / "direct_record_output_checksums.csv",
            direct_checksum_rows,
        )
        write_csv(output / "record_input_immutability.csv", immutability_rows)

        domain_summary = {
            "schema_version": "direct_equivalence_domain_summary_v1",
            "total_record_count": EXPECTED_RECORD_COUNT,
            "production_executed_domain_record_count": production_domain_count,
            "adapter_precondition_domain_record_count": precondition_domain_count,
            "adapter_precondition_record_indexes": precondition_indexes,
            "adapter_precondition_scan_indexes": precondition_scan_indexes,
            "production_metric_equivalence_required_count": (
                production_metric_required_count
            ),
            "production_metric_equivalence_pass_count": (
                production_metric_pass_count
            ),
            "production_metric_equivalence_mismatch_count": (
                production_metric_mismatch_count
            ),
            "production_metric_equivalence_max_abs_error": (
                production_metric_max_error
            ),
            "adapter_precondition_contract_pass_count": (
                precondition_contract_pass_count
            ),
            "adapter_precondition_contract_mismatch_count": (
                precondition_contract_mismatch_count
            ),
            "direct_production_diagnostic_record_count": len(direct_lines),
            "direct_production_exception_count": (
                direct_production_exception_count
            ),
        }
        if args.run_id == "fresh_process_remediation_run_1":
            write_csv(
                output / "contract_aware_direct_equivalence.csv",
                equivalence_rows,
            )
            write_json(
                output / "direct_equivalence_domain_summary.json",
                domain_summary,
            )

        adapter_invalid_count = EXPECTED_RECORD_COUNT - adapter_valid_count
        direct_invalid_count = EXPECTED_RECORD_COUNT - direct_valid_count
        adapter_schema_summary = {
            "schema_version": "fallback_c_adapter_schema_summary_v1",
            "reused_schema_path_alias": (
                "schemas/harmful_bias/readonly_detector_output_v3.schema.json"
            ),
            "reused_schema_sha256": source["output_schema_sha256"],
            "schema_accepted_output_count": EXPECTED_RECORD_COUNT,
            "schema_rejected_output_count": adapter_schema_rejected_count,
            "forbidden_field_count": forbidden_count,
            "output_schema_pass": (
                adapter_schema_rejected_count == 0 and forbidden_count == 0
            ),
        }
        direct_schema_summary = {
            "schema_version": "fallback_c_direct_schema_summary_v1",
            "schema_path_alias": source["direct_output_schema_path_alias"],
            "schema_sha256": source["direct_output_schema_sha256"],
            "schema_accepted_output_count": EXPECTED_RECORD_COUNT,
            "schema_rejected_output_count": direct_schema_rejected_count,
            "forbidden_field_count": forbidden_count,
            "output_schema_pass": (
                direct_schema_rejected_count == 0 and forbidden_count == 0
            ),
        }
        write_json(
            output / "adapter_output_schema_summary.json",
            adapter_schema_summary,
        )
        write_json(
            output / "direct_output_schema_summary.json",
            direct_schema_summary,
        )
        write_json(
            output / "adapter_invalid_reason_summary.json",
            {
                "schema_version": "fallback_c_adapter_invalid_reason_summary_v1",
                "valid_count": adapter_valid_count,
                "invalid_count": adapter_invalid_count,
                "invalid_reason_counts": dict(
                    sorted(adapter_invalid_reasons.items())
                ),
            },
        )
        write_json(
            output / "direct_invalid_reason_summary.json",
            {
                "schema_version": "fallback_c_direct_invalid_reason_summary_v1",
                "valid_count": direct_valid_count,
                "invalid_count": direct_invalid_count,
                "invalid_reason_counts": dict(
                    sorted(direct_invalid_reasons.items())
                ),
            },
        )
        no_gt = {
            "schema_version": "fallback_c_no_gt_output_audit_v1",
            "scanned_adapter_output_count": EXPECTED_RECORD_COUNT,
            "scanned_direct_output_count": EXPECTED_RECORD_COUNT,
            "forbidden_field_count": forbidden_count,
            "gt_topic_consumed_count": 0,
            "no_gt_pass": forbidden_count == 0,
        }
        write_json(output / "no_gt_output_audit.json", no_gt)

        binary_sha_after = file_sha256(binary)
        archive_sha_after = file_sha256(archive)
        if binary_sha_after != binary_sha_before:
            raise ValueError("extracted frozen binary changed during run")
        if archive_sha_after != archive_sha_before:
            raise ValueError("frozen observation archive changed during run")

        summary = {
            "schema_version": "fallback_c_remediation_run_summary_v1",
            "fresh_process_run_id": args.run_id,
            "canonical_json_spec_version": CANONICAL_JSON_SPEC_VERSION,
            "frozen_archive_sha256_before": archive_sha_before,
            "frozen_archive_sha256_after": archive_sha_after,
            "core_binary_sha256_before": binary_sha_before,
            "core_binary_sha256_after": binary_sha_after,
            "input_record_count": len(records),
            "adapter_output_count": len(adapter_lines),
            "direct_output_count": len(direct_lines),
            "adapter_valid_count": adapter_valid_count,
            "adapter_invalid_count": adapter_invalid_count,
            "adapter_too_few_correspondence_count": int(
                adapter_invalid_reasons["TOO_FEW_CORRESPONDENCES"]
            ),
            "direct_valid_count": direct_valid_count,
            "direct_invalid_count": direct_invalid_count,
            "missing_output_count": 0,
            "duplicate_output_count": 0,
            "adapter_schema_rejected_count": adapter_schema_rejected_count,
            "direct_schema_rejected_count": direct_schema_rejected_count,
            "detector_exception_count": detector_exception_count,
            "direct_production_exception_count": direct_production_exception_count,
            "adapter_input_mutation_count": adapter_input_mutation_count,
            "direct_input_mutation_count": direct_input_mutation_count,
            "total_input_mutation_count": total_input_mutation_count,
            "forbidden_field_count": forbidden_count,
            "adapter_jsonl_sha256": adapter_sha,
            "direct_jsonl_sha256": direct_sha,
            "adapter_output_backward_compatibility_pass": (
                adapter_sha == EXPECTED_ADAPTER_JSONL_SHA256
            ),
            **domain_summary,
            "detector_called": True,
            "odi_computed": True,
            "weak_direction_computed": True,
            "detector_residual_used": False,
            "prior_covariance_used_by_detector": False,
            "real_observation_artifact_used": True,
        }
        write_json(output / "run_summary.json", summary)
        write_json(output / "source_identity.json", source)
        write_json(output / "environment_identity.json", environment)
        write_json(
            output / "frozen_input_identity.json",
            {
                "frozen_archive_sha256": archive_sha_before,
                "core_binary_sha256": binary_sha_before,
                "record_index_sha256": frozen_identity["record_index_sha256"],
                "observation_schema_sha256": frozen_identity[
                    "observation_schema_sha256"
                ],
                "input_record_count": frozen_identity["input_record_count"],
                "internal_hash_failure_count": frozen_identity[
                    "internal_hash_verification"
                ]["hash_failure_count"],
                "schema_rejected_record_count": frozen_identity[
                    "schema_rejected_record_count"
                ],
                "gt_topic_consumed_count": frozen_identity[
                    "gt_topic_consumed_count"
                ],
            },
        )

    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, tarfile.TarError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
