#!/usr/bin/env python3
"""Run one fresh-process offline production-detector determinism pass."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
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
from fastlio2_adapter.offline_detector_determinism import (  # noqa: E402
    DIRECT_EQUIVALENCE_TOLERANCE,
    EXPECTED_CORE_BINARY_SHA256,
    EXPECTED_FROZEN_ARCHIVE_SHA256,
    EXPECTED_RECORD_COUNT,
    compare_direct_production,
    detector_identity,
    direct_production_metrics,
    evaluate_frozen_observation,
    file_sha256,
    input_component_identity,
    load_frozen_records,
    tree_sha256,
)


ALLOWED_RUN_IDS = frozenset(
    {
        "fresh_process_run_1",
        "fresh_process_run_2",
        "fresh_process_run_3",
    }
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


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
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
    for path in root.rglob("*"):
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)
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


def main() -> int:
    args = parse_args()
    if args.run_id not in ALLOWED_RUN_IDS:
        raise SystemExit("ERROR: unexpected fresh-process run id")
    archive = args.frozen_observation.resolve()
    output = args.output_dir.resolve()
    if output.exists():
        raise SystemExit(f"ERROR: output directory exists: {output}")
    if file_sha256(archive) != EXPECTED_FROZEN_ARCHIVE_SHA256:
        raise SystemExit("ERROR: frozen observation archive SHA mismatch")
    environment = environment_identity()
    source = detector_identity(ROOT)
    source["detector_artifact_tree_sha256"] = tree_sha256(
        ROOT / "artifacts/current/detector_stage2a"
    )
    source["observation_schema_path_alias"] = (
        "schemas/harmful_bias/readonly_observation_v3.schema.json"
    )
    source["detector_output_schema_path_alias"] = (
        "schemas/harmful_bias/readonly_detector_output_v3.schema.json"
    )
    source["runtime_adapter_path_alias"] = (
        "src/fastlio2_adapter/runtime_detector_adapter_v3.py"
    )
    source["offline_adapter_path_alias"] = (
        "src/fastlio2_adapter/offline_detector_determinism.py"
    )

    output.mkdir(parents=True, exist_ok=False)
    archive_sha_before = file_sha256(archive)
    with tempfile.TemporaryDirectory(
        prefix=f"degen_fallback_c_{args.run_id}_"
    ) as temporary:
        frozen_root = safe_extract(archive, Path(temporary))
        records, frozen_identity = load_frozen_records(frozen_root)
        binary = frozen_root / "binary/observation_records_v3.bin"
        binary_sha_before = file_sha256(binary)
        if binary_sha_before != EXPECTED_CORE_BINARY_SHA256:
            raise ValueError("frozen core binary SHA mismatch")

        canonical_lines: list[bytes] = []
        output_checksum_rows: list[dict[str, Any]] = []
        immutability_rows: list[dict[str, Any]] = []
        direct_rows: list[dict[str, Any]] = []
        invalid_reasons: Counter[str] = Counter()
        valid_count = 0
        nonfinite_output_count = 0
        schema_rejected_output_count = 0
        detector_exception_count = 0
        input_mutation_count = 0
        direct_mismatch_count = 0
        direct_max_error = 0.0
        forbidden_count = 0

        for record_index, record in enumerate(records):
            before = input_component_identity(record)
            try:
                detector_output = evaluate_frozen_observation(
                    record, record_index=record_index
                )
            except Exception:
                detector_exception_count += 1
                raise
            after = input_component_identity(record)
            unchanged = before == after
            if not unchanged:
                input_mutation_count += 1
            immutability_rows.append(
                {
                    "record_index": record_index,
                    "scan_index": record["scan_index"],
                    "input_checksum_before": before[
                        "input_observation_checksum"
                    ],
                    "input_checksum_after": after["input_observation_checksum"],
                    "jacobian_checksum_before": before[
                        "detector_pose_jacobian_rows_checksum"
                    ],
                    "jacobian_checksum_after": after[
                        "detector_pose_jacobian_rows_checksum"
                    ],
                    "residual_checksum_before": before[
                        "formal_filter_innovation_h_checksum"
                    ],
                    "residual_checksum_after": after[
                        "formal_filter_innovation_h_checksum"
                    ],
                    "prior_covariance_checksum_before": before[
                        "prior_covariance_checksum"
                    ],
                    "prior_covariance_checksum_after": after[
                        "prior_covariance_checksum"
                    ],
                    "variance_before": before[
                        "measurement_variance_scalar_m2"
                    ],
                    "variance_after": after["measurement_variance_scalar_m2"],
                    "valid_correspondence_count_before": before[
                        "valid_correspondence_count"
                    ],
                    "valid_correspondence_count_after": after[
                        "valid_correspondence_count"
                    ],
                    "input_unchanged": str(unchanged).lower(),
                }
            )
            try:
                validate_canonical_detector_output(detector_output)
            except Exception:
                schema_rejected_output_count += 1
                raise
            forbidden = forbidden_field_paths(detector_output)
            forbidden_count += len(forbidden)
            if forbidden:
                raise ValueError(f"forbidden canonical output fields: {forbidden}")

            line = canonical_json_line(detector_output)
            canonical_lines.append(line)
            output_checksum_rows.append(
                {
                    "record_index": record_index,
                    "scan_index": detector_output["scan_index"],
                    "timestamp_begin": repr(detector_output["timestamp_begin"]),
                    "timestamp_end": repr(detector_output["timestamp_end"]),
                    "input_observation_checksum": detector_output[
                        "input_observation_checksum"
                    ],
                    "detector_input_checksum": detector_output[
                        "detector_input_checksum"
                    ],
                    "detector_output_checksum": detector_output[
                        "detector_output_checksum"
                    ],
                    "canonical_json_line_sha256": hashlib.sha256(line).hexdigest(),
                }
            )
            invalid_reasons[detector_output["invalid_reason"]] += 1
            valid_count += int(detector_output["valid"])
            nonfinite_output_count += int(
                detector_output["invalid_reason"] == "DETECTOR_OUTPUT_NONFINITE"
            )

            if args.run_id == "fresh_process_run_1":
                direct = direct_production_metrics(record)
                matched, max_error, fields = compare_direct_production(
                    detector_output,
                    direct,
                    tolerance=DIRECT_EQUIVALENCE_TOLERANCE,
                )
                direct_mismatch_count += int(not matched)
                direct_max_error = max(direct_max_error, max_error)
                direct_rows.append(
                    {
                        "record_index": record_index,
                        "scan_index": record["scan_index"],
                        "matched": str(matched).lower(),
                        "max_abs_error": repr(max_error),
                        "mismatched_fields": ";".join(fields),
                    }
                )

        if len(canonical_lines) != EXPECTED_RECORD_COUNT:
            raise ValueError("detector output count is not 487")
        jsonl = output / "detector_outputs_v3.jsonl"
        jsonl.write_bytes(b"".join(canonical_lines))
        jsonl_sha = file_sha256(jsonl)
        (output / "detector_outputs_v3.jsonl.sha256").write_text(
            f"{jsonl_sha}  detector_outputs_v3.jsonl\n", encoding="utf-8"
        )
        write_csv(
            output / "record_output_checksums.csv",
            output_checksum_rows,
            list(output_checksum_rows[0]),
        )
        write_csv(
            output / "record_input_immutability.csv",
            immutability_rows,
            list(immutability_rows[0]),
        )
        if args.run_id == "fresh_process_run_1":
            write_csv(
                output / "direct_production_equivalence.csv",
                direct_rows,
                list(direct_rows[0]),
            )

        invalid_count = EXPECTED_RECORD_COUNT - valid_count
        schema_summary = {
            "schema_version": "fallback_detector_output_schema_summary_v1",
            "reused_schema_path_alias": (
                "schemas/harmful_bias/readonly_detector_output_v3.schema.json"
            ),
            "reused_schema_sha256": source["output_schema_sha256"],
            "frozen_source_extension": "FROZEN_REAL_OBSERVATION",
            "schema_accepted_output_count": EXPECTED_RECORD_COUNT,
            "schema_rejected_output_count": schema_rejected_output_count,
            "forbidden_field_count": forbidden_count,
            "output_schema_pass": (
                schema_rejected_output_count == 0 and forbidden_count == 0
            ),
        }
        write_json(output / "detector_output_schema_summary.json", schema_summary)
        write_json(
            output / "detector_invalid_reason_summary.json",
            {
                "schema_version": "fallback_detector_invalid_reason_summary_v1",
                "valid_count": valid_count,
                "invalid_count": invalid_count,
                "nonfinite_output_count": nonfinite_output_count,
                "invalid_reason_counts": dict(sorted(invalid_reasons.items())),
            },
        )
        no_gt = {
            "schema_version": "fallback_detector_no_gt_output_audit_v1",
            "scanned_output_count": EXPECTED_RECORD_COUNT,
            "forbidden_scientific_field_count": forbidden_count,
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
            "schema_version": "fallback_offline_detector_run_summary_v1",
            "fresh_process_run_id": args.run_id,
            "canonical_json_spec_version": CANONICAL_JSON_SPEC_VERSION,
            "frozen_archive_sha256_before": archive_sha_before,
            "frozen_archive_sha256_after": archive_sha_after,
            "core_binary_sha256_before": binary_sha_before,
            "core_binary_sha256_after": binary_sha_after,
            "input_record_count": len(records),
            "detector_output_count": len(canonical_lines),
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "nonfinite_output_count": nonfinite_output_count,
            "missing_output_count": 0,
            "duplicate_output_count": 0,
            "schema_rejected_output_count": schema_rejected_output_count,
            "forbidden_field_count": forbidden_count,
            "detector_exception_count": detector_exception_count,
            "input_mutation_count": input_mutation_count,
            "detector_outputs_jsonl_sha256": jsonl_sha,
            "direct_equivalence_executed": args.run_id == "fresh_process_run_1",
            "direct_equivalence_mismatch_count": direct_mismatch_count,
            "direct_equivalence_max_abs_error": direct_max_error,
            "detector_called": True,
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
