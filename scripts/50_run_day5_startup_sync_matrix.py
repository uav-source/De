#!/usr/bin/env python3
"""Run and summarize the Git-locked Day 5 startup-sync V3 matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.source_lock import (
    clear_allowed_runtime_outputs,
    compare_runtime_inventories,
    runtime_output_inventory,
    sha256_file,
    snapshot_source_lock,
    source_lock_mismatches,
    write_json,
)
from fastlio2_adapter.runtime_paths import (
    RuntimePathError,
    build_runtime_paths,
    resolve_runtime_path,
    validate_runtime_output_param,
)


RUN_ID = "multihyp_day5_startup_sync_v3"
SEQUENCES = ("avia_quick_shack", "avia_outdoor_run_100hz")
REPEATS = (1, 2, 3)
MODE = "AUDIT_ONLY"
TOLERANCE = 1e-12
HANDSHAKE_PROTOCOL_VERSION = "DAY5_STARTUP_SYNC_TCPROS_V3_MONOTONIC_UNPAUSE"
EXPECTED_BINARY_SHA256 = "59deeb5302c3c575b04d6cb65b9decdd3e9042eb5d70447f5cc4ee4227d3c136"
CLIPS = {
    "avia_quick_shack": {
        "alias": "avia_quick_shack.replay.bag",
        "path": "$HOME/harmful_bias_replay_clips/day5_startup_sync_v1/avia_quick_shack.replay.bag",
        "sha256": "272325265978787c838e010b1f0da963a15fb4b08ff8730fc3dd9901e32a0e20",
        "original_bag_sha256": "05a56e75898f952766f136d1e5db64a35d202e990e3b1052558369d8384d7ffe",
        "duration_seconds": 50.001004,
    },
    "avia_outdoor_run_100hz": {
        "alias": "avia_outdoor_run_100hz.replay.bag",
        "path": "$HOME/harmful_bias_replay_clips/day5_startup_sync_v1/avia_outdoor_run_100hz.replay.bag",
        "sha256": "087c552c9c62be37b42d218323383459df8791ce6514fa7b3425f7bab5021284",
        "original_bag_sha256": "13bde5d88ce054d88904873e924e2619153efdf5b63df7f3bbab4f16eb72a253",
        "duration_seconds": 63.857759,
    },
}
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


class MatrixFailure(RuntimeError):
    def __init__(self, classification: str, message: str) -> None:
        super().__init__(message)
        self.classification = classification


def locked_path(value: str, root: Path | None = None) -> Path:
    path = Path(os.path.expandvars(value))
    return path if path.is_absolute() or root is None else root / path


def fixed_replay_plan() -> list[dict[str, Any]]:
    return [
        {"sequence_id": sequence, "repeat_id": repeat, "mode": MODE}
        for sequence in SEQUENCES
        for repeat in REPEATS
    ]


def validate_replay_plan(plan: Iterable[Mapping[str, Any]]) -> None:
    if [dict(row) for row in plan] != fixed_replay_plan():
        raise ValueError("startup-sync V3 replay plan must be the fixed six-run AUDIT_ONLY matrix")


def build_handshake_command(
    *, root: Path, run_id: str, sequence_id: str, repeat_id: int,
    master_uri: str, output: Path,
) -> list[str]:
    if run_id != RUN_ID or sequence_id not in SEQUENCES or repeat_id not in REPEATS:
        raise ValueError("unsupported startup-sync V3 handshake identity")
    return [
        sys.executable,
        str(root / "scripts/48_wait_rosbag_connections.py"),
        "--run-id", run_id,
        "--sequence-id", sequence_id,
        "--repeat-id", str(repeat_id),
        "--master-uri", master_uri,
        "--stable-polls", "20",
        "--poll-interval", "0.1",
        "--timeout", "30",
        "--output", str(output),
    ]


def first_ten_signature(rows: list[dict[str, str]]) -> str:
    selected = [
        {
            "scan_index": row["scan_index"],
            "measure_group_checksum": row["measure_group_checksum"],
            "timestamp_begin": row["timestamp_begin"],
            "lidar_point_count": row["lidar_point_count"],
            "imu_message_count": row["imu_message_count"],
        }
        for row in rows[:10]
    ]
    return hashlib.sha256(
        json.dumps(selected, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def startup_boundary_pass(records: Iterable[Mapping[str, Any]]) -> bool:
    by_sequence: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        by_sequence.setdefault(str(record["sequence_id"]), []).append(record)
    fields = (
        "scan_count",
        "first_runtime_scan_index",
        "first_measure_group_checksum",
        "first_measure_group_lidar_begin_time",
        "first_measure_group_lidar_end_time",
        "first_measure_group_lidar_point_count",
        "first_measure_group_imu_message_count",
        "first_measure_group_first_imu_timestamp",
        "first_measure_group_last_imu_timestamp",
        "first_ten_signature_sha256",
    )
    return set(by_sequence) == set(SEQUENCES) and all(
        len(rows) == 3 and all(len({row[field] for row in rows}) == 1 for field in fields)
        for rows in by_sequence.values()
    )


def matrix_status(value: bool, completed: bool) -> str:
    return "PASS" if completed and value else "FAIL" if completed else "NOT_EVALUATED"


def evaluate_startup_sync_v3_gate(values: Mapping[str, Any]) -> dict[str, Any]:
    complete = values.get("successful_replay_count") == 6 and values.get("evaluated_pair_count") == 6
    boolean_fields = {
        "CLIP_BAG_FREEZE_STATUS": bool(values.get("clip_lock_pass")),
        "CONNECTION_HANDSHAKE_STATUS": bool(values.get("connection_handshake_pass")),
        "PAUSED_START_STATUS": bool(values.get("paused_start_pass")),
        "RUNTIME_OUTPUT_CONTRACT_STATUS": bool(values.get("runtime_output_contract_pass")),
        "EXPECTED_RUNTIME_OUTPUT_ALLOWLIST_STATUS": bool(values.get("runtime_allowlist_pass")),
        "RUNTIME_OUTPUT_ABSOLUTE_PATH_STATUS": bool(values.get("runtime_output_absolute_path_pass")),
        "RUNTIME_BINARY_COMPLETENESS_STATUS": bool(values.get("runtime_binary_completeness_pass")),
        "STARTUP_INPUT_BOUNDARY_STATUS": bool(values.get("startup_input_boundary_pass")),
        "SOURCE_LOCK_STATUS": bool(values.get("source_lock_pass")),
        "BINARY_LOCK_STATUS": bool(values.get("binary_lock_pass")),
        "PARAMETER_IDENTITY_STATUS": bool(values.get("parameter_identity_pass")),
        "SCAN_PAIRING_STATUS": bool(values.get("scan_pairing_pass")),
        "MEASURE_GROUP_EQUIVALENCE_STATUS": bool(values.get("measure_group_equivalence_pass")),
        "POSE_EQUIVALENCE_STATUS": bool(values.get("pose_equivalence_pass")),
        "COVARIANCE_EQUIVALENCE_STATUS": bool(values.get("covariance_equivalence_pass")),
        "FORMAL_JACOBIAN_EQUIVALENCE_STATUS": bool(values.get("jacobian_equivalence_pass")),
        "FORMAL_RESIDUAL_EQUIVALENCE_STATUS": bool(values.get("residual_equivalence_pass")),
        "ACCEPTED_INDEX_EQUIVALENCE_STATUS": bool(values.get("accepted_index_equivalence_pass")),
        "CORRESPONDENCE_EQUIVALENCE_STATUS": bool(values.get("correspondence_equivalence_pass")),
        "MAP_SIZE_EQUIVALENCE_STATUS": bool(values.get("map_size_equivalence_pass")),
        "FINAL_MAP_EQUIVALENCE_STATUS": bool(values.get("final_map_equivalence_pass")),
        "NO_NONFINITE_STATUS": bool(values.get("no_nonfinite_pass")),
        "NO_GT_RUNTIME_STATUS": bool(values.get("no_gt_runtime_pass")),
    }
    statuses = {name: matrix_status(value, complete) for name, value in boolean_fields.items()}
    passed = complete and all(boolean_fields.values())
    return {
        **statuses,
        "executed_run_count": int(values.get("executed_replay_count", 0)),
        "executed_run_handshake_pass_count": int(values.get("executed_handshake_pass_count", 0)),
        "executed_run_paused_start_pass_count": int(values.get("executed_paused_start_pass_count", 0)),
        "executed_run_runtime_product_pass_count": int(values.get("executed_runtime_product_pass_count", 0)),
        "RUNTIME_OUTPUT_CONTRACT_PASS": passed and boolean_fields["RUNTIME_OUTPUT_CONTRACT_STATUS"],
        "EXPECTED_RUNTIME_OUTPUT_ALLOWLIST_PASS": passed and boolean_fields["EXPECTED_RUNTIME_OUTPUT_ALLOWLIST_STATUS"],
        "RUNTIME_OUTPUT_ABSOLUTE_PATH_PASS": passed and boolean_fields["RUNTIME_OUTPUT_ABSOLUTE_PATH_STATUS"],
        "RUNTIME_BINARY_COMPLETENESS_PASS": passed and boolean_fields["RUNTIME_BINARY_COMPLETENESS_STATUS"],
        "STARTUP_INPUT_BOUNDARY_PASS": passed and boolean_fields["STARTUP_INPUT_BOUNDARY_STATUS"],
        "BASELINE_REPEATABILITY_PASS": passed,
        "DAY5_STARTUP_SYNC_V3_PASS": passed,
        "DAY5_CAPTURE_EXPORT_REMEDIATION_AUTHORIZED": passed,
        "DAY5_RUNTIME_EQUIVALENCE_PASS": False,
        "OFF_ON_REPLAY_EQUIVALENCE_STATUS": "NOT_REEVALUATED_STARTUP_SYNC_ONLY",
        "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED": False,
    }


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row}) if rows else ["status"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _contains_nonfinite(rows: Iterable[Mapping[str, str]]) -> bool:
    forbidden = {"nan", "+nan", "-nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}
    return any(
        token.lower() in forbidden
        for row in rows
        for value in row.values()
        for token in re.findall(r"[+-]?(?:nan|inf(?:inity)?)", str(value), re.IGNORECASE)
    )


def _ros_environment(fast_ws: Path) -> dict[str, str]:
    command = (
        "source /opt/ros/noetic/setup.bash && "
        f"source {shlex_quote(str(fast_ws / 'devel/setup.bash'))} && env -0"
    )
    completed = subprocess.run(["bash", "-c", command], stdout=subprocess.PIPE, check=True)
    environment = dict(os.environ)
    for row in completed.stdout.split(b"\0"):
        if b"=" in row:
            key, value = row.split(b"=", 1)
            environment[key.decode()] = value.decode()
    environment.update(LOCKED_ENVIRONMENT)
    return environment


def shlex_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _run(
    command: Sequence[str], *, environment: Mapping[str, str],
    output: Path | None = None, check: bool = True,
) -> subprocess.CompletedProcess[Any]:
    if output is None:
        return subprocess.run(list(command), env=dict(environment), check=check, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        return subprocess.run(list(command), env=dict(environment), check=check, stdout=stream, stderr=subprocess.STDOUT, text=True)


def _capture(command: Sequence[str], path: Path, environment: Mapping[str, str]) -> None:
    completed = _run(command, environment=environment, check=False)
    path.write_text(completed.stdout or "", encoding="utf-8")
    if completed.returncode:
        raise MatrixFailure("ROSBAG_SUBSCRIBER_HANDSHAKE_FAILURE", f"command failed: {' '.join(command)}")


def _start(command: Sequence[str], log_path: Path, environment: Mapping[str, str]) -> tuple[subprocess.Popen[Any], Any]:
    handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        list(command), env=dict(environment), stdout=handle, stderr=subprocess.STDOUT,
        text=True, start_new_session=True,
    )
    return process, handle


def _stop(process: subprocess.Popen[Any] | None, timeout: float = 20.0) -> int | None:
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


def graceful_shutdown_roslaunch(
    process: subprocess.Popen[Any],
    *,
    environment: Mapping[str, str],
    run_dir: Path,
    timeout: float = 30.0,
) -> dict[str, Any]:
    started = time.monotonic_ns()
    request = subprocess.run(
        ["rosnode", "kill", "/laserMapping"],
        env=dict(environment),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    (run_dir / "rosnode_shutdown.txt").write_text(
        request.stdout or "", encoding="utf-8"
    )
    method = "rosnode kill /laserMapping"
    if request.returncode:
        method = "roslaunch process group SIGINT"
        try:
            os.killpg(process.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
    forced_terminate = False
    forced_kill = False
    try:
        exit_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        forced_terminate = True
        process.terminate()
        try:
            exit_code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            forced_kill = True
            process.kill()
            exit_code = process.wait(timeout=5)
    completed = not forced_terminate and not forced_kill
    result = {
        "rosbag_natural_exit": True,
        "shutdown_request_method": method,
        "shutdown_request_monotonic_ns": started,
        "laser_mapping_exit_code": 0 if request.returncode == 0 else None,
        "roslaunch_exit_code": exit_code,
        "shutdown_completed": completed,
        "shutdown_duration_ms": (time.monotonic_ns() - started) / 1_000_000.0,
        "forced_terminate_used": forced_terminate,
        "forced_kill_used": forced_kill,
    }
    write_json(run_dir / "graceful_shutdown_v3.json", result)
    if not completed:
        raise MatrixFailure(
            "RUNTIME_NODE_SHUTDOWN_INCOMPLETE",
            "laserMapping/roslaunch did not complete normal shutdown",
        )
    return result


def _wait_command(
    command: Sequence[str], *, environment: Mapping[str, str],
    attempts: int, process: subprocess.Popen[Any] | None = None,
) -> None:
    for _ in range(attempts):
        completed = subprocess.run(list(command), env=dict(environment), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if completed.returncode == 0:
            return
        if process is not None and process.poll() is not None:
            raise MatrixFailure("ROSBAG_SUBSCRIBER_HANDSHAKE_FAILURE", f"process exited while waiting for {' '.join(command)}")
        time.sleep(0.1)
    raise MatrixFailure("ROSBAG_SUBSCRIBER_HANDSHAKE_FAILURE", f"timeout waiting for {' '.join(command)}")


def _source_lock_result(
    lock: Mapping[str, Any], root: Path, run_root: Path, output: Path,
) -> dict[str, Any]:
    fast_root = locked_path(lock["fastlio2_root"])
    binary = locked_path(lock["binary_path"])
    degen_expected = json.loads((run_root / lock["degen_source_lock_path"]).read_text(encoding="utf-8"))
    fast_expected = json.loads((run_root / lock["fastlio2_source_lock_path"]).read_text(encoding="utf-8"))
    degen_actual = snapshot_source_lock(root, repo_alias="Degen-LIO")
    fast_actual = snapshot_source_lock(
        fast_root, repo_alias="FAST_LIO", binary_path=binary,
        binary_path_alias=lock["fastlio2_binary_path_alias"],
    )
    degen_mismatches = source_lock_mismatches(degen_expected, degen_actual)
    fast_mismatches = source_lock_mismatches(fast_expected, fast_actual)
    binary_actual = sha256_file(binary) if binary.is_file() else None
    clip_results = {}
    for sequence, definition in lock["clips"].items():
        path = locked_path(definition["path"])
        actual = sha256_file(path) if path.is_file() else None
        clip_results[sequence] = {
            "sha256": actual,
            "match": actual == definition["sha256"],
            "read_only": path.is_file() and path.stat().st_mode & 0o222 == 0,
        }
    result = {
        "source_lock_pass": not degen_mismatches and not fast_mismatches,
        "degen_source_lock_pass": not degen_mismatches,
        "fastlio2_source_lock_pass": not fast_mismatches,
        "degen_mismatches": degen_mismatches,
        "fastlio2_mismatches": fast_mismatches,
        "binary_sha256": binary_actual,
        "binary_lock_pass": binary_actual == lock["fastlio2_binary_sha256"],
        "clip_results": clip_results,
        "clip_lock_pass": all(row["match"] and row["read_only"] for row in clip_results.values()),
    }
    write_json(output, result)
    if not result["source_lock_pass"]:
        raise MatrixFailure("SOURCE_LOCK_CHANGED", f"source lock mismatch; see {output}")
    if not result["binary_lock_pass"]:
        raise MatrixFailure("BINARY_CHANGED", f"binary lock mismatch; see {output}")
    if not result["clip_lock_pass"]:
        raise MatrixFailure("CLIP_CHANGED", f"clip lock mismatch; see {output}")
    return result


def execute_replay(
    *, lock: Mapping[str, Any], root: Path, run_root: Path,
    phase_root: Path, sequence: str, repeat: int,
) -> dict[str, Any]:
    run_label = f"AUDIT_ONLY_R{repeat}"
    fast_root = locked_path(lock["fastlio2_root"]).resolve(strict=False)
    fast_ws = locked_path(lock["fastlio2_ws"]).resolve(strict=False)
    binary = locked_path(lock["binary_path"]).resolve(strict=False)
    clip = lock["clips"][sequence]
    clip_path = locked_path(clip["path"]).resolve(strict=False)
    try:
        paths = build_runtime_paths(
            run_root=run_root,
            phase_root=phase_root,
            run_dir=phase_root / sequence / run_label,
            clip_path=clip_path,
            binary_path=binary,
        )
    except RuntimePathError as error:
        raise MatrixFailure("RUNTIME_OUTPUT_PATH_INVALID", str(error)) from error
    run_dir = paths.run_dir
    if run_dir.exists():
        raise MatrixFailure("SOURCE_LOCK_CHANGED", f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    paths.ros_home.mkdir()
    paths.ros_log_dir.mkdir()
    write_json(run_dir / "absolute_path_audit.json", paths.audit())

    before_clear = runtime_output_inventory(fast_root)
    write_json(run_dir / "runtime_output_inventory_before_clear.json", before_clear)
    clear_actions = clear_allowed_runtime_outputs(fast_root)
    write_json(run_dir / "runtime_output_clear_actions.json", {"actions": clear_actions})
    after_clear = runtime_output_inventory(fast_root)
    write_json(run_dir / "runtime_output_inventory_after_clear.json", after_clear)
    clear_audit = compare_runtime_inventories(before_clear, after_clear)
    write_json(run_dir / "runtime_output_clear_allowlist_audit.json", clear_audit)
    if not clear_audit["allowlist_pass"]:
        raise MatrixFailure("RUNTIME_OUTPUT_ALLOWLIST_INCOMPLETE", "runtime clear changed a non-allowlisted file")
    _source_lock_result(lock, root, run_root, run_dir / "post_clear_source_lock.json")

    environment = _ros_environment(fast_ws)
    sequence_slot = SEQUENCES.index(sequence) + 1
    ros_port = 19700 + sequence_slot * 10 + repeat
    environment.update(
        {
            "ROS_MASTER_URI": f"http://127.0.0.1:{ros_port}",
            "ROS_HOSTNAME": "127.0.0.1",
            "ROS_HOME": str(paths.ros_home),
            "ROS_LOG_DIR": str(paths.ros_log_dir),
        }
    )
    _run(["rosbag", "info", "--yaml", str(clip_path)], environment=environment, output=run_dir / "bag_info.yaml")
    config_bundle = hashlib.sha256(
        (sha256_file(fast_root / "config/avia.yaml") + sha256_file(fast_root / "launch/mapping_avia.launch")).encode()
    ).hexdigest()

    roscore = roslaunch = rosbag = None
    roscore_log = roslaunch_log = rosbag_log = None
    rosbag_exit = roslaunch_exit = None
    shutdown: dict[str, Any] | None = None
    try:
        roscore, roscore_log = _start(["roscore", "-p", str(ros_port)], run_dir / "roscore.log", environment)
        _wait_command(["rosparam", "list"], environment=environment, attempts=100, process=roscore)
        _run(["rosparam", "load", str(fast_root / "config/avia.yaml"), "/"], environment=environment)
        extrinsic = _run(["rosparam", "get", "/mapping/extrinsic_est_en"], environment=environment).stdout.strip()
        if extrinsic != "false":
            raise MatrixFailure("SOURCE_LOCK_CHANGED", "frozen config has extrinsic estimation enabled")
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
            "/harmful_bias/run_id": f"{RUN_ID}_{sequence}_{run_label}",
            "/harmful_bias/sequence_id": sequence,
            "/harmful_bias/bag_sha256": clip["sha256"],
            "/harmful_bias/config_bundle_sha256": config_bundle,
            "/harmful_bias/fastlio2_binary_sha256": lock["fastlio2_binary_sha256"],
        }
        for key, value in parameters.items():
            _run(["rosparam", "set", key, value], environment=environment)
        paths.launch_path.write_text(
            '<launch>\n  <node pkg="fast_lio" type="fastlio_mapping" name="laserMapping" output="screen" required="true" />\n</launch>\n',
            encoding="utf-8",
        )
        roslaunch, roslaunch_log = _start(
            ["taskset", "-c", str(lock["cpu_affinity"]["fastlio2_core"]), "roslaunch", str(paths.launch_path)],
            run_dir / "roslaunch.log", environment,
        )
        _wait_command(["rosnode", "info", "/laserMapping"], environment=environment, attempts=300, process=roslaunch)
        actual_output_dir = _run(
            ["rosparam", "get", "/harmful_bias/runtime_equivalence_output_dir"],
            environment=environment,
        ).stdout.strip()
        try:
            path_param_audit = validate_runtime_output_param(
                paths.runtime_output_dir, actual_output_dir
            )
        except RuntimePathError as error:
            raise MatrixFailure("RUNTIME_OUTPUT_PATH_INVALID", str(error)) from error
        write_json(run_dir / "runtime_output_param_audit.json", path_param_audit)
        _capture(["rosparam", "dump", str(run_dir / "rosparams.yaml"), "/"], run_dir / "rosparam_dump_command.txt", environment)
        (run_dir / "runtime_environment.txt").write_text(
            "\n".join(f"{key}={environment[key]}" for key in sorted(LOCKED_ENVIRONMENT)) + "\n",
            encoding="utf-8",
        )
        bag_command = [
            "taskset", "-c", str(lock["cpu_affinity"]["rosbag_core"]),
            "rosbag", "play", str(clip_path), "--pause", "--clock", "--rate", "0.25", "--queue=10000",
            "__name:=day5_bag_player",
        ]
        (run_dir / "bag_command.txt").write_text(" ".join(bag_command) + "\n", encoding="utf-8")
        rosbag, rosbag_log = _start(bag_command, run_dir / "rosbag.log", environment)
        handshake_path = run_dir / "connection_handshake_v3.json"
        handshake_command = build_handshake_command(
            root=root, run_id=RUN_ID, sequence_id=sequence, repeat_id=repeat,
            master_uri=environment["ROS_MASTER_URI"], output=handshake_path,
        )
        handshake = _run(handshake_command, environment=environment, output=run_dir / "connection_handshake_tool.log", check=False)
        if handshake.returncode:
            raise MatrixFailure("ROSBAG_SUBSCRIBER_HANDSHAKE_FAILURE", "paused connection handshake or unpause failed")
        handshake_value = json.loads(handshake_path.read_text(encoding="utf-8"))
        (run_dir / "pause_service_response.txt").write_text(handshake_value.get("pause_service_response", ""), encoding="utf-8")
        for command, filename in (
            (["rosnode", "info", "/laserMapping"], "rosnode_info_laser_mapping.txt"),
            (["rosnode", "info", "/day5_bag_player"], "rosnode_info_bag_player.txt"),
            (["rostopic", "info", "/livox/lidar"], "rostopic_info_livox_lidar.txt"),
            (["rostopic", "info", "/livox/imu"], "rostopic_info_livox_imu.txt"),
            (["rosservice", "list"], "rosservice_list.txt"),
            (["rosservice", "type", "/day5_bag_player/pause_playback"], "rosservice_type_pause_playback.txt"),
            (["rosservice", "uri", "/day5_bag_player/pause_playback"], "rosservice_uri_pause_playback.txt"),
        ):
            _capture(command, run_dir / filename, environment)
        shutil.copy2(
            run_dir / "rosnode_info_laser_mapping.txt",
            run_dir / "rosnode_info.txt",
        )
        try:
            rosbag_exit = rosbag.wait(timeout=float(clip["duration_seconds"]) / 0.25 + 120)
        except subprocess.TimeoutExpired as exc:
            raise MatrixFailure("ROSBAG_SUBSCRIBER_HANDSHAKE_FAILURE", "rosbag playback timeout") from exc
        if rosbag_exit != 0:
            raise MatrixFailure("ROSBAG_SUBSCRIBER_HANDSHAKE_FAILURE", f"rosbag exit code {rosbag_exit}")
        time.sleep(5)
        shutdown = graceful_shutdown_roslaunch(
            roslaunch,
            environment=environment,
            run_dir=run_dir,
            timeout=30.0,
        )
        roslaunch_exit = shutdown["roslaunch_exit_code"]
        roslaunch = None
    finally:
        _stop(rosbag)
        _stop(roslaunch)
        _stop(roscore)
        for handle in (rosbag_log, roslaunch_log, roscore_log):
            if handle is not None:
                handle.close()

    if shutdown is None:
        raise MatrixFailure(
            "RUNTIME_NODE_SHUTDOWN_INCOMPLETE",
            "normal runtime shutdown evidence is missing",
        )
    conversion_start = time.monotonic_ns()
    product_validation_path = run_dir / "runtime_product_validation_v3.json"
    product_process = _run(
        [
            sys.executable,
            str(root / "scripts/53_validate_runtime_audit_products.py"),
            "--run-dir",
            str(run_dir),
            "--converted-dir",
            str(run_dir / "converted"),
            "--output",
            str(product_validation_path),
        ],
        environment=environment,
        output=run_dir / "runtime_product_validation_tool.log",
        check=False,
    )
    if product_process.returncode:
        if product_validation_path.is_file():
            product_failure = json.loads(
                product_validation_path.read_text(encoding="utf-8")
            )
            classification = product_failure.get(
                "failure_classification", "RUNTIME_PRODUCT_MISSING"
            )
            message = product_failure.get("message", "runtime product validation failed")
        else:
            classification = "RUNTIME_PRODUCT_MISSING"
            message = "runtime product validator produced no result"
        raise MatrixFailure(classification, message)
    conversion_runtime = time.monotonic_ns() - conversion_start
    rows = _read_csv(run_dir / "converted/runtime_frames.csv")
    conversion = json.loads((run_dir / "converted/binary_conversion_summary.json").read_text(encoding="utf-8"))
    product_validation = json.loads(product_validation_path.read_text(encoding="utf-8"))
    metadata = {
        "run_id": f"{RUN_ID}_{sequence}_{run_label}",
        "phase_run_id": RUN_ID,
        "sequence_id": sequence,
        "runtime_mode": MODE,
        "repeat_id": repeat,
        "local_alias": clip["alias"],
        "bag_sha256": clip["sha256"],
        "original_bag_sha256": clip["original_bag_sha256"],
        "playback_rate": 0.25,
        "use_clock": True,
        "ros_master_port": ros_port,
        "fast_cpu_core": lock["cpu_affinity"]["fastlio2_core"],
        "rosbag_cpu_core": lock["cpu_affinity"]["rosbag_core"],
        "rosbag_exit_code": rosbag_exit,
        "rosbag_natural_exit": True,
        "laser_mapping_exit_code": shutdown["laser_mapping_exit_code"],
        "roslaunch_exit_code": roslaunch_exit,
        "shutdown_completed": shutdown["shutdown_completed"],
        "shutdown_request_method": shutdown["shutdown_request_method"],
        "forced_terminate_used": shutdown["forced_terminate_used"],
        "forced_kill_used": shutdown["forced_kill_used"],
        "runtime_audit_row_count": len(rows),
        "observation_record_count": conversion["observation_record_count"],
        "offline_conversion_runtime_ns": conversion_runtime,
        "fastlio2_binary_sha256_before": lock["fastlio2_binary_sha256"],
        "fastlio2_binary_sha256_after": sha256_file(binary),
        "config_bundle_sha256": config_bundle,
        "runtime_output_dir": str(paths.runtime_output_dir),
        "runtime_output_dir_is_absolute": True,
        "runtime_output_param_match": True,
        "runtime_product_pass": product_validation["runtime_product_pass"],
        "runtime_binary_trailer_pass": product_validation["runtime_binary_trailer_pass"],
    }
    write_json(run_dir / "run_metadata.json", metadata)
    after_run = runtime_output_inventory(fast_root)
    write_json(run_dir / "runtime_output_inventory_after_run.json", after_run)
    runtime_audit = compare_runtime_inventories(after_clear, after_run)
    write_json(run_dir / "runtime_output_allowlist_audit.json", runtime_audit)
    if not runtime_audit["allowlist_pass"]:
        raise MatrixFailure("RUNTIME_OUTPUT_ALLOWLIST_INCOMPLETE", "unknown FAST runtime output changed")
    return metadata


def summarize(run_root: Path, phase_root: Path) -> dict[str, Any]:
    phase = json.loads((run_root / "baseline_phase_summary.json").read_text(encoding="utf-8"))
    run_lock = json.loads(
        (run_root / "day5_startup_sync_v3_run_lock.json").read_text(
            encoding="utf-8"
        )
    )
    comparisons = list(phase["comparisons"])
    first_inputs: list[dict[str, Any]] = []
    run_manifest: list[dict[str, Any]] = []
    all_rows: list[dict[str, str]] = []
    handshakes: list[dict[str, Any]] = []
    timing_rows: list[dict[str, Any]] = []
    lock_rows: list[dict[str, Any]] = []
    allowlist_rows: list[dict[str, Any]] = []
    absolute_path_rows: list[dict[str, Any]] = []
    shutdown_rows: list[dict[str, Any]] = []
    product_rows: list[dict[str, Any]] = []
    full_log_rows: list[dict[str, Any]] = []
    declared_nonfinite_count = 0
    for sequence in SEQUENCES:
        for repeat in REPEATS:
            label = f"AUDIT_ONLY_R{repeat}"
            run_dir = phase_root / sequence / label
            rows = _read_csv(run_dir / "converted/runtime_frames.csv")
            all_rows.extend(rows)
            first = rows[0]
            first_inputs.append(
                {
                    "sequence_id": sequence,
                    "repeat_id": repeat,
                    "scan_count": len(rows),
                    "first_runtime_scan_index": int(first["scan_index"]),
                    "first_measure_group_checksum": int(first["measure_group_checksum"]),
                    "first_measure_group_lidar_begin_time": float(first["lidar_begin_time"]),
                    "first_measure_group_lidar_end_time": float(first["lidar_end_time"]),
                    "first_measure_group_lidar_point_count": int(first["lidar_point_count"]),
                    "first_measure_group_imu_message_count": int(first["imu_message_count"]),
                    "first_measure_group_first_imu_timestamp": float(first["first_imu_timestamp"]),
                    "first_measure_group_last_imu_timestamp": float(first["last_imu_timestamp"]),
                    "first_ten_signature_sha256": first_ten_signature(rows),
                }
            )
            _write_csv(
                run_dir / "first_ten_measure_groups.csv",
                [{key: row[key] for key in ("scan_index", "measure_group_checksum", "timestamp_begin", "lidar_point_count", "imu_message_count")} for row in rows[:10]],
            )
            handshake = json.loads((run_dir / "connection_handshake_v3.json").read_text(encoding="utf-8"))
            order_pass = (
                handshake["handshake_start_monotonic_ns"] <= handshake["handshake_ready_monotonic_ns"]
                <= handshake["unpause_call_start_monotonic_ns"] <= handshake["unpause_call_end_monotonic_ns"]
            )
            handshakes.append(
                {
                    "sequence_id": sequence,
                    "repeat_id": repeat,
                    "handshake_pass": handshake["handshake_pass"],
                    "unpause_success": handshake["unpause_success"],
                    "stable_poll_required": handshake["stable_poll_required"],
                    "stable_poll_observed": handshake["stable_poll_observed"],
                    "lidar_publisher_bus_connected": handshake["lidar_publisher_bus_connected"],
                    "lidar_subscriber_bus_connected": handshake["lidar_subscriber_bus_connected"],
                    "imu_publisher_bus_connected": handshake["imu_publisher_bus_connected"],
                    "imu_subscriber_bus_connected": handshake["imu_subscriber_bus_connected"],
                    "extra_publisher_present": handshake["extra_publisher_present"],
                    "extra_subscriber_present": handshake["extra_subscriber_present"],
                    "failure_reason": handshake["failure_reason"],
                }
            )
            timing_rows.append(
                {"sequence_id": sequence, "repeat_id": repeat, "monotonic_order_pass": order_pass,
                 **{key: handshake[key] for key in ("handshake_start_monotonic_ns", "handshake_ready_monotonic_ns", "unpause_call_start_monotonic_ns", "unpause_call_end_monotonic_ns", "unpause_wall_time_utc")}}
            )
            run_manifest.append(json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8")))
            declared_nonfinite_count += int(
                json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))["nonfinite_count"]
            )
            declared_nonfinite_count += int(
                json.loads((run_dir / "final_map_summary.json").read_text(encoding="utf-8"))["nonfinite_count"]
            )
            for when in ("pre", "post"):
                audit = json.loads((run_root / f"{when}_{sequence}_AUDIT_ONLY_R{repeat}_lock.json").read_text(encoding="utf-8"))
                lock_rows.append(
                    {"sequence_id": sequence, "repeat_id": repeat, "when": when,
                     "source_lock_pass": audit["source_lock_pass"], "binary_lock_pass": audit["binary_lock_pass"], "clip_lock_pass": audit["clip_lock_pass"]}
                )
            runtime_audit = json.loads((run_dir / "runtime_output_allowlist_audit.json").read_text(encoding="utf-8"))
            allowlist_rows.append(
                {"sequence_id": sequence, "repeat_id": repeat, "allowlist_pass": runtime_audit["allowlist_pass"],
                 "changed_paths": ";".join(runtime_audit["changed_paths"]),
                 "unexpected_runtime_output_count": runtime_audit["unexpected_runtime_output_count"]}
            )
            path_audit = json.loads(
                (run_dir / "absolute_path_audit.json").read_text(encoding="utf-8")
            )
            param_audit = json.loads(
                (run_dir / "runtime_output_param_audit.json").read_text(encoding="utf-8")
            )
            absolute_path_rows.append(
                {
                    "sequence_id": sequence,
                    "repeat_id": repeat,
                    "run_dir_is_absolute": Path(path_audit["paths"]["run_dir"]).is_absolute(),
                    "ros_home_is_absolute": Path(path_audit["paths"]["ros_home"]).is_absolute(),
                    "ros_log_dir_is_absolute": Path(path_audit["paths"]["ros_log_dir"]).is_absolute(),
                    "runtime_output_dir_is_absolute": path_audit["runtime_output_dir_is_absolute"],
                    "runtime_output_param_match": param_audit["runtime_output_param_match"],
                    "duplicate_run_root_detected": path_audit["duplicate_run_root_detected"],
                }
            )
            shutdown = json.loads(
                (run_dir / "graceful_shutdown_v3.json").read_text(encoding="utf-8")
            )
            shutdown_rows.append(
                {"sequence_id": sequence, "repeat_id": repeat, **shutdown}
            )
            product = json.loads(
                (run_dir / "runtime_product_validation_v3.json").read_text(
                    encoding="utf-8"
                )
            )
            product_rows.append(
                {"sequence_id": sequence, "repeat_id": repeat, **product}
            )
            conversion = json.loads((run_dir / "converted/binary_conversion_summary.json").read_text(encoding="utf-8"))
            for path, file_type, count in (
                (run_dir / "runtime_audit_v2.bin", "runtime_binary", conversion["runtime_record_count"]),
                (run_dir / "converted/runtime_frames.csv", "runtime_csv", len(rows)),
                (run_dir / "rosbag.log", "ros_log", ""),
                (run_dir / "roslaunch.log", "ros_log", ""),
                (run_dir / "roscore.log", "ros_log", ""),
            ):
                full_log_rows.append(
                    {"phase": "startup_sync_v3", "run_id": RUN_ID, "sequence_id": sequence, "mode": MODE,
                     "repeat_id": repeat, "relative_path": path.relative_to(run_root).as_posix(), "file_type": file_type,
                     "size_bytes": path.stat().st_size, "sha256": sha256_file(path), "row_or_record_count": count,
                     "included_in_audit_package": False, "exclusion_reason": "LARGE_REAL_RUNTIME_LOG_NOT_SHARED"}
                )

    sums = lambda field: sum(int(row[field]) for row in comparisons)
    max_value = lambda field: max(float(row[field]) for row in comparisons)
    boundary_pass = startup_boundary_pass(first_inputs)
    handshake_pass = all(row["handshake_pass"] and row["unpause_success"] for row in handshakes)
    lock_pass = all(row["source_lock_pass"] for row in lock_rows)
    binary_pass = all(row["binary_lock_pass"] for row in lock_rows)
    clip_pass = all(row["clip_lock_pass"] for row in lock_rows)
    runtime_pass = all(row["allowlist_pass"] for row in allowlist_rows)
    absolute_path_pass = all(
        row["run_dir_is_absolute"]
        and row["ros_home_is_absolute"]
        and row["ros_log_dir_is_absolute"]
        and row["runtime_output_dir_is_absolute"]
        and row["runtime_output_param_match"]
        and not row["duplicate_run_root_detected"]
        for row in absolute_path_rows
    )
    runtime_product_pass = all(
        row["runtime_product_pass"]
        and row["runtime_binary_trailer_pass"]
        and row["runtime_binary_checksum_pass"]
        for row in product_rows
    )
    passing_pairs = sum(bool(row["overall_equivalence_pass"]) for row in comparisons)
    successful_replays = int(phase["successful_replay_count"])
    values = {
        "successful_replay_count": successful_replays,
        "executed_replay_count": len(run_manifest),
        "evaluated_pair_count": len(comparisons),
        "executed_handshake_pass_count": sum(bool(row["handshake_pass"]) for row in handshakes),
        "executed_paused_start_pass_count": sum(bool(row["unpause_success"]) for row in handshakes),
        "executed_runtime_product_pass_count": sum(
            bool(row["runtime_product_pass"]) for row in product_rows
        ),
        "clip_lock_pass": clip_pass,
        "connection_handshake_pass": handshake_pass,
        "paused_start_pass": all(row["unpause_success"] for row in handshakes),
        "runtime_allowlist_pass": runtime_pass,
        "runtime_output_contract_pass": bool(
            run_lock["runtime_output_contract_pass"]
        ),
        "runtime_output_absolute_path_pass": absolute_path_pass,
        "runtime_binary_completeness_pass": runtime_product_pass,
        "startup_input_boundary_pass": boundary_pass,
        "source_lock_pass": lock_pass,
        "binary_lock_pass": binary_pass,
        "parameter_identity_pass": bool(phase["PARAMETER_DIFF_ALLOWLIST_PASS"]),
        "scan_pairing_pass": sums("missing_scan_count") == 0 and sums("duplicate_scan_count") == 0,
        "measure_group_equivalence_pass": sums("measure_group_checksum_mismatch_count") == 0 and sums("exact_field_mismatch_count") == 0,
        "pose_equivalence_pass": sums("prior_state_checksum_mismatch_count") == 0 and sums("posterior_state_checksum_mismatch_count") == 0 and max_value("max_position_difference_m") <= TOLERANCE and max_value("max_rotation_geodesic_difference_rad") <= TOLERANCE,
        "covariance_equivalence_pass": sums("prior_covariance_checksum_mismatch_count") == 0 and sums("posterior_covariance_checksum_mismatch_count") == 0 and max_value("max_covariance_absolute_difference") <= TOLERANCE,
        "jacobian_equivalence_pass": sums("formal_native_jacobian_checksum_mismatch_count") == 0 and sums("detector_jacobian_checksum_mismatch_count") == 0,
        "residual_equivalence_pass": sums("formal_innovation_checksum_mismatch_count") == 0 and sums("geometric_residual_checksum_mismatch_count") == 0,
        "accepted_index_equivalence_pass": sums("accepted_index_checksum_mismatch_count") == 0,
        "correspondence_equivalence_pass": sums("formal_correspondence_checksum_mismatch_count") == 0,
        "map_size_equivalence_pass": sums("map_size_after_update_mismatch_count") == 0,
        "final_map_equivalence_pass": all(row["final_map_equivalence_pass"] for row in comparisons),
        "no_nonfinite_pass": declared_nonfinite_count == 0 and not _contains_nonfinite(all_rows),
        "no_gt_runtime_pass": bool(phase["NO_GT_RUNTIME_PASS"]),
    }
    gates = evaluate_startup_sync_v3_gate(values)
    if not lock_pass:
        failure = "SOURCE_LOCK_CHANGED"
    elif not binary_pass:
        failure = "BINARY_CHANGED"
    elif not clip_pass:
        failure = "CLIP_CHANGED"
    elif not values["runtime_output_contract_pass"]:
        failure = "RUNTIME_OUTPUT_ALLOWLIST_INCOMPLETE"
    elif not runtime_pass:
        failure = "RUNTIME_OUTPUT_ALLOWLIST_INCOMPLETE"
    elif not absolute_path_pass:
        failure = "RUNTIME_OUTPUT_PATH_INVALID"
    elif not all(row["shutdown_completed"] for row in shutdown_rows):
        failure = "RUNTIME_NODE_SHUTDOWN_INCOMPLETE"
    elif not runtime_product_pass:
        failure = "RUNTIME_PRODUCT_MISSING"
    elif not handshake_pass:
        failure = "ROSBAG_SUBSCRIBER_HANDSHAKE_FAILURE"
    elif not boundary_pass:
        failure = "INPUT_BOUNDARY_NONDETERMINISM_AFTER_HANDSHAKE"
    elif sums("prior_state_checksum_mismatch_count"):
        failure = "FASTLIO2_BASELINE_STATE_NONDETERMINISM"
    elif sums("prior_covariance_checksum_mismatch_count"):
        failure = "FASTLIO2_BASELINE_STATE_NONDETERMINISM"
    elif sums("formal_native_jacobian_checksum_mismatch_count") or sums("geometric_residual_checksum_mismatch_count"):
        failure = "FASTLIO2_FORMAL_LINEARIZATION_NONDETERMINISM"
    elif sums("posterior_state_checksum_mismatch_count"):
        failure = "FASTLIO2_FILTER_UPDATE_NONDETERMINISM"
    elif sums("posterior_covariance_checksum_mismatch_count"):
        failure = "FASTLIO2_FILTER_UPDATE_NONDETERMINISM"
    elif sums("map_size_after_update_mismatch_count"):
        failure = "FINAL_MAP_DIGEST_OR_TRAVERSAL_NONDETERMINISM"
    elif not values["final_map_equivalence_pass"]:
        failure = "FINAL_MAP_DIGEST_OR_TRAVERSAL_NONDETERMINISM"
    else:
        failure = "NONE"
    gates["FAILURE_CLASSIFICATION"] = failure
    first_divergence = next((row for row in comparisons if row["first_divergence_stage"] != "NONE"), None)
    summary = {
        **gates,
        "run_id": RUN_ID,
        "planned_replay_count": 6,
        "successful_replay_count": successful_replays,
        "executed_replay_count": len(run_manifest),
        "planned_pair_count": 6,
        "evaluated_pair_count": len(comparisons),
        "passing_pair_count": passing_pairs,
        "paired_scan_count": sums("paired_scan_count"),
        "missing_scan_count": sums("missing_scan_count"),
        "duplicate_scan_count": sums("duplicate_scan_count"),
        "measure_group_mismatch_count": sums("measure_group_checksum_mismatch_count"),
        "prior_state_mismatch_count": sums("prior_state_checksum_mismatch_count"),
        "prior_covariance_mismatch_count": sums("prior_covariance_checksum_mismatch_count"),
        "jacobian_mismatch_count": sums("formal_native_jacobian_checksum_mismatch_count"),
        "residual_mismatch_count": sums("geometric_residual_checksum_mismatch_count"),
        "accepted_index_mismatch_count": sums("accepted_index_checksum_mismatch_count"),
        "correspondence_mismatch_count": sums("formal_correspondence_checksum_mismatch_count"),
        "posterior_state_mismatch_count": sums("posterior_state_checksum_mismatch_count"),
        "posterior_covariance_mismatch_count": sums("posterior_covariance_checksum_mismatch_count"),
        "map_size_mismatch_count": sums("map_size_after_update_mismatch_count"),
        "final_map_mismatch_count": sum(not row["final_map_equivalence_pass"] for row in comparisons),
        "max_position_difference_m": max_value("max_position_difference_m"),
        "max_rotation_difference_rad": max_value("max_rotation_geodesic_difference_rad"),
        "max_covariance_difference": max_value("max_covariance_absolute_difference"),
        "first_divergence_scan": first_divergence["first_divergence_scan_index"] if first_divergence else None,
        "first_divergence_stage": first_divergence["first_divergence_stage"] if first_divergence else "NONE",
        "unexpected_runtime_output_count": sum(int(row["unexpected_runtime_output_count"]) for row in allowlist_rows),
        "runtime_output_changed_paths": sorted({path for row in allowlist_rows for path in str(row["changed_paths"]).split(";") if path}),
        "run_root_is_absolute": run_root.is_absolute(),
        "run_dirs_absolute_count": sum(bool(row["run_dir_is_absolute"]) for row in absolute_path_rows),
        "ros_home_absolute_count": sum(bool(row["ros_home_is_absolute"]) for row in absolute_path_rows),
        "ros_log_absolute_count": sum(bool(row["ros_log_dir_is_absolute"]) for row in absolute_path_rows),
        "runtime_output_dirs_absolute_count": sum(bool(row["runtime_output_dir_is_absolute"]) for row in absolute_path_rows),
        "runtime_output_param_match_count": sum(bool(row["runtime_output_param_match"]) for row in absolute_path_rows),
        "duplicate_run_root_count": sum(bool(row["duplicate_run_root_detected"]) for row in absolute_path_rows),
        "forced_terminate_count": sum(bool(row["forced_terminate_used"]) for row in shutdown_rows),
        "forced_kill_count": sum(bool(row["forced_kill_used"]) for row in shutdown_rows),
        "shutdown_completed_count": sum(bool(row["shutdown_completed"]) for row in shutdown_rows),
        "runtime_binary_file_count": len(product_rows),
        "runtime_binary_trailer_pass_count": sum(bool(row["runtime_binary_trailer_pass"]) for row in product_rows),
        "runtime_binary_checksum_failure_count": sum(int(row["binary_checksum_failure_count"]) for row in product_rows),
        "runtime_product_missing_count": sum(int(row["runtime_product_missing_count"]) for row in product_rows),
        "run_summary_pass_count": sum(bool(row["run_summary_pass"]) for row in product_rows),
        "final_map_summary_pass_count": sum(bool(row["final_map_summary_pass"]) for row in product_rows),
        "tap_export_summary_pass_count": sum(bool(row["tap_export_summary_pass"]) for row in product_rows),
    }
    _write_csv(run_root / "source_lock_summary.csv", lock_rows)
    _write_csv(run_root / "runtime_output_allowlist_audit.csv", allowlist_rows)
    _write_csv(run_root / "absolute_path_audit.csv", absolute_path_rows)
    _write_csv(run_root / "graceful_shutdown_summary.csv", shutdown_rows)
    _write_csv(run_root / "runtime_product_completeness.csv", product_rows)
    _write_csv(run_root / "binary_trailer_validation.csv", product_rows)
    _write_csv(run_root / "connection_handshake_summary.csv", handshakes)
    _write_csv(run_root / "monotonic_timing_summary.csv", timing_rows)
    _write_csv(run_root / "first_input_boundary_summary.csv", first_inputs)
    _write_csv(run_root / "baseline_pairwise_equivalence.csv", comparisons)
    _write_csv(run_root / "baseline_repeatability_summary.csv", [summary])
    _write_csv(run_root / "source_binary_clip_lock_audit.csv", lock_rows)
    _write_csv(run_root / "gate_summary.csv", [{"gate": key, "value": value} for key, value in gates.items()])
    _write_csv(run_root / "full_log_index.csv", full_log_rows)
    shutil.copy2(run_root / "first_divergence_baseline.csv", run_root / "first_divergence_summary.csv")
    shutil.copy2(run_root / "parameter_diff_audit_baseline.csv", run_root / "parameter_identity_audit.csv")
    shutil.copy2(run_root / "no_gt_runtime_audit_baseline.csv", run_root / "no_gt_runtime_audit.csv")
    write_json(run_root / "day5_startup_sync_v3_run_manifest.json", {"run_id": RUN_ID, "runs": run_manifest})
    write_json(run_root / "day5_startup_sync_v3_summary.json", summary)
    write_json(run_root / "day5_startup_sync_v3_gate_summary.json", gates)
    return summary


def copy_small_results(root: Path, run_root: Path) -> None:
    destination = root / "artifacts/current/harmful_bias_multihyp_dev/day5_startup_sync_v3"
    if destination.exists():
        raise MatrixFailure("SOURCE_LOCK_CHANGED", f"small artifact directory already exists: {destination}")
    destination.mkdir(parents=True)
    names = (
        "source_lock_summary.csv", "runtime_output_allowlist_audit.csv", "absolute_path_audit.csv",
        "graceful_shutdown_summary.csv", "runtime_product_completeness.csv",
        "binary_trailer_validation.csv", "connection_handshake_summary.csv",
        "monotonic_timing_summary.csv", "first_input_boundary_summary.csv", "baseline_pairwise_equivalence.csv",
        "baseline_repeatability_summary.csv", "first_divergence_summary.csv", "parameter_identity_audit.csv",
        "source_binary_clip_lock_audit.csv", "no_gt_runtime_audit.csv", "gate_summary.csv",
        "day5_startup_sync_v3_run_manifest.json", "day5_startup_sync_v3_summary.json",
        "day5_startup_sync_v3_gate_summary.json", "full_log_index.csv",
    )
    for name in names:
        shutil.copy2(run_root / name, destination / name)
    for name in (
        "fastlio2_runtime_output_source_scan.csv",
        "fastlio2_runtime_output_allowlist_v2.json",
    ):
        shutil.copy2(run_root / "source_locks" / name, destination / name)


def install_prepared_locks(
    *, prepared_lock: Path, lock: Mapping[str, Any], run_root: Path
) -> Path:
    for relative in lock["prepared_lock_files"]:
        destination = run_root / relative
        source = prepared_lock.parent / Path(relative).name
        if not source.is_file():
            raise MatrixFailure("SOURCE_LOCK_CHANGED", f"prepared lock file missing: {source.name}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    installed_run_lock = run_root / "day5_startup_sync_v3_run_lock.json"
    shutil.copy2(prepared_lock, installed_run_lock)
    if sha256_file(installed_run_lock) != sha256_file(prepared_lock):
        raise MatrixFailure("SOURCE_LOCK_CHANGED", "installed run lock SHA mismatch")
    return installed_run_lock


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--lock", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    args.run_root = (
        Path(args.run_root)
        .expanduser()
        .resolve(strict=False)
    )
    if not args.run_root.is_absolute():
        raise SystemExit("ERROR: RUNTIME_OUTPUT_PATH_INVALID")
    args.lock = resolve_runtime_path(args.lock, name="lock")
    if args.run_root.exists():
        raise SystemExit("ERROR: startup-sync V3 run-id has already been used")
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    if lock["run_id"] != RUN_ID:
        raise SystemExit("ERROR: wrong startup-sync V3 run lock")
    args.run_root.mkdir(parents=True)
    install_prepared_locks(prepared_lock=args.lock, lock=lock, run_root=args.run_root)
    (args.run_root / "matrix_started.marker").write_text("RUN_ID_CONSUMED_NO_REUSE\n", encoding="utf-8")
    phase_root = args.run_root / "runs/baseline"
    phase_root.mkdir(parents=True)
    plan = fixed_replay_plan()
    validate_replay_plan(plan)
    lock_sha = sha256_file(args.lock)
    try:
        for row in plan:
            sequence, repeat = row["sequence_id"], row["repeat_id"]
            _source_lock_result(lock, root, args.run_root, args.run_root / f"pre_{sequence}_AUDIT_ONLY_R{repeat}_lock.json")
            execute_replay(lock=lock, root=root, run_root=args.run_root, phase_root=phase_root, sequence=sequence, repeat=repeat)
            if sha256_file(args.lock) != lock_sha:
                raise MatrixFailure("SOURCE_LOCK_CHANGED", "run lock changed during matrix")
            _source_lock_result(lock, root, args.run_root, args.run_root / f"post_{sequence}_AUDIT_ONLY_R{repeat}_lock.json")
    except MatrixFailure as exc:
        write_json(
            args.run_root / "matrix_failure.json",
            {"failure_classification": exc.classification, "message": str(exc), "run_id_reuse_forbidden": True},
        )
        return 30
    comparator = locked_path(lock["comparator_path"], root)
    compared = subprocess.run(
        [sys.executable, str(comparator), "--phase", "baseline", "--phase-root", str(phase_root), "--output-root", str(args.run_root)],
        cwd=root,
    )
    summary = summarize(args.run_root, phase_root)
    copy_small_results(root, args.run_root)
    return 0 if summary["DAY5_STARTUP_SYNC_V3_PASS"] and compared.returncode == 0 else 20


if __name__ == "__main__":
    raise SystemExit(main())
