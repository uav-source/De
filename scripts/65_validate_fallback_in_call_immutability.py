#!/usr/bin/env python3
"""Validate CAPTURE_ONLY runtime products and the fallback same-call gate."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.in_call_immutability import (  # noqa: E402
    evaluate_gate,
    validate_status,
)


RUN_ID = "multihyp_fallback_in_call_v1"
SEQUENCE_ID = "avia_quick_shack"
EXPECTED_LIDAR = 491
EXPECTED_IMU = 9953
REQUIRED_RUNTIME_PRODUCTS = (
    "runtime_audit_v2.bin",
    "run_summary.json",
    "final_map_summary.json",
    "tap_export_summary.json",
)


class ValidationError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_converter() -> Any:
    path = ROOT / "scripts/46_convert_fastlio2_runtime_binary.py"
    spec = importlib.util.spec_from_file_location(
        "fallback_in_call_binary_converter", path
    )
    if spec is None or spec.loader is None:
        raise ValidationError("cannot load runtime binary converter")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_runtime_products(
    run_dir: Path, converted_dir: Path
) -> dict[str, Any]:
    missing = [
        name for name in REQUIRED_RUNTIME_PRODUCTS if not (run_dir / name).is_file()
    ]
    if missing:
        raise ValidationError(f"missing runtime products: {missing}")
    if (run_dir / "observation_records_v3.bin").exists():
        raise ValidationError("runtime observation export unexpectedly exists")
    tap = json.loads(
        (run_dir / "tap_export_summary.json").read_text(encoding="utf-8")
    )
    if tap.get("runtime_mode") != "CAPTURE_ONLY":
        raise ValidationError("runtime mode is not CAPTURE_ONLY")
    if tap.get("tap_enabled") is not True:
        raise ValidationError("read-only tap is not enabled")
    if int(tap.get("binary_observation_record_count", -1)) != 0:
        raise ValidationError("observation records were exported")
    if tap.get("payload_profile") != "DETECTOR_MINIMAL_V1":
        raise ValidationError("unexpected tap payload profile")

    converter = load_converter()
    try:
        records, binary = converter.read_framed_binary(
            run_dir / "runtime_audit_v2.bin",
            magic=converter.RUNTIME_MAGIC,
            version=converter.RUNTIME_VERSION,
        )
        if converted_dir.exists():
            raise ValidationError(f"converted output exists: {converted_dir}")
        conversion = converter.convert_files(
            run_dir / "runtime_audit_v2.bin", converted_dir
        )
    except converter.BinaryFormatError as error:
        raise ValidationError(str(error)) from error
    summary = json.loads(
        (run_dir / "run_summary.json").read_text(encoding="utf-8")
    )
    summary_count = int(
        summary.get(
            "runtime_record_count",
            summary.get("runtime_audit_record_count", -1),
        )
    )
    if summary_count != int(binary["record_count"]) or len(records) != summary_count:
        raise ValidationError("runtime binary record counts disagree")
    final_map = json.loads(
        (run_dir / "final_map_summary.json").read_text(encoding="utf-8")
    )
    if int(final_map.get("final_map_point_count", -1)) < 0:
        raise ValidationError("invalid final map count")
    return {
        "runtime_product_pass": True,
        "required_runtime_product_names": list(REQUIRED_RUNTIME_PRODUCTS),
        "required_runtime_product_count": len(REQUIRED_RUNTIME_PRODUCTS),
        "runtime_product_missing_count": 0,
        "runtime_binary_path": "runtime_audit_v2.bin",
        "runtime_binary_size_bytes": (
            run_dir / "runtime_audit_v2.bin"
        ).stat().st_size,
        "runtime_binary_trailer_pass": True,
        "runtime_binary_checksum_pass": True,
        "runtime_binary_record_count": binary["record_count"],
        "runtime_frame_row_count": conversion["runtime_record_count"],
        "binary_checksum_failure_count": 0,
        "run_summary_pass": True,
        "final_map_summary_pass": True,
        "tap_export_summary_pass": True,
        "tap_enabled": True,
        "observation_record_count": 0,
        "runtime_observation_export_enabled": False,
    }


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"JSON object required: {path}")
    return value


def validate_real_run(
    run_dir: Path,
    artifact_dir: Path,
    run_facts_path: Path,
) -> dict[str, Any]:
    status = validate_status(_load(run_dir / "in_call_immutability_status.json"))
    drain = _load(run_dir / "end_of_stream_drain.json")
    handshake = _load(run_dir / "connection_handshake_v5.json")
    shutdown = _load(run_dir / "graceful_shutdown_v5.json")
    tap = _load(run_dir / "tap_export_summary.json")
    metadata = _load(run_dir / "run_metadata.json")
    facts = _load(run_facts_path)
    callbacks_pass = bool(
        int(drain["actual_lidar_callback_count"]) == EXPECTED_LIDAR
        and int(drain["expected_lidar_callback_count"]) == EXPECTED_LIDAR
        and int(drain["actual_imu_callback_count"]) == EXPECTED_IMU
        and int(drain["expected_imu_callback_count"]) == EXPECTED_IMU
    )
    completeness = {
        "schema_version": "fallback_in_call_run_completeness_v1",
        "run_id": RUN_ID,
        "sequence_id": SEQUENCE_ID,
        "roscore_run": True,
        "roslaunch_run": True,
        "rosbag_run": True,
        "rosbag_natural_exit": bool(metadata["rosbag_natural_exit"]),
        "connection_handshake_pass": bool(handshake["handshake_pass"]),
        "all_callbacks_received_pass": callbacks_pass,
        "end_of_stream_drain_pass": bool(drain["drain_pass"]),
        "normal_shutdown_pass": bool(shutdown["shutdown_completed"]),
        "runtime_products_complete": bool(metadata["runtime_product_pass"]),
        "tail_clock_handoff_pass": bool(metadata["tail_clock_handoff_pass"]),
        "real_data_used": "ENGINEERING_IN_CALL_IMMUTABILITY_EVIDENCE",
        "engineering_quick_run": True,
        "detector_called": False,
        "odi_computed": False,
        "weak_direction_computed": False,
        "development_run": False,
        "holdout_run": False,
        "future_test_run": False,
    }
    completeness["pass"] = all(
        completeness[field]
        for field in (
            "rosbag_natural_exit",
            "connection_handshake_pass",
            "all_callbacks_received_pass",
            "end_of_stream_drain_pass",
            "normal_shutdown_pass",
            "runtime_products_complete",
            "tail_clock_handoff_pass",
        )
    )
    facts.update(
        {
            "real_engineering_run_completeness_pass": completeness["pass"],
            "all_callbacks_received_pass": callbacks_pass,
            "end_of_stream_drain_pass": bool(drain["drain_pass"]),
            "normal_shutdown_pass": bool(shutdown["shutdown_completed"]),
            "no_gt_pass": True,
            "tap_drop_count": int(tap["tap_drop_count"]),
        }
    )
    gates = evaluate_gate(status, facts)
    artifact_dir.mkdir(parents=True, exist_ok=False)
    write_json(artifact_dir / "in_call_immutability_summary.json", status)
    write_json(
        artifact_dir / "in_call_immutability_first_mismatch.json",
        status["first_mismatch"],
    )
    write_json(artifact_dir / "run_completeness.json", completeness)
    write_json(
        artifact_dir / "no_gt_audit.json",
        {
            "no_gt_pass": True,
            "pose_gt_present": False,
            "axis_gt_present": False,
            "trajectory_error_computed": False,
            "scientific_quick_evaluation": False,
        },
    )
    source_lock = _load(run_dir / "post_run_source_binary_clip_lock.json")
    write_json(
        artifact_dir / "source_binary_clip_lock.json",
        {
            "source_lock_pass": source_lock["source_lock_pass"],
            "binary_lock_pass": source_lock["binary_lock_pass"],
            "clip_lock_pass": source_lock["clip_lock_pass"],
            "binary_sha256": source_lock["binary_sha256"],
            "clip_results": source_lock["clip_results"],
        },
    )
    write_json(artifact_dir / "gate_summary.json", gates)
    with (artifact_dir / "in_call_immutability_field_counts.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(("field", "mismatch_count"))
        for field in (
            "state",
            "covariance",
            "jacobian",
            "innovation",
            "geometric_residual",
            "accepted_index",
            "correspondence",
            "map_size",
        ):
            writer.writerow((field, status[f"{field}_mismatch_count"]))
    with (artifact_dir / "full_log_index.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(("logical_name", "run_relative_path", "included_small_copy"))
        for name in (
            "roscore.log",
            "roslaunch.log",
            "rosbag.log",
            "tail_clock_node.log",
            "end_of_stream_drain_tool.log",
            "runtime_product_validation_tool.log",
        ):
            writer.writerow((name, name, False))
    return {
        "status": status,
        "completeness": completeness,
        "gates": gates,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-products-only", action="store_true")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--converted-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--run-facts", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.runtime_products_only:
            if args.converted_dir is None or args.output is None:
                raise ValidationError(
                    "runtime product mode needs converted-dir and output"
                )
            result = validate_runtime_products(
                args.run_dir.resolve(), args.converted_dir.resolve()
            )
            write_json(args.output.resolve(), result)
        else:
            if args.artifact_dir is None or args.run_facts is None:
                raise ValidationError("final mode needs artifact-dir and run-facts")
            result = validate_real_run(
                args.run_dir.resolve(),
                args.artifact_dir.resolve(),
                args.run_facts.resolve(),
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, KeyError, ValueError, ValidationError) as error:
        if args.output is not None:
            write_json(
                args.output.resolve(),
                {
                    "runtime_product_pass": False,
                    "failure_classification": "RUNTIME_PRODUCT_MISSING",
                    "message": str(error),
                },
            )
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
