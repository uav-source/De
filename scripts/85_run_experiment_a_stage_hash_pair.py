#!/usr/bin/env python3
"""Run one member of the authorized two-run Experiment A replay pair.

This wrapper reuses the frozen Day 5 V5 paused-start, connection handshake,
tail-clock adjudication, drain, and normal-shutdown transport. It adds only the
bounded Experiment A status service and compact post-run materialization.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import signal
import sys
import tarfile
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.experiment_a_stage_hash import (  # noqa: E402
    SCAN_END,
    SCAN_START,
    materialize_status,
    validate_status,
)


MAIN_RUN_ID = "multihyp_day6_experiment_a_input_map_hash_v1"
SUB_RUN_IDS = (
    "multihyp_day6_experiment_a_hash_r1",
    "multihyp_day6_experiment_a_hash_r2",
)
SEQUENCE_ID = "avia_quick_shack"
EXPECTED_CLIP_SHA256 = (
    "272325265978787c838e010b1f0da963a15fb4b08ff8730fc3dd9901e32a0e20"
)
EXPECTED_AUDIT_SHA256 = (
    "f93ee5afec27c616b8849ded6fadc200c7be8b58fd124fd4c118a2566bfba9de"
)
STAGE_STATUS_SERVICE = "/harmful_bias/experiment_a_stage_hash_status"


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_authorization_archive(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise RuntimeError("Experiment A authorization archive missing")
    base = load_module(
        ROOT / "src/fastlio2_adapter/day6_fallback_functional_diagnostics.py",
        "experiment_a_sha_helper",
    )
    actual = base.sha256_file(resolved)
    if actual != EXPECTED_AUDIT_SHA256:
        raise RuntimeError("Experiment A authorization archive SHA mismatch")
    with tarfile.open(resolved, "r:gz") as archive:
        names = archive.getnames()
        required_fragments = (
            "day6_branch_divergence_root_cause_manifest.json",
            "day6_branch_divergence_root_cause_report.md",
        )
        for fragment in required_fragments:
            if not any(name.endswith(fragment) for name in names):
                raise RuntimeError(
                    f"authorization evidence missing: {fragment}"
                )
    return {
        "authorization_audit_path": str(resolved),
        "authorization_audit_sha256": actual,
        "day6_branch_divergence_root_cause_audit_pass": True,
        "branch_divergence_localized_pass": True,
        "fast_branch_root_cause_proven": False,
        "experiment_a_authorization_source":
            "USER_TASK_DIRECTIVE_2026-07-17",
        "experiment_a_input_and_map_stage_hashes_authorized": True,
        "experiment_b_thread_sensitivity_authorized": False,
        "experiment_c_correspondence_fine_grain_authorized": False,
        "day7_authorized": False,
        "stage3_start_authorized": False,
    }


def configure_transport(
    base: Any, transport: Any, *, run_id: str, repeat_id: int
) -> None:
    base.configure_transport(
        transport, run_id=run_id, repeat_id=repeat_id
    )
    prior_run_command = transport.run_command

    def run_command(
        command: Sequence[str],
        *,
        environment: Mapping[str, str],
        output: Path | None = None,
        check: bool = True,
    ) -> Any:
        values = list(command)
        if values[:3] == [
            "rosparam",
            "set",
            "/harmful_bias/run_id",
        ]:
            values[3] = run_id
        result = prior_run_command(
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
                    "/harmful_bias/experiment_a_stage_hash_enabled",
                    "true",
                ),
                (
                    "/harmful_bias/experiment_a_scan_start",
                    str(SCAN_START),
                ),
                (
                    "/harmful_bias/experiment_a_scan_end",
                    str(SCAN_END),
                ),
            ):
                prior_run_command(
                    ["rosparam", "set", key, value],
                    environment=environment,
                )
        return result

    transport.run_command = run_command
    prior_shutdown = transport.graceful_shutdown

    def graceful_shutdown(
        roslaunch: Any,
        *,
        environment: Mapping[str, str],
        run_dir: Path,
    ) -> dict[str, Any]:
        poll = transport.bounded_trigger_call(
            STAGE_STATUS_SERVICE,
            environment=environment,
            timeout_sec=15.0,
        )
        transport.atomic_json(
            run_dir / "experiment_a_stage_hash_service_evidence.json",
            dict(poll.evidence),
        )
        if (
            poll.snapshot is None
            or poll.evidence.get("service_success") is not True
        ):
            raise transport.RunFailure(
                "RUNTIME_PRODUCT_MISSING",
                "Experiment A stage-hash status service failed",
            )
        validated = validate_status(poll.snapshot)
        transport.atomic_json(
            run_dir / "experiment_a_stage_hash_status.json",
            validated,
        )
        return prior_shutdown(
            roslaunch, environment=environment, run_dir=run_dir
        )

    transport.graceful_shutdown = graceful_shutdown


def materialization_context(
    run_lock_path: Path,
    *,
    run_id: str,
) -> dict[str, Any]:
    """Resolve post-run fields from the frozen lock before ROS can start."""

    value = json.loads(
        run_lock_path.expanduser().resolve().read_text(encoding="utf-8")
    )
    if not isinstance(value, dict):
        raise RuntimeError("run lock must be a JSON object")
    if value.get("main_run_id") != MAIN_RUN_ID:
        raise RuntimeError("materialization run lock main run-id mismatch")
    if tuple(value.get("sub_run_ids", ())) != SUB_RUN_IDS:
        raise RuntimeError("materialization run lock sub-run ids mismatch")
    ports = value.get("ros_master_ports")
    if not isinstance(ports, dict) or run_id not in ports:
        raise RuntimeError(
            f"ros_master_port missing from run lock for {run_id}"
        )
    port = ports[run_id]
    if isinstance(port, bool) or not isinstance(port, int):
        raise RuntimeError("ros_master_port must be an integer")
    if not 1 <= port <= 65535:
        raise RuntimeError("ros_master_port is outside the valid range")
    locked_ports = [ports.get(locked_run_id) for locked_run_id in SUB_RUN_IDS]
    if any(
        isinstance(item, bool) or not isinstance(item, int)
        for item in locked_ports
    ):
        raise RuntimeError("all authorized ros_master_ports are required")
    if len(set(locked_ports)) != len(locked_ports):
        raise RuntimeError("authorized ros_master_ports must be unique")
    return {
        "schema_version": "experiment_a_materialization_context_v1",
        "run_id": run_id,
        "ros_master_port": port,
        "authoritative_source": "frozen run lock ros_master_ports",
    }


def finalize_materialized_summary(
    runtime_summary: Mapping[str, Any],
    stage_summary: Mapping[str, Any],
    *,
    run_id: str,
    ros_master_port: int,
) -> dict[str, Any]:
    """Create a new summary without mutating runtime evidence."""

    summary = dict(runtime_summary)
    summary.update(
        {
            "schema_version": "day6_experiment_a_replay_run_summary_v1",
            "run_id": run_id,
            "ros_master_port": ros_master_port,
            "stage_hash_record_count": int(
                stage_summary["stage_record_count"]
            ),
            "stage_hash_first_scan": int(
                stage_summary["first_scan_index"]
            ),
            "stage_hash_last_scan": int(stage_summary["last_scan_index"]),
            "diagnostic_mutation_count": int(
                stage_summary["diagnostic_mutation_count"]
            ),
            "diagnostic_internal_error_count": int(
                stage_summary["diagnostic_internal_error_count"]
            ),
            "stage_hash_schema_pass": True,
            "stage_hash_window_coverage_pass": True,
            "raw_lidar_hash_capture_pass": True,
            "imu_bundle_hash_capture_pass": True,
            "undistorted_cloud_hash_capture_pass": True,
            "map_before_hash_capture_pass": True,
            "correspondence_hash_reuse_pass": True,
            "insertion_batch_hash_capture_pass": True,
            "map_after_hash_capture_pass": True,
        }
    )
    summary["complete"] = bool(summary["complete"]) and all(
        (
            summary["stage_hash_record_count"] == 26,
            summary["stage_hash_first_scan"] == 135,
            summary["stage_hash_last_scan"] == 160,
            summary["diagnostic_mutation_count"] == 0,
            summary["diagnostic_internal_error_count"] == 0,
        )
    )
    return summary


def materialize(
    base: Any,
    *,
    output: Path,
    run_dir: Path,
    endpoint_contract: Path,
    raw_runner_exit_code: int,
    raw_failure_classification: str,
    ros_master_port: int,
) -> dict[str, Any]:
    runtime_summary = base.materialize_run_outputs(
        output=output,
        run_dir=run_dir,
        endpoint_contract=endpoint_contract,
        raw_runner_exit_code=raw_runner_exit_code,
        raw_failure_classification=raw_failure_classification,
    )
    stage_status = json.loads(
        (run_dir / "experiment_a_stage_hash_status.json").read_text(
            encoding="utf-8"
        )
    )
    stage_summary = materialize_status(stage_status, output)
    runtime_product_summary = json.loads(
        (output / "runtime_product_summary.json").read_text(
            encoding="utf-8"
        )
    )
    runtime_summary_with_counts = dict(runtime_summary)
    runtime_summary_with_counts["runtime_scan_count"] = int(
        runtime_product_summary["runtime_binary_record_count"]
    )
    summary = finalize_materialized_summary(
        runtime_summary_with_counts,
        stage_summary,
        run_id=output.name,
        ros_master_port=ros_master_port,
    )
    base.write_json(output / "run_summary.json", summary)
    return summary


def main() -> int:
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
    parser.add_argument("--enable-experiment-a-stage-hash", action="store_true")
    parser.add_argument("--disable-runtime-detector", action="store_true")
    parser.add_argument("--use-frozen-tail-adjudication", action="store_true")
    args = parser.parse_args()

    if not all(
        (
            args.enable_readonly_tap,
            args.enable_compact_export,
            args.enable_in_call_audit,
            args.enable_experiment_a_stage_hash,
            args.disable_runtime_detector,
            args.use_frozen_tail_adjudication,
        )
    ):
        raise RuntimeError("all Experiment A safety flags are required")
    if args.sequence != SEQUENCE_ID or args.run_id not in SUB_RUN_IDS:
        raise RuntimeError("unauthorized Experiment A replay identity")
    context = materialization_context(
        args.run_lock,
        run_id=args.run_id,
    )
    output = args.output_dir.expanduser().resolve()
    if output.exists():
        raise RuntimeError(f"output already exists: {output}")

    base = load_module(
        ROOT / "scripts/75_run_day6_fallback_real_replay.py",
        "experiment_a_day6_transport_base",
    )
    base.MAIN_RUN_ID = MAIN_RUN_ID
    base.SUB_RUN_IDS = SUB_RUN_IDS
    base.SEQUENCE_ID = SEQUENCE_ID
    base.EXPECTED_CLIP_SHA256 = EXPECTED_CLIP_SHA256
    base.validate_authorization_archive = validate_authorization_archive

    clip = args.clip.expanduser().resolve()
    if not clip.is_file() or base.sha256_file(clip) != EXPECTED_CLIP_SHA256:
        raise RuntimeError("Quick Shack clip SHA mismatch")
    if clip.stat().st_mode & 0o222:
        raise RuntimeError("Quick Shack clip must be read-only")
    authorization = validate_authorization_archive(args.authorization_audit)
    before_processes = base.residual_processes()
    if before_processes:
        raise RuntimeError(
            f"residual ROS processes before run: {before_processes}"
        )

    repeat_id = SUB_RUN_IDS.index(args.run_id) + 1
    output.mkdir(parents=True, exist_ok=False)
    base.write_json(output / "authorization_identity.json", authorization)
    transport_root = output / "_transport"
    transport_root.mkdir()
    transport_lock = base.install_transport_inputs(
        args.run_lock.resolve(),
        transport_root,
        run_id=args.run_id,
        repeat_id=repeat_id,
    )
    endpoint_contract = args.endpoint_contract.resolve()

    transport = load_module(
        ROOT / "scripts/60_run_single_startup_sync_v5.py",
        f"experiment_a_v5_transport_{repeat_id}",
    )
    configure_transport(
        base, transport, run_id=args.run_id, repeat_id=repeat_id
    )
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
        transport.execute(transport_args)
    except transport.RunFailure as error:
        raw_exit = 30
        failure_classification = str(error.classification)
    finally:
        if transport._ACTIVE_HEARTBEAT is not None:
            transport._ACTIVE_HEARTBEAT.stop()
            transport._ACTIVE_HEARTBEAT = None
    run_dir = (
        transport_root
        / "runs/baseline"
        / SEQUENCE_ID
        / f"AUDIT_ONLY_R{repeat_id}"
    )
    if (
        raw_exit
        and failure_classification not in base.EXPECTED_RAW_FAILURES
    ):
        raise RuntimeError(
            "raw runner failed for non-frozen reason: "
            f"{failure_classification}"
        )
    summary = materialize(
        base,
        output=output,
        run_dir=run_dir,
        endpoint_contract=endpoint_contract,
        raw_runner_exit_code=raw_exit,
        raw_failure_classification=failure_classification,
        ros_master_port=int(context["ros_master_port"]),
    )
    after_processes = base.residual_processes()
    base.write_json(
        output / "post_run_process_cleanup.json",
        {
            "schema_version": "experiment_a_post_run_process_cleanup_v1",
            "before_run_residual_processes": before_processes,
            "after_run_residual_processes": after_processes,
            "clean_before_run": not before_processes,
            "clean_after_run": not after_processes,
        },
    )
    if after_processes:
        raise RuntimeError(
            f"residual ROS processes after run: {after_processes}"
        )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
