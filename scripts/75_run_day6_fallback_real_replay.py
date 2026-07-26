#!/usr/bin/env python3
"""Run one authorized Day 6 Fallback Quick Shack compact-export replay."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day6_fallback_functional_diagnostics import (  # noqa: E402
    Day6FallbackError,
    EXPECTED_CLIP_SHA256,
    EXPECTED_IMU_CALLBACK_COUNT,
    EXPECTED_LIDAR_CALLBACK_COUNT,
    EXPECTED_RECORD_COUNT,
    EXPECTED_TAIL_ADJUDICATION_RULE_SHA256,
    MAIN_RUN_ID,
    SEQUENCE_ID,
    SUB_RUN_IDS,
    sha256_file,
    validate_authorization_archive,
    write_json,
)
from fastlio2_adapter.frozen_observation import (  # noqa: E402
    FrozenObservationError,
    convert_frozen_set,
)
from fastlio2_adapter.in_call_immutability import validate_status  # noqa: E402


FAST_RUNTIME_MODE = "COMPACT_EXPORT"
PAYLOAD_PROFILE = "DETECTOR_MINIMAL_V1"
IN_CALL_STATUS_SERVICE = "/harmful_bias/in_call_immutability_status"
TAP_BUFFER_CAPACITY = 1024
EXPECTED_RAW_FAILURES = {
    "NONE",
    "TAIL_CLOCK_STOP_FAILURE",
    "TAIL_CLOCK_DUPLICATE_TIME",
}
PROCESS_PATTERNS = (
    ("roscore", ("pgrep", "-x", "roscore")),
    ("roslaunch", ("pgrep", "-x", "roslaunch")),
    ("laser_mapping", ("pgrep", "-f", "[f]astlio_mapping")),
    ("rosbag_play", ("pgrep", "-f", "[r]osbag play")),
)


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Day6FallbackError(f"cannot load module: {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Day6FallbackError(f"JSON object required: {path}")
    return value


def residual_processes() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for name, command in PROCESS_PATTERNS:
        completed = subprocess.run(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        rows = [line for line in completed.stdout.splitlines() if line]
        if rows:
            found[name] = rows
    return found


def configure_transport(
    module: Any, *, run_id: str, repeat_id: int
) -> None:
    module.RUN_ID = run_id
    module.SEQUENCES = (SEQUENCE_ID,)
    module.REPEATS = (repeat_id,)
    module.MODE = FAST_RUNTIME_MODE

    original_run_command = module.run_command

    def run_command(
        command: Sequence[str],
        *,
        environment: Mapping[str, str],
        output: Path | None = None,
        check: bool = True,
    ) -> Any:
        values = list(command)
        if len(values) >= 2 and Path(values[1]).name == (
            "53_validate_runtime_audit_products.py"
        ):
            values[1] = str(ROOT / "scripts/67_validate_frozen_observation.py")
            values.insert(2, "--runtime-products-only")
        result = original_run_command(
            values,
            environment=environment,
            output=output,
            check=check,
        )
        if values[:3] == [
            "rosparam",
            "set",
            "/harmful_bias/end_of_stream_audit_enabled",
        ]:
            for key, value in (
                (
                    "/harmful_bias/in_call_immutability_audit_enabled",
                    "true",
                ),
                (
                    "/harmful_bias/readonly_tap_buffer_capacity",
                    str(TAP_BUFFER_CAPACITY),
                ),
            ):
                original_run_command(
                    ["rosparam", "set", key, value],
                    environment=environment,
                )
        return result

    module.run_command = run_command
    original_shutdown = module.graceful_shutdown

    def graceful_shutdown(
        roslaunch: Any,
        *,
        environment: Mapping[str, str],
        run_dir: Path,
    ) -> dict[str, Any]:
        poll = module.bounded_trigger_call(
            IN_CALL_STATUS_SERVICE,
            environment=environment,
            timeout_sec=5.0,
        )
        module.atomic_json(
            run_dir / "in_call_immutability_service_evidence.json",
            dict(poll.evidence),
        )
        if poll.snapshot is None or poll.evidence.get("service_success") is not True:
            raise module.RunFailure(
                "RUNTIME_PRODUCT_MISSING",
                "in-call immutability status service failed",
            )
        status = validate_status(poll.snapshot)
        module.atomic_json(run_dir / "in_call_immutability_status.json", status)
        if int(status["audited_call_count"]) <= 0:
            raise module.RunFailure(
                "RUNTIME_PRODUCT_MISSING",
                "in-call audit observed no valid tap calls",
            )
        return original_shutdown(
            roslaunch,
            environment=environment,
            run_dir=run_dir,
        )

    module.graceful_shutdown = graceful_shutdown


def adjudicate_tail(
    raw: Mapping[str, Any],
    *,
    raw_runner_exit_code: int,
    raw_failure_classification: str,
) -> dict[str, Any]:
    step = int(raw["tail_clock_step_ns"])
    first_expected = int(raw["last_bag_clock_ns"]) + step
    final_expected = int(raw["tail_first_clock_ns"]) + (
        int(raw["tail_publish_count"]) - 1
    ) * step
    derived_duplicate = 0 if step > 0 else int(raw["tail_publish_count"])
    derived_backward = 0 if step > 0 else int(raw["tail_publish_count"])
    rule_applies = (
        int(raw["clock_publisher_overlap_count"]) == 0
        and int(raw["clock_backward_count"]) == 0
        and int(raw["tail_first_clock_ns"]) == first_expected
        and int(raw["tail_final_clock_ns"]) == final_expected
        and int(raw["tail_publish_count"]) > 0
        and raw_failure_classification in EXPECTED_RAW_FAILURES
    )
    adjudicated = bool(raw.get("handoff_pass")) or rule_applies
    return {
        "schema_version": "day6_fallback_tail_adjudication_v1",
        "tail_adjudication_rule_sha256": (
            EXPECTED_TAIL_ADJUDICATION_RULE_SHA256
        ),
        "frozen_v5_mixed_counter_rule_applied": rule_applies,
        "raw_runner_exit_code": raw_runner_exit_code,
        "raw_failure_classification": raw_failure_classification,
        "raw_tail_handoff_pass": bool(raw.get("handoff_pass")),
        "raw_clock_duplicate_count": int(raw["clock_duplicate_count"]),
        "raw_clock_backward_count": int(raw["clock_backward_count"]),
        "raw_overlap_count": int(raw["clock_publisher_overlap_count"]),
        "expected_first_tail_clock_ns": first_expected,
        "expected_final_tail_clock_ns": final_expected,
        "adjudicated_tail_duplicate_count": derived_duplicate,
        "adjudicated_tail_backward_count": derived_backward,
        "adjudicated_tail_handoff_pass": adjudicated,
        "runner_exit_adjudicated_pass": (
            raw_runner_exit_code == 0 or rule_applies
        ),
    }


def install_transport_inputs(
    run_lock_path: Path,
    transport_root: Path,
    *,
    run_id: str,
    repeat_id: int,
) -> Path:
    lock = json_object(run_lock_path)
    if lock.get("main_run_id") != MAIN_RUN_ID:
        raise Day6FallbackError("Day 6 main run-id lock mismatch")
    if tuple(lock.get("sub_run_ids", ())) != SUB_RUN_IDS:
        raise Day6FallbackError("Day 6 sub-run lock mismatch")
    if run_id not in SUB_RUN_IDS:
        raise Day6FallbackError("unauthorized Day 6 sub-run id")
    transport_lock = dict(lock)
    transport_lock.update(
        {
            "run_id": run_id,
            "repeat_id": repeat_id,
            "runtime_mode": FAST_RUNTIME_MODE,
            "payload_profile": PAYLOAD_PROFILE,
            "detector_execution": "disabled",
            "runtime_equivalence_comparison": "disabled",
            "readonly_tap_enabled": True,
            "readonly_tap_export_enabled": True,
            "in_call_immutability_audit_enabled": True,
        }
    )
    source_root = run_lock_path.parent
    for field in ("degen_source_lock_path", "fastlio2_source_lock_path"):
        relative = Path(str(lock[field]))
        source = source_root / relative
        destination = transport_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    installed = transport_root / "day6_transport_run_lock.json"
    write_json(installed, transport_lock)
    return installed


def copy_product(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise Day6FallbackError(f"runtime product missing: {source.name}")
    shutil.copy2(source, destination)


def materialize_run_outputs(
    *,
    output: Path,
    run_dir: Path,
    endpoint_contract: Path,
    raw_runner_exit_code: int,
    raw_failure_classification: str,
) -> dict[str, Any]:
    validator = load_module(
        ROOT / "scripts/67_validate_frozen_observation.py",
        "day6_runtime_product_validator",
    )
    converted_transport = run_dir / "converted_transport"
    validation = validator.validate_runtime_products(
        run_dir, converted_transport
    )
    write_json(run_dir / "runtime_product_validation_day6.json", validation)

    transport_summary = json_object(run_dir / "run_summary.json")
    expected_runtime_run_id = str(transport_summary["run_id"])
    observation_diagnostics = run_dir / "observation_diagnostics"
    conversion = convert_frozen_set(
        observation_binary=run_dir / "observation_records_v3.bin",
        runtime_binary=run_dir / "runtime_audit_v2.bin",
        output_dir=observation_diagnostics,
        endpoint_contract_sha256=sha256_file(endpoint_contract),
        expected_run_id=expected_runtime_run_id,
        expected_sequence_id=SEQUENCE_ID,
    )

    raw_tail = json_object(run_dir / "tail_clock_handoff.json")
    adjudication = adjudicate_tail(
        raw_tail,
        raw_runner_exit_code=raw_runner_exit_code,
        raw_failure_classification=raw_failure_classification,
    )
    drain = json_object(run_dir / "end_of_stream_drain.json")
    shutdown = json_object(run_dir / "graceful_shutdown_v5.json")
    handshake = json_object(run_dir / "connection_handshake_v5.json")
    tap = json_object(run_dir / "tap_export_summary.json")
    in_call = validate_status(
        json_object(run_dir / "in_call_immutability_status.json")
    )

    if not adjudication["adjudicated_tail_handoff_pass"]:
        raise Day6FallbackError("frozen V5 tail adjudication did not pass")
    if (
        int(drain["actual_lidar_callback_count"])
        != EXPECTED_LIDAR_CALLBACK_COUNT
        or int(drain["actual_imu_callback_count"])
        != EXPECTED_IMU_CALLBACK_COUNT
    ):
        raise Day6FallbackError("endpoint callback contract failed")

    copy_pairs = (
        ("observation_records_v3.bin", "observation_records_v3.bin"),
        ("runtime_audit_v2.bin", "runtime_audit_v2.bin"),
        ("final_map_summary.json", "final_map_summary.json"),
        ("tap_export_summary.json", "tap_export_summary.json"),
    )
    for source_name, destination_name in copy_pairs:
        copy_product(run_dir / source_name, output / destination_name)
    copy_product(endpoint_contract, output / "endpoint_contract.json")
    shutil.copy2(
        run_dir / "connection_handshake_v5.json",
        output / "connection_handshake_summary.json",
    )
    shutil.copy2(
        run_dir / "tail_clock_handoff.json",
        output / "tail_clock_raw_summary.json",
    )
    shutil.copy2(
        run_dir / "end_of_stream_drain.json", output / "drain_summary.json"
    )
    shutil.copy2(
        run_dir / "graceful_shutdown_v5.json",
        output / "shutdown_summary.json",
    )
    write_json(output / "tail_clock_adjudication_summary.json", adjudication)
    write_json(output / "runtime_product_summary.json", validation)
    write_json(output / "in_call_immutability_summary.json", in_call)

    diagnostic_names = {
        "record_index.csv": "observation_record_index.csv",
        "lifecycle_summary.json": "observation_lifecycle_summary.json",
        "schema_validation_summary.json": "observation_schema_summary.json",
        "no_gt_audit.json": "observation_no_gt_audit.json",
        "binary_validation_summary.json": (
            "observation_binary_validation_summary.json"
        ),
        "record_manifest.json": "observation_record_manifest.json",
    }
    for source_name, destination_name in diagnostic_names.items():
        shutil.copy2(
            observation_diagnostics / source_name, output / destination_name
        )

    binary_sha = sha256_file(output / "observation_records_v3.bin")
    (output / "observation_records_v3.bin.sha256").write_text(
        f"{binary_sha}  observation_records_v3.bin\n", encoding="utf-8"
    )
    lifecycle = conversion["lifecycle"]
    summary = {
        "schema_version": "day6_fallback_real_replay_run_summary_v1",
        "run_id": output.name,
        "sequence_id": SEQUENCE_ID,
        "runtime_mode": FAST_RUNTIME_MODE,
        "payload_profile": PAYLOAD_PROFILE,
        "raw_runner_exit_code": raw_runner_exit_code,
        "raw_failure_classification": raw_failure_classification,
        "raw_tail_handoff_pass": adjudication["raw_tail_handoff_pass"],
        "adjudicated_tail_handoff_pass": adjudication[
            "adjudicated_tail_handoff_pass"
        ],
        "tail_adjudication_rule_sha256": adjudication[
            "tail_adjudication_rule_sha256"
        ],
        "lidar_callback_count": int(drain["actual_lidar_callback_count"]),
        "imu_callback_count": int(drain["actual_imu_callback_count"]),
        "end_of_stream_drain_pass": bool(drain["drain_pass"]),
        "normal_shutdown_pass": bool(shutdown["shutdown_completed"]),
        "runtime_product_pass": bool(validation["runtime_product_pass"]),
        "connection_handshake_pass": bool(handshake["handshake_pass"]),
        "observation_binary_sha256": binary_sha,
        "observation_binary_size_bytes": (
            output / "observation_records_v3.bin"
        ).stat().st_size,
        "observation_record_count": int(
            conversion["record_manifest"]["observation_record_count"]
        ),
        "first_valid_linearization_count": int(
            lifecycle["first_valid_linearization_count"]
        ),
        "tap_emitted_count": int(in_call["tap_record_emitted_count"]),
        "in_call_audited_count": int(in_call["audited_call_count"]),
        "tap_drop_count": int(tap["tap_drop_count"]),
        "writer_error_count": int(tap["writer_error_count"]),
        "binary_checksum_failure_count": int(
            conversion["binary_validation"][
                "binary_checksum_failure_count"
            ]
        ),
        "truncated_record_count": int(
            conversion["binary_validation"]["truncated_record_count"]
        ),
        "extra_trailing_bytes": int(
            conversion["binary_validation"].get("extra_trailing_bytes", 0)
        ),
        "in_call_mutation_count": int(in_call["mutation_detected_count"]),
        "schema_rejected_record_count": int(
            conversion["schema_validation"]["schema_rejected_record_count"]
        ),
        "nonfinite_input_record_count": int(
            conversion["schema_validation"]["nonfinite_record_count"]
        ),
        "forbidden_input_field_count": int(
            conversion["no_gt"]["forbidden_field_count"]
        ),
        "GT_TOPIC_CONSUMED_COUNT": int(
            conversion["no_gt"]["gt_topic_consumed_count"]
        ),
        "roscore_run": True,
        "roslaunch_run": True,
        "rosbag_run": True,
        "fastlio2_run": True,
        "detector_called_inside_fastlio2": False,
        "detector_feedback_enabled": False,
        "complete": True,
    }
    required_487 = (
        summary["observation_record_count"],
        summary["first_valid_linearization_count"],
        summary["tap_emitted_count"],
        summary["in_call_audited_count"],
    )
    zero_counts = (
        summary["tap_drop_count"],
        summary["writer_error_count"],
        summary["binary_checksum_failure_count"],
        summary["truncated_record_count"],
        summary["extra_trailing_bytes"],
        summary["in_call_mutation_count"],
        summary["schema_rejected_record_count"],
        summary["nonfinite_input_record_count"],
        summary["forbidden_input_field_count"],
        summary["GT_TOPIC_CONSUMED_COUNT"],
    )
    summary["complete"] = (
        all(value == EXPECTED_RECORD_COUNT for value in required_487)
        and all(value == 0 for value in zero_counts)
        and summary["connection_handshake_pass"]
        and summary["end_of_stream_drain_pass"]
        and summary["normal_shutdown_pass"]
        and summary["runtime_product_pass"]
        and summary["adjudicated_tail_handoff_pass"]
    )
    if not summary["complete"]:
        raise Day6FallbackError(f"real replay completeness failed: {summary}")
    write_json(output / "run_summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--clip", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-lock", required=True, type=Path)
    parser.add_argument("--endpoint-contract", required=True, type=Path)
    parser.add_argument("--authorization-audit", required=True, type=Path)
    parser.add_argument("--enable-readonly-tap", action="store_true")
    parser.add_argument("--enable-compact-export", action="store_true")
    parser.add_argument("--enable-in-call-audit", action="store_true")
    parser.add_argument("--disable-runtime-detector", action="store_true")
    parser.add_argument("--use-frozen-tail-adjudication", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    required_flags = (
        args.enable_readonly_tap,
        args.enable_compact_export,
        args.enable_in_call_audit,
        args.disable_runtime_detector,
        args.use_frozen_tail_adjudication,
    )
    if not all(required_flags):
        raise SystemExit("ERROR: all Day 6 Fallback safety flags are required")
    if args.sequence != SEQUENCE_ID:
        raise SystemExit("ERROR: only avia_quick_shack is authorized")
    if args.run_id not in SUB_RUN_IDS:
        raise SystemExit("ERROR: unauthorized Day 6 Fallback run-id")
    repeat_id = SUB_RUN_IDS.index(args.run_id) + 1
    output = args.output_dir.expanduser().resolve()
    if output.exists():
        raise SystemExit(f"ERROR: output directory exists: {output}")
    clip = args.clip.expanduser().resolve()
    if not clip.is_file() or sha256_file(clip) != EXPECTED_CLIP_SHA256:
        raise SystemExit("ERROR: Quick Shack clip SHA mismatch")
    if clip.stat().st_mode & 0o222:
        raise SystemExit("ERROR: Quick Shack clip must be read-only")
    validate_authorization_archive(args.authorization_audit)
    before_processes = residual_processes()
    if before_processes:
        raise SystemExit(f"ERROR: residual ROS processes before run: {before_processes}")

    output.mkdir(parents=True, exist_ok=False)
    transport_root = output / "_transport"
    transport_root.mkdir()
    transport_lock = install_transport_inputs(
        args.run_lock.resolve(),
        transport_root,
        run_id=args.run_id,
        repeat_id=repeat_id,
    )
    endpoint_contract = args.endpoint_contract.resolve()
    shutil.copy2(args.run_lock.resolve(), output / args.run_lock.name)
    shutil.copy2(
        args.authorization_audit.resolve(),
        output / "authorization_identity_source.tar.gz",
    )

    module = load_module(
        ROOT / "scripts/60_run_single_startup_sync_v5.py",
        f"day6_v5_transport_{repeat_id}",
    )
    configure_transport(module, run_id=args.run_id, repeat_id=repeat_id)
    transport_args = argparse.Namespace(
        run_id=args.run_id,
        sequence_id=SEQUENCE_ID,
        repeat_id=repeat_id,
        run_root=transport_root,
        endpoint_contract=endpoint_contract,
        run_lock=transport_lock,
    )
    raw_exit = 0
    failure_classification = "NONE"
    try:
        module.execute(transport_args)
    except module.RunFailure as error:
        raw_exit = 30
        failure_classification = str(error.classification)
    finally:
        if module._ACTIVE_HEARTBEAT is not None:
            module._ACTIVE_HEARTBEAT.stop()
            module._ACTIVE_HEARTBEAT = None
    run_dir = (
        transport_root
        / "runs/baseline"
        / SEQUENCE_ID
        / f"AUDIT_ONLY_R{repeat_id}"
    )
    if raw_exit and failure_classification not in EXPECTED_RAW_FAILURES:
        raise Day6FallbackError(
            "raw runner failed for a non-frozen reason: "
            f"{failure_classification}"
        )
    summary = materialize_run_outputs(
        output=output,
        run_dir=run_dir,
        endpoint_contract=endpoint_contract,
        raw_runner_exit_code=raw_exit,
        raw_failure_classification=failure_classification,
    )
    after_processes = residual_processes()
    process_summary = {
        "schema_version": "day6_post_run_process_cleanup_v1",
        "before_run_residual_processes": before_processes,
        "after_run_residual_processes": after_processes,
        "clean_before_run": not before_processes,
        "clean_after_run": not after_processes,
    }
    write_json(output / "post_run_process_cleanup.json", process_summary)
    if after_processes:
        raise Day6FallbackError(
            f"residual ROS processes after run: {after_processes}"
        )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        raise SystemExit(main())
    except (
        Day6FallbackError,
        FrozenObservationError,
        OSError,
        KeyError,
        ValueError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
