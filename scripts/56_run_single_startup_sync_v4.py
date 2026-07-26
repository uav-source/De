#!/usr/bin/env python3
"""Run exactly one Git-locked Day 5 startup-sync V4 AUDIT_ONLY replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.replay_endpoint_contract import sequence_contract  # noqa: E402
from fastlio2_adapter.runtime_paths import (  # noqa: E402
    RuntimePathError,
    build_runtime_paths,
    validate_runtime_output_param,
)
from fastlio2_adapter.source_lock import (  # noqa: E402
    clear_allowed_runtime_outputs,
    compare_runtime_inventories,
    runtime_output_inventory,
    sha256_file,
    snapshot_source_lock,
    source_lock_mismatches,
)


RUN_ID = "multihyp_day5_startup_sync_v4"
SEQUENCES = ("avia_quick_shack", "avia_outdoor_run_100hz")
REPEATS = (1, 2, 3)
MODE = "AUDIT_ONLY"
LOCKED_ENVIRONMENT = {
    "OMP_NUM_THREADS": "1",
    "OMP_DYNAMIC": "FALSE",
    "OMP_SCHEDULE": "static",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "LC_ALL": "C",
    "LANG": "C",
}


class RunFailure(RuntimeError):
    def __init__(self, classification: str, message: str) -> None:
        super().__init__(message)
        self.classification = classification


def atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(str(path.parent), os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def state_writer(path: Path, identity: Mapping[str, Any]):
    started = time.time()

    def write(status: str, **extra: Any) -> None:
        atomic_json(
            path,
            {
                **identity,
                "status": status,
                "pid": os.getpid(),
                "started_at_epoch": started,
                "updated_at_epoch": time.time(),
                **extra,
            },
        )

    return write


def shlex_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def ros_environment(fast_ws: Path) -> dict[str, str]:
    command = (
        "source /opt/ros/noetic/setup.bash && "
        f"source {shlex_quote(str(fast_ws / 'devel/setup.bash'))} && env -0"
    )
    completed = subprocess.run(
        ["bash", "-c", command], stdout=subprocess.PIPE, check=True
    )
    environment = dict(os.environ)
    for row in completed.stdout.split(b"\0"):
        if b"=" in row:
            key, value = row.split(b"=", 1)
            environment[key.decode()] = value.decode()
    environment.update(LOCKED_ENVIRONMENT)
    return environment


def run_command(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    output: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[Any]:
    if output is None:
        return subprocess.run(
            list(command),
            env=dict(environment),
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        return subprocess.run(
            list(command),
            env=dict(environment),
            check=check,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
        )


def start_process(
    command: Sequence[str], log_path: Path, environment: Mapping[str, str]
) -> tuple[subprocess.Popen[Any], Any]:
    handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        list(command),
        env=dict(environment),
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    return process, handle


def stop_process(
    process: subprocess.Popen[Any] | None, timeout: float = 20.0
) -> int | None:
    if process is None or process.poll() is not None:
        return None if process is None else process.returncode
    try:
        os.killpg(process.pid, signal.SIGINT)
    except ProcessLookupError:
        pass
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            return process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            return process.wait(timeout=5)


def wait_command(
    command: Sequence[str],
    *,
    environment: Mapping[str, str],
    attempts: int,
    process: subprocess.Popen[Any] | None = None,
) -> None:
    for _ in range(attempts):
        completed = subprocess.run(
            list(command),
            env=dict(environment),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if completed.returncode == 0:
            return
        if process is not None and process.poll() is not None:
            raise RunFailure(
                "RUNTIME_PRODUCT_MISSING",
                f"process exited while waiting for {' '.join(command)}",
            )
        time.sleep(0.1)
    raise RunFailure(
        "RUNTIME_PRODUCT_MISSING",
        f"timeout waiting for {' '.join(command)}",
    )


def source_lock_result(
    lock: Mapping[str, Any],
    run_root: Path,
    output: Path,
) -> dict[str, Any]:
    fast_root = Path(lock["fastlio2_root"])
    binary = Path(lock["binary_path"])
    degen_expected = json.loads(
        (run_root / lock["degen_source_lock_path"]).read_text(encoding="utf-8")
    )
    fast_expected = json.loads(
        (run_root / lock["fastlio2_source_lock_path"]).read_text(encoding="utf-8")
    )
    degen_actual = snapshot_source_lock(ROOT, repo_alias="Degen-LIO")
    fast_actual = snapshot_source_lock(
        fast_root,
        repo_alias="FAST_LIO",
        binary_path=binary,
        binary_path_alias=lock["fastlio2_binary_path_alias"],
    )
    degen_mismatches = source_lock_mismatches(degen_expected, degen_actual)
    fast_mismatches = source_lock_mismatches(fast_expected, fast_actual)
    clip_results = {}
    for sequence, definition in lock["clips"].items():
        path = Path(definition["path"])
        actual = sha256_file(path) if path.is_file() else None
        clip_results[sequence] = {
            "sha256": actual,
            "match": actual == definition["sha256"],
            "read_only": path.is_file() and path.stat().st_mode & 0o222 == 0,
        }
    binary_actual = sha256_file(binary) if binary.is_file() else None
    result = {
        "source_lock_pass": not degen_mismatches and not fast_mismatches,
        "degen_source_lock_pass": not degen_mismatches,
        "fastlio2_source_lock_pass": not fast_mismatches,
        "degen_mismatches": degen_mismatches,
        "fastlio2_mismatches": fast_mismatches,
        "binary_sha256": binary_actual,
        "binary_lock_pass": binary_actual == lock["fastlio2_binary_sha256"],
        "clip_results": clip_results,
        "clip_lock_pass": all(
            row["match"] and row["read_only"] for row in clip_results.values()
        ),
    }
    atomic_json(output, result)
    if not result["source_lock_pass"]:
        raise RunFailure("SOURCE_LOCK_CHANGED", f"source lock mismatch: {output}")
    if not result["binary_lock_pass"]:
        raise RunFailure("BINARY_CHANGED", f"binary lock mismatch: {output}")
    if not result["clip_lock_pass"]:
        raise RunFailure("CLIP_CHANGED", f"clip lock mismatch: {output}")
    return result


def graceful_shutdown(
    roslaunch: subprocess.Popen[Any],
    *,
    environment: Mapping[str, str],
    run_dir: Path,
) -> dict[str, Any]:
    started = time.monotonic_ns()
    request = subprocess.run(
        ["rosnode", "kill", "/laserMapping"],
        env=dict(environment),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    (run_dir / "rosnode_shutdown.txt").write_text(
        request.stdout or "", encoding="utf-8"
    )
    forced_terminate = False
    forced_kill = False
    try:
        exit_code = roslaunch.wait(timeout=30)
    except subprocess.TimeoutExpired:
        forced_terminate = True
        roslaunch.terminate()
        try:
            exit_code = roslaunch.wait(timeout=5)
        except subprocess.TimeoutExpired:
            forced_kill = True
            roslaunch.kill()
            exit_code = roslaunch.wait(timeout=5)
    result = {
        "rosbag_natural_exit": True,
        "shutdown_request_method": "rosnode kill /laserMapping",
        "shutdown_request_monotonic_ns": started,
        "laser_mapping_exit_code": 0 if request.returncode == 0 else None,
        "roslaunch_exit_code": exit_code,
        "shutdown_completed": not forced_terminate and not forced_kill,
        "shutdown_duration_ms": (time.monotonic_ns() - started) / 1_000_000.0,
        "forced_terminate_used": forced_terminate,
        "forced_kill_used": forced_kill,
    }
    atomic_json(run_dir / "graceful_shutdown_v4.json", result)
    if not result["shutdown_completed"]:
        raise RunFailure(
            "RUNTIME_NODE_SHUTDOWN_INCOMPLETE",
            "laserMapping did not complete normal shutdown",
        )
    return result


def execute(args: argparse.Namespace) -> dict[str, Any]:
    run_root = args.run_root.expanduser().resolve()
    endpoint_path = args.endpoint_contract.expanduser().resolve()
    lock_path = args.run_lock.expanduser().resolve()
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    contract_bytes = endpoint_path.read_bytes()
    contract = json.loads(contract_bytes)
    endpoint = sequence_contract(contract, args.sequence_id)
    if lock.get("run_id") != RUN_ID:
        raise RunFailure("SOURCE_LOCK_CHANGED", "wrong V4 run lock")
    if lock.get("endpoint_contract_sha256") != hashlib.sha256(contract_bytes).hexdigest():
        raise RunFailure("ENDPOINT_CONTRACT_MISMATCH", "endpoint contract SHA mismatch")
    if args.sequence_id not in SEQUENCES or args.repeat_id not in REPEATS:
        raise RunFailure("SOURCE_LOCK_CHANGED", "unsupported replay identity")
    run_label = f"AUDIT_ONLY_R{args.repeat_id}"
    phase_root = run_root / "runs/baseline"
    run_dir = phase_root / args.sequence_id / run_label
    if run_dir.exists():
        raise RunFailure("SOURCE_LOCK_CHANGED", f"run directory exists: {run_dir}")
    fast_root = Path(lock["fastlio2_root"])
    fast_ws = Path(lock["fastlio2_ws"])
    binary = Path(lock["binary_path"])
    clip = lock["clips"][args.sequence_id]
    clip_path = Path(clip["path"])
    try:
        paths = build_runtime_paths(
            run_root=run_root,
            phase_root=phase_root,
            run_dir=run_dir,
            clip_path=clip_path,
            binary_path=binary,
        )
    except RuntimePathError as error:
        raise RunFailure("RUNTIME_PRODUCT_MISSING", str(error)) from error
    run_dir.mkdir(parents=True)
    paths.ros_home.mkdir()
    paths.ros_log_dir.mkdir()
    atomic_json(run_dir / "absolute_path_audit.json", paths.audit())
    write_state = state_writer(
        run_dir / "single_run_state.json",
        {
            "run_id": RUN_ID,
            "sequence_id": args.sequence_id,
            "repeat_id": args.repeat_id,
            "runtime_mode": MODE,
        },
    )
    write_state("CREATED")
    before_clear = runtime_output_inventory(fast_root)
    atomic_json(run_dir / "runtime_output_inventory_before_clear.json", before_clear)
    clear_actions = clear_allowed_runtime_outputs(fast_root)
    atomic_json(run_dir / "runtime_output_clear_actions.json", {"actions": clear_actions})
    after_clear = runtime_output_inventory(fast_root)
    clear_audit = compare_runtime_inventories(before_clear, after_clear)
    atomic_json(run_dir / "runtime_output_clear_allowlist_audit.json", clear_audit)
    if not clear_audit["allowlist_pass"]:
        raise RunFailure("SOURCE_LOCK_CHANGED", "runtime clear exceeded allowlist")
    source_lock_result(lock, run_root, run_dir / "post_clear_source_lock.json")

    environment = ros_environment(fast_ws)
    sequence_slot = SEQUENCES.index(args.sequence_id) + 1
    ros_port = 19800 + sequence_slot * 10 + args.repeat_id
    environment.update(
        {
            "ROS_MASTER_URI": f"http://127.0.0.1:{ros_port}",
            "ROS_HOSTNAME": "127.0.0.1",
            "ROS_HOME": str(paths.ros_home),
            "ROS_LOG_DIR": str(paths.ros_log_dir),
        }
    )
    config_bundle = hashlib.sha256(
        (
            sha256_file(fast_root / "config/avia.yaml")
            + sha256_file(fast_root / "launch/mapping_avia.launch")
        ).encode()
    ).hexdigest()
    roscore = roslaunch = rosbag = None
    handles: list[Any] = []
    rosbag_exit: int | None = None
    shutdown: dict[str, Any] | None = None
    try:
        write_state("STARTING_ROS")
        roscore, handle = start_process(
            ["roscore", "-p", str(ros_port)], run_dir / "roscore.log", environment
        )
        handles.append(handle)
        wait_command(["rosparam", "list"], environment=environment, attempts=100, process=roscore)
        run_command(
            ["rosparam", "load", str(fast_root / "config/avia.yaml"), "/"],
            environment=environment,
        )
        parameters = {
            "/use_sim_time": "true",
            "/feature_extract_enable": "false",
            "/point_filter_num": "3",
            "/max_iteration": "3",
            "/filter_size_surf": "0.5",
            "/filter_size_map": "0.5",
            "/cube_side_length": "1000.0",
            "/runtime_pos_log_enable": "false",
            "/publish/path_en": "false",
            "/publish/scan_publish_en": "false",
            "/publish/dense_publish_en": "false",
            "/publish/scan_bodyframe_pub_en": "false",
            "/pcd_save/pcd_save_en": "false",
            "/harmful_bias/runtime_mode": MODE,
            "/harmful_bias/runtime_equivalence_output_dir": str(paths.runtime_output_dir),
            "/harmful_bias/run_id": f"{RUN_ID}_{args.sequence_id}_{run_label}",
            "/harmful_bias/sequence_id": args.sequence_id,
            "/harmful_bias/bag_sha256": clip["sha256"],
            "/harmful_bias/config_bundle_sha256": config_bundle,
            "/harmful_bias/fastlio2_binary_sha256": lock["fastlio2_binary_sha256"],
            "/harmful_bias/end_of_stream_audit_enabled": "true",
        }
        for key, value in parameters.items():
            run_command(["rosparam", "set", key, value], environment=environment)
        paths.launch_path.write_text(
            '<launch>\n  <node pkg="fast_lio" type="fastlio_mapping" '
            'name="laserMapping" output="screen" required="true" />\n</launch>\n',
            encoding="utf-8",
        )
        roslaunch, handle = start_process(
            [
                "taskset",
                "-c",
                str(lock["cpu_affinity"]["fastlio2_core"]),
                "roslaunch",
                str(paths.launch_path),
            ],
            run_dir / "roslaunch.log",
            environment,
        )
        handles.append(handle)
        wait_command(
            ["rosnode", "info", "/laserMapping"],
            environment=environment,
            attempts=300,
            process=roslaunch,
        )
        actual_output = run_command(
            ["rosparam", "get", "/harmful_bias/runtime_equivalence_output_dir"],
            environment=environment,
        ).stdout.strip()
        atomic_json(
            run_dir / "runtime_output_param_audit.json",
            validate_runtime_output_param(paths.runtime_output_dir, actual_output),
        )
        run_command(
            ["rosparam", "dump", str(run_dir / "rosparams.yaml"), "/"],
            environment=environment,
        )
        (run_dir / "runtime_environment.txt").write_text(
            "\n".join(
                f"{key}={environment[key]}" for key in sorted(LOCKED_ENVIRONMENT)
            )
            + "\n",
            encoding="utf-8",
        )
        bag_command = [
            "taskset",
            "-c",
            str(lock["cpu_affinity"]["rosbag_core"]),
            "rosbag",
            "play",
            str(clip_path),
            "--pause",
            "--clock",
            "--rate",
            str(lock["playback_rate"]),
            "--queue=10000",
            "__name:=day5_bag_player",
        ]
        (run_dir / "bag_command.txt").write_text(
            " ".join(bag_command) + "\n", encoding="utf-8"
        )
        rosbag, handle = start_process(bag_command, run_dir / "rosbag.log", environment)
        handles.append(handle)
        write_state("HANDSHAKING")
        handshake = run_command(
            [
                sys.executable,
                str(ROOT / "scripts/48_wait_rosbag_connections.py"),
                "--run-id",
                RUN_ID,
                "--sequence-id",
                args.sequence_id,
                "--repeat-id",
                str(args.repeat_id),
                "--master-uri",
                environment["ROS_MASTER_URI"],
                "--stable-polls",
                "20",
                "--poll-interval",
                "0.1",
                "--timeout",
                "30",
                "--output",
                str(run_dir / "connection_handshake_v4.json"),
            ],
            environment=environment,
            output=run_dir / "connection_handshake_tool.log",
            check=False,
        )
        if handshake.returncode:
            raise RunFailure(
                "RUNTIME_PRODUCT_MISSING", "connection handshake/unpause failed"
            )
        for command, filename in (
            (["rosnode", "info", "/laserMapping"], "rosnode_info.txt"),
            (["rosnode", "info", "/day5_bag_player"], "rosnode_info_bag_player.txt"),
            (["rostopic", "info", "/livox/lidar"], "rostopic_info_livox_lidar.txt"),
            (["rostopic", "info", "/livox/imu"], "rostopic_info_livox_imu.txt"),
            (["rosservice", "list"], "rosservice_list.txt"),
        ):
            run_command(command, environment=environment, output=run_dir / filename)
        write_state("PLAYING")
        duration = (
            max(endpoint["last_lidar_bag_time_ns"], endpoint["last_imu_bag_time_ns"])
            - min(endpoint["first_lidar_bag_time_ns"], endpoint["first_imu_bag_time_ns"])
        ) / 1e9
        try:
            rosbag_exit = rosbag.wait(
                timeout=duration / float(lock["playback_rate"]) + 120
            )
        except subprocess.TimeoutExpired as error:
            raise RunFailure("RUNTIME_PRODUCT_MISSING", "rosbag timeout") from error
        if rosbag_exit != 0:
            raise RunFailure("RUNTIME_PRODUCT_MISSING", f"rosbag exit {rosbag_exit}")
        write_state("DRAINING")
        drain = run_command(
            [
                sys.executable,
                str(ROOT / "scripts/55_wait_fastlio2_end_of_stream_drain.py"),
                "--endpoint-contract",
                str(endpoint_path),
                "--sequence-id",
                args.sequence_id,
                "--run-id",
                RUN_ID,
                "--repeat-id",
                str(args.repeat_id),
                "--master-uri",
                environment["ROS_MASTER_URI"],
                "--service-name",
                lock["drain_service_name"],
                "--stable-poll-count",
                str(lock["stable_poll_count"]),
                "--poll-interval",
                str(lock["poll_interval_sec"]),
                "--timeout",
                str(lock["drain_timeout_sec"]),
                "--output",
                str(run_dir / "end_of_stream_drain.json"),
                "--trace-output",
                str(run_dir / "end_of_stream_drain_poll_trace.csv"),
            ],
            environment=environment,
            output=run_dir / "end_of_stream_drain_tool.log",
            check=False,
        )
        if drain.returncode:
            drain_result = json.loads(
                (run_dir / "end_of_stream_drain.json").read_text(encoding="utf-8")
            )
            raise RunFailure(
                drain_result.get("failure_classification", "END_OF_STREAM_DRAIN_TIMEOUT"),
                drain_result.get("message", "end-of-stream drain failed"),
            )
        time.sleep(0.25)
        write_state("SHUTTING_DOWN")
        shutdown = graceful_shutdown(
            roslaunch, environment=environment, run_dir=run_dir
        )
        roslaunch = None
    finally:
        stop_process(rosbag)
        stop_process(roslaunch)
        stop_process(roscore)
        for handle in handles:
            handle.close()
    if shutdown is None:
        raise RunFailure(
            "RUNTIME_NODE_SHUTDOWN_INCOMPLETE", "shutdown evidence missing"
        )
    write_state("VALIDATING_PRODUCTS")
    product_path = run_dir / "runtime_product_validation_v4.json"
    product = run_command(
        [
            sys.executable,
            str(ROOT / "scripts/53_validate_runtime_audit_products.py"),
            "--run-dir",
            str(run_dir),
            "--converted-dir",
            str(run_dir / "converted"),
            "--output",
            str(product_path),
        ],
        environment=environment,
        output=run_dir / "runtime_product_validation_tool.log",
        check=False,
    )
    if product.returncode:
        details = (
            json.loads(product_path.read_text(encoding="utf-8"))
            if product_path.is_file()
            else {}
        )
        raise RunFailure(
            details.get("failure_classification", "RUNTIME_PRODUCT_MISSING"),
            details.get("message", "runtime product validation failed"),
        )
    frames_path = run_dir / "converted/runtime_frames.csv"
    with frames_path.open(encoding="utf-8") as stream:
        scan_count = max(0, sum(1 for _ in stream) - 1)
    conversion = json.loads(
        (run_dir / "converted/binary_conversion_summary.json").read_text(
            encoding="utf-8"
        )
    )
    product_result = json.loads(product_path.read_text(encoding="utf-8"))
    drain_result = json.loads(
        (run_dir / "end_of_stream_drain.json").read_text(encoding="utf-8")
    )
    metadata = {
        "run_id": f"{RUN_ID}_{args.sequence_id}_{run_label}",
        "phase_run_id": RUN_ID,
        "sequence_id": args.sequence_id,
        "runtime_mode": MODE,
        "repeat_id": args.repeat_id,
        "local_alias": clip["alias"],
        "bag_sha256": clip["sha256"],
        "playback_rate": lock["playback_rate"],
        "use_clock": True,
        "ros_master_port": ros_port,
        "rosbag_exit_code": rosbag_exit,
        "rosbag_natural_exit": True,
        "laser_mapping_exit_code": shutdown["laser_mapping_exit_code"],
        "roslaunch_exit_code": shutdown["roslaunch_exit_code"],
        "shutdown_completed": shutdown["shutdown_completed"],
        "runtime_audit_row_count": scan_count,
        "observation_record_count": conversion["observation_record_count"],
        "fastlio2_binary_sha256_before": lock["fastlio2_binary_sha256"],
        "fastlio2_binary_sha256_after": sha256_file(binary),
        "config_bundle_sha256": config_bundle,
        "runtime_output_dir": str(paths.runtime_output_dir),
        "runtime_product_pass": product_result["runtime_product_pass"],
        "runtime_binary_trailer_pass": product_result["runtime_binary_trailer_pass"],
        "end_of_stream_drain_pass": drain_result["drain_pass"],
        "final_processed_measure_group_count": drain_result[
            "final_processed_measure_group_count"
        ],
        "unprocessed_lidar_tail_count": drain_result[
            "unprocessed_lidar_tail_count"
        ],
        "remaining_imu_count": drain_result["remaining_imu_count"],
    }
    atomic_json(run_dir / "run_metadata.json", metadata)
    after_run = runtime_output_inventory(fast_root)
    runtime_audit = compare_runtime_inventories(after_clear, after_run)
    atomic_json(run_dir / "runtime_output_allowlist_audit.json", runtime_audit)
    if not runtime_audit["allowlist_pass"]:
        raise RunFailure(
            "RUNTIME_PRODUCT_MISSING", "unexpected FAST runtime output changed"
        )
    source_lock_result(
        lock,
        run_root,
        run_dir / "post_run_source_binary_clip_lock.json",
    )
    write_state("COMPLETED", terminal_result=metadata)
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sequence-id", required=True, choices=SEQUENCES)
    parser.add_argument("--repeat-id", required=True, type=int, choices=REPEATS)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--endpoint-contract", required=True, type=Path)
    parser.add_argument("--run-lock", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.run_id != RUN_ID:
        raise SystemExit("ERROR: only multihyp_day5_startup_sync_v4 is allowed")
    def interrupt_runner(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, interrupt_runner)
    signal.signal(signal.SIGTERM, interrupt_runner)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    identity = {
        "run_id": RUN_ID,
        "sequence_id": args.sequence_id,
        "repeat_id": args.repeat_id,
        "runtime_mode": MODE,
    }
    run_state = (
        args.run_root.expanduser().resolve()
        / "runs/baseline"
        / args.sequence_id
        / f"AUDIT_ONLY_R{args.repeat_id}"
        / "single_run_state.json"
    )
    try:
        execute(args)
        return 0
    except KeyboardInterrupt:
        if run_state.parent.exists():
            state_writer(run_state, identity)("INTERRUPTED")
        return 130
    except RunFailure as error:
        if run_state.parent.exists():
            state_writer(run_state, identity)(
                "FAILED",
                failure_classification=error.classification,
                message=str(error),
            )
            atomic_json(
                run_state.parent / "single_run_failure.json",
                {
                    **identity,
                    "failure_classification": error.classification,
                    "message": str(error),
                },
            )
        return 30


if __name__ == "__main__":
    raise SystemExit(main())
