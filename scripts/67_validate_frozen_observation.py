#!/usr/bin/env python3
"""Validate compact export products or create one deterministic freeze view."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.frozen_observation import (  # noqa: E402
    FrozenObservationError,
    convert_frozen_set,
    load_existing_converter,
)


REQUIRED_RUNTIME_PRODUCTS = (
    "runtime_audit_v2.bin",
    "observation_records_v3.bin",
    "run_summary.json",
    "final_map_summary.json",
    "tap_export_summary.json",
)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def validate_runtime_products(
    run_dir: Path, converted_dir: Path
) -> dict[str, Any]:
    missing = [
        name for name in REQUIRED_RUNTIME_PRODUCTS if not (run_dir / name).is_file()
    ]
    if missing:
        raise FrozenObservationError(f"missing runtime products: {missing}")
    tap = json.loads(
        (run_dir / "tap_export_summary.json").read_text(encoding="utf-8")
    )
    if tap.get("runtime_mode") != "COMPACT_EXPORT":
        raise FrozenObservationError("runtime mode is not COMPACT_EXPORT")
    if tap.get("payload_profile") != "DETECTOR_MINIMAL_V1":
        raise FrozenObservationError("unexpected payload profile")
    if tap.get("tap_enabled") is not True:
        raise FrozenObservationError("read-only tap is disabled")
    converter = load_existing_converter()
    try:
        runtime_records, runtime_binary = converter.read_framed_binary(
            run_dir / "runtime_audit_v2.bin",
            magic=converter.RUNTIME_MAGIC,
            version=converter.RUNTIME_VERSION,
        )
        observation_records, observation_binary = converter.read_framed_binary(
            run_dir / "observation_records_v3.bin",
            magic=converter.OBSERVATION_MAGIC,
            version=converter.OBSERVATION_VERSION,
        )
        if converted_dir.exists():
            raise FrozenObservationError(
                f"transport conversion output exists: {converted_dir}"
            )
        conversion = converter.convert_files(
            run_dir / "runtime_audit_v2.bin",
            converted_dir,
            run_dir / "observation_records_v3.bin",
        )
    except converter.BinaryFormatError as error:
        raise FrozenObservationError(str(error)) from error
    summary = json.loads(
        (run_dir / "run_summary.json").read_text(encoding="utf-8")
    )
    runtime_count = int(summary.get("runtime_audit_record_count", -1))
    observation_count = int(tap.get("binary_observation_record_count", -1))
    capture_count = int(tap.get("capture_record_count", -1))
    if not (
        runtime_count == len(runtime_records)
        and observation_count == len(observation_records)
        and observation_count == capture_count
        and observation_count > 0
    ):
        raise FrozenObservationError("runtime/export record counts disagree")
    return {
        "runtime_product_pass": True,
        "required_runtime_product_count": len(REQUIRED_RUNTIME_PRODUCTS),
        "runtime_product_missing_count": 0,
        "runtime_binary_trailer_pass": bool(runtime_binary["trailer_valid"]),
        "runtime_binary_checksum_pass": bool(
            runtime_binary["file_checksum_valid"]
        ),
        "observation_binary_trailer_pass": bool(
            observation_binary["trailer_valid"]
        ),
        "observation_binary_checksum_pass": bool(
            observation_binary["file_checksum_valid"]
        ),
        "runtime_binary_record_count": len(runtime_records),
        "observation_record_count": len(observation_records),
        "capture_record_count": capture_count,
        "binary_checksum_failure_count": 0,
        "truncated_record_count": 0,
        "transport_conversion_record_count": conversion[
            "observation_record_count"
        ],
        "runtime_observation_export_enabled": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-products-only", action="store_true")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--converted-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--freeze-view", action="store_true")
    parser.add_argument("--endpoint-contract-sha256")
    parser.add_argument("--expected-run-id")
    parser.add_argument("--expected-sequence-id")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.converted_dir is None:
            raise FrozenObservationError("--converted-dir is required")
        if args.runtime_products_only:
            result = validate_runtime_products(
                args.run_dir.resolve(), args.converted_dir.resolve()
            )
        elif args.freeze_view:
            for name, value in (
                ("--endpoint-contract-sha256", args.endpoint_contract_sha256),
                ("--expected-run-id", args.expected_run_id),
                ("--expected-sequence-id", args.expected_sequence_id),
            ):
                if not value:
                    raise FrozenObservationError(f"{name} is required")
            result = convert_frozen_set(
                observation_binary=(
                    args.run_dir.resolve() / "observation_records_v3.bin"
                ),
                runtime_binary=args.run_dir.resolve() / "runtime_audit_v2.bin",
                output_dir=args.converted_dir.resolve(),
                endpoint_contract_sha256=str(args.endpoint_contract_sha256),
                expected_run_id=str(args.expected_run_id),
                expected_sequence_id=str(args.expected_sequence_id),
            )
        else:
            raise FrozenObservationError("one validation mode is required")
        if args.output is not None:
            write_json(args.output.resolve(), result)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, KeyError, ValueError, FrozenObservationError) as error:
        if args.output is not None:
            write_json(
                args.output.resolve(),
                {
                    "runtime_product_pass": False,
                    "failure_classification": "FROZEN_OBSERVATION_INVALID",
                    "message": str(error),
                },
            )
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
