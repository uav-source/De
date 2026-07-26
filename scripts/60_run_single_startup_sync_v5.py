#!/usr/bin/env python3
"""Run one Git-locked Day 5 V5 AUDIT_ONLY replay with tail-clock handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import xmlrpc.client
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.replay_endpoint_contract import sequence_contract  # noqa: E402
from fastlio2_adapter.end_of_stream_drain import (  # noqa: E402
    bounded_trigger_call,
)
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
from fastlio2_adapter.tail_clock_protocol import (  # noqa: E402
    BAG_PLAYER_NODE,
    NODE_NAME as TAIL_CLOCK_NODE,
    START_SERVICE as TAIL_CLOCK_START_SERVICE,
    STATUS_SERVICE as TAIL_CLOCK_STATUS_SERVICE,
    STOP_SERVICE as TAIL_CLOCK_STOP_SERVICE,
    TAIL_CLOCK_STEP_NS,
    validate_status as validate_tail_clock_status,
)


RUN_ID = "multihyp_day5_startup_sync_v5"
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
_ACTIVE_HEARTBEAT: "RunnerHeartbeat | None" = None


class RunFailure(RuntimeError):
    def __init__(self, classification: str, message: str) -> None:
        super().__init__(message)
        self.classification = classification


class RunnerHeartbeat:
    def __init__(self, path: Path, identity: Mapping[str, Any]) -> None:
        self.path = path
        self.identity = dict(identity)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(
            target=self._run,
            name="day5-v5-runner-heartbeat",
            daemon=False,
        )
        self.count = 0

    def start(self) -> None:
        self.thread.start()

    def _run(self) -> None:
        while not self.stop_event.is_set():
            self.count += 1
            atomic_json(
                self.path,
                {
                    **self.identity,
                    "runner_pid": os.getpid(),
                    "heartbeat_count": self.count,
                    "last_heartbeat_monotonic_ns": time.monotonic_ns(),
                },
            )
            self.stop_event.wait(5.0)

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=6.0)


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


def clock_publishers(master_uri: str) -> list[str]:
    master = xmlrpc.client.ServerProxy(master_uri, allow_none=True)
    code, _message, system_state = master.getSystemState(
        "/day5_startup_sync_v5_runner"
    )
    if int(code) != 1:
        raise RunFailure(
            "TAIL_CLOCK_START_FAILURE",
            "cannot read ROS master publisher state",
        )
    publishers = {topic: names for topic, names in system_state[0]}
    return sorted(set(publishers.get("/clock", [])))


def wait_for_bag_clock_release(
    *,
    master_uri: str,
    timeout_sec: float = 15.0,
) -> dict[str, Any]:
    started = time.monotonic_ns()
    deadline = started + int(timeout_sec * 1_000_000_000)
    last_publishers: list[str] = []
    while time.monotonic_ns() <= deadline:
        last_publishers = clock_publishers(master_uri)
        if BAG_PLAYER_NODE not in last_publishers and not last_publishers:
            ready = time.monotonic_ns()
            return {
                "bag_clock_publisher_disappear_start_ns": started,
                "bag_clock_publisher_disappear_ready_ns": ready,
                "clock_publishers_before_handoff": last_publishers,
            }
        time.sleep(0.02)
    if BAG_PLAYER_NODE in last_publishers:
        classification = "TAIL_CLOCK_BAG_PUBLISHER_STILL_ACTIVE"
    else:
        classification = "TAIL_CLOCK_UNKNOWN_PUBLISHER_PRESENT"
    raise RunFailure(
        classification,
        f"clock publisher did not release: {last_publishers}",
    )


def trigger_status(
    service_name: str,
    *,
    environment: Mapping[str, str],
    timeout_sec: float,
    failure_classification: str = "TAIL_CLOCK_START_FAILURE",
) -> dict[str, Any]:
    poll = bounded_trigger_call(
        service_name,
        environment=environment,
        timeout_sec=timeout_sec,
    )
    if poll.snapshot is None:
        raise RunFailure(
            failure_classification,
            str(
                poll.evidence.get("service_exception")
                or f"Trigger call failed: {service_name}"
            ),
        )
    try:
        return validate_tail_clock_status(dict(poll.snapshot))
    except ValueError as error:
        raise RunFailure(
            failure_classification,
            f"invalid tail-clock status: {error}",
        ) from error


def write_tail_handoff(
    path: Path,
    identity: Mapping[str, Any],
    runner_evidence: Mapping[str, Any],
    node_status: Mapping[str, Any] | None,
) -> None:
    atomic_json(
        path,
        {
            **identity,
            **dict(runner_evidence),
            **(dict(node_status) if node_status is not None else {}),
        },
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
    atomic_json(run_dir / "graceful_shutdown_v5.json", result)
    if not result["shutdown_completed"]:
        raise RunFailure(
            "NORMAL_SHUTDOWN_FAILURE",
            "laserMapping did not complete normal shutdown",
        )
    return result


def execute(args: argparse.Namespace) -> dict[str, Any]:
    global _ACTIVE_HEARTBEAT
    run_root = args.run_root.expanduser().resolve()
    endpoint_path = args.endpoint_contract.expanduser().resolve()
    lock_path = args.run_lock.expanduser().resolve()
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    contract_bytes = endpoint_path.read_bytes()
    contract = json.loads(contract_bytes)
    endpoint = sequence_contract(contract, args.sequence_id)
    if lock.get("run_id") != RUN_ID:
        raise RunFailure("SOURCE_LOCK_CHANGED", "wrong V5 run lock")
    if lock.get("endpoint_contract_sha256") != hashlib.sha256(contract_bytes).hexdigest():
        raise RunFailure("SOURCE_LOCK_CHANGED", "endpoint contract SHA mismatch")
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
    _ACTIVE_HEARTBEAT = RunnerHeartbeat(
        run_dir / "single_run_heartbeat.json",
        {
            "run_id": RUN_ID,
            "sequence_id": args.sequence_id,
            "repeat_id": args.repeat_id,
            "runtime_mode": MODE,
        },
    )
    _ACTIVE_HEARTBEAT.start()
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
    ros_port = 20200 + sequence_slot * 10 + args.repeat_id
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
    roscore = roslaunch = rosbag = tail_clock = None
    handles: list[Any] = []
    rosbag_exit: int | None = None
    shutdown: dict[str, Any] | None = None
    tail_status: dict[str, Any] | None = None
    tail_runner_evidence: dict[str, Any] = {}
    tail_started = False
    tail_stopped = False
    tail_state_path = run_dir / "tail_clock_node_state.json"
    handoff_path = run_dir / "tail_clock_handoff.json"
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
        tail_clock, handle = start_process(
            [
                sys.executable,
                str(ROOT / "scripts/59_day5_tail_clock_node.py"),
                "--state-output",
                str(tail_state_path),
            ],
            run_dir / "tail_clock_node.log",
            environment,
        )
        handles.append(handle)
        wait_command(
            ["rosservice", "info", TAIL_CLOCK_STATUS_SERVICE],
            environment=environment,
            attempts=200,
            process=tail_clock,
        )
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
                str(run_dir / "connection_handshake_v5.json"),
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
        bag_exit_ns = time.monotonic_ns()
        tail_runner_evidence = {
            "bag_player_exit_monotonic_ns": bag_exit_ns,
            **wait_for_bag_clock_release(
                master_uri=environment["ROS_MASTER_URI"],
            ),
        }
        write_state("TAIL_CLOCK_HANDOFF")
        tail_status = trigger_status(
            lock["tail_clock_start_service"],
            environment=environment,
            timeout_sec=10.0,
        )
        tail_started = bool(tail_status["start_success"])
        write_tail_handoff(
            handoff_path,
            {
                "run_id": RUN_ID,
                "sequence_id": args.sequence_id,
                "repeat_id": args.repeat_id,
            },
            tail_runner_evidence,
            tail_status,
        )
        if not tail_started:
            raise RunFailure(
                str(tail_status.get("failure_reason") or "TAIL_CLOCK_START_FAILURE"),
                "tail-clock start did not pass",
            )
        if (
            int(tail_status["tail_first_clock_ns"])
            != int(tail_status["last_bag_clock_ns"]) + TAIL_CLOCK_STEP_NS
        ):
            raise RunFailure(
                "TAIL_CLOCK_START_FAILURE",
                "first tail clock is not last bag clock plus fixed step",
            )
        if int(tail_status["clock_publisher_overlap_count"]) != 0:
            raise RunFailure(
                "TAIL_CLOCK_PUBLISHER_OVERLAP",
                "clock publisher overlap observed at handoff",
            )
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
                "--service-call-timeout",
                str(lock["service_call_timeout_sec"]),
                "--max-consecutive-service-timeouts",
                str(lock["max_consecutive_service_timeouts"]),
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
        drain_result = json.loads(
            (run_dir / "end_of_stream_drain.json").read_text(encoding="utf-8")
        )
        if (
            int(drain_result["main_loop_heartbeat_end"])
            <= int(drain_result["main_loop_heartbeat_start"])
        ):
            raise RunFailure(
                "TAIL_CLOCK_MAIN_LOOP_NOT_PROGRESSING",
                "FAST main-loop heartbeat did not advance under tail-clock",
            )
        time.sleep(0.25)
        write_state("SHUTTING_DOWN")
        shutdown = graceful_shutdown(
            roslaunch, environment=environment, run_dir=run_dir
        )
        roslaunch = None
        tail_status = trigger_status(
            lock["tail_clock_stop_service"],
            environment=environment,
            timeout_sec=10.0,
            failure_classification="TAIL_CLOCK_STOP_FAILURE",
        )
        tail_stopped = bool(
            tail_status["stop_success"] and tail_status["handoff_pass"]
        )
        write_tail_handoff(
            handoff_path,
            {
                "run_id": RUN_ID,
                "sequence_id": args.sequence_id,
                "repeat_id": args.repeat_id,
            },
            tail_runner_evidence,
            tail_status,
        )
        if not tail_stopped:
            raise RunFailure(
                str(tail_status.get("failure_reason") or "TAIL_CLOCK_STOP_FAILURE"),
                "tail-clock stop/handoff did not pass",
            )
        try:
            tail_exit = tail_clock.wait(timeout=10)
        except subprocess.TimeoutExpired as error:
            raise RunFailure(
                "TAIL_CLOCK_STOP_FAILURE",
                "tail-clock process did not exit after stop",
            ) from error
        if tail_exit != 0:
            raise RunFailure(
                "TAIL_CLOCK_STOP_FAILURE",
                f"tail-clock process exit code {tail_exit}",
            )
        tail_clock = None
    finally:
        stop_process(rosbag)
        if tail_clock is not None and tail_clock.poll() is None:
            if tail_started and not tail_stopped:
                try:
                    cleanup_status = trigger_status(
                        TAIL_CLOCK_STOP_SERVICE,
                        environment=environment,
                        timeout_sec=5.0,
                        failure_classification="TAIL_CLOCK_STOP_FAILURE",
                    )
                    tail_status = cleanup_status
                    tail_stopped = bool(cleanup_status.get("stop_success"))
                except Exception:
                    pass
            stop_process(tail_clock)
        if tail_state_path.is_file():
            try:
                tail_status = json.loads(
                    tail_state_path.read_text(encoding="utf-8")
                )
                validate_tail_clock_status(tail_status)
            except Exception:
                pass
            write_tail_handoff(
                handoff_path,
                {
                    "run_id": RUN_ID,
                    "sequence_id": args.sequence_id,
                    "repeat_id": args.repeat_id,
                },
                tail_runner_evidence,
                tail_status,
            )
        stop_process(roslaunch)
        stop_process(roscore)
        for handle in handles:
            handle.close()
    if shutdown is None:
        raise RunFailure(
            "NORMAL_SHUTDOWN_FAILURE", "shutdown evidence missing"
        )
    write_state("VALIDATING_PRODUCTS")
    product_path = run_dir / "runtime_product_validation_v5.json"
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
    tail_result = json.loads(handoff_path.read_text(encoding="utf-8"))
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
        "tail_clock_handoff_pass": tail_result["handoff_pass"],
        "last_bag_clock_ns": tail_result["last_bag_clock_ns"],
        "tail_first_clock_ns": tail_result["tail_first_clock_ns"],
        "tail_publish_count": tail_result["tail_publish_count"],
        "tail_final_clock_ns": tail_result["tail_final_clock_ns"],
        "clock_publisher_overlap_count": tail_result[
            "clock_publisher_overlap_count"
        ],
        "clock_duplicate_count": tail_result["clock_duplicate_count"],
        "clock_backward_count": tail_result["clock_backward_count"],
        "end_of_stream_drain_pass": drain_result["drain_pass"],
        "service_call_timeout_count": drain_result[
            "service_call_timeout_count"
        ],
        "max_consecutive_service_timeouts": drain_result[
            "max_consecutive_service_timeouts"
        ],
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
    global _ACTIVE_HEARTBEAT
    args = parse_args()
    if args.run_id != RUN_ID:
        raise SystemExit("ERROR: only multihyp_day5_startup_sync_v5 is allowed")
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
    finally:
        if _ACTIVE_HEARTBEAT is not None:
            _ACTIVE_HEARTBEAT.stop()
            _ACTIVE_HEARTBEAT = None


if __name__ == "__main__":
    raise SystemExit(main())
