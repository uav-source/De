#!/usr/bin/env python3
"""Wait for an exact, stable two-topic TCPROS rosbag handshake."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import xmlrpc.client
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


BAG_PLAYER = "/day5_bag_player"
LASER_MAPPING = "/laserMapping"
TOPICS = ("/livox/lidar", "/livox/imu")
PAUSE_SERVICE = "/day5_bag_player/pause_playback"
PAUSE_SERVICE_TYPE = "std_srvs/SetBool"
PROTOCOL_VERSION = "DAY5_STARTUP_SYNC_TCPROS_V2_MONOTONIC_UNPAUSE"


class HandshakeError(RuntimeError):
    pass


class TimeoutTransport(xmlrpc.client.Transport):
    def __init__(self, timeout: float = 2.0) -> None:
        super().__init__()
        self.timeout = timeout

    def make_connection(self, host: str):  # type: ignore[no-untyped-def]
        connection = super().make_connection(host)
        connection.timeout = self.timeout
        return connection


def _state_map(entries: list[list[Any]]) -> dict[str, list[str]]:
    return {str(topic): sorted(str(node) for node in nodes) for topic, nodes in entries}


def _connected_bus(
    rows: list[list[Any]], *, direction: str, peer: str, topic: str
) -> list[list[Any]]:
    matched = []
    for row in rows:
        if len(row) < 6:
            continue
        if str(row[2]) != direction or str(row[4]) != topic:
            continue
        if str(row[1]) != peer or not bool(row[5]):
            continue
        matched.append(row)
    return matched


def evaluate_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    publishers = _state_map(list(snapshot["publisher_state"]))
    subscribers = _state_map(list(snapshot["subscriber_state"]))
    services = _state_map(list(snapshot["service_state"]))
    publisher_bus = list(snapshot["publisher_bus_info"])
    subscriber_bus = list(snapshot["subscriber_bus_info"])
    subscriber_peer = str(snapshot.get("bag_player_node_uri") or BAG_PLAYER)

    result: dict[str, Any] = {
        "publisher_count_lidar": len(publishers.get(TOPICS[0], [])),
        "publisher_count_imu": len(publishers.get(TOPICS[1], [])),
        "subscriber_count_lidar": len(subscribers.get(TOPICS[0], [])),
        "subscriber_count_imu": len(subscribers.get(TOPICS[1], [])),
        "pause_service_present": services.get(PAUSE_SERVICE) == [BAG_PLAYER],
        "pause_service_type": snapshot.get("pause_service_type"),
    }
    for short, topic in (("lidar", TOPICS[0]), ("imu", TOPICS[1])):
        exact_publisher = publishers.get(topic) == [BAG_PLAYER]
        exact_subscriber = subscribers.get(topic) == [LASER_MAPPING]
        pub_bus = _connected_bus(
            publisher_bus, direction="o", peer=LASER_MAPPING, topic=topic
        )
        sub_bus = _connected_bus(
            subscriber_bus, direction="i", peer=subscriber_peer, topic=topic
        )
        result[f"{short}_publisher_graph"] = exact_publisher
        result[f"{short}_subscriber_graph"] = exact_subscriber
        result[f"{short}_publisher_bus_connected"] = len(pub_bus) == 1
        result[f"{short}_subscriber_bus_connected"] = len(sub_bus) == 1
        result[f"{short}_connected"] = bool(
            exact_publisher
            and exact_subscriber
            and len(pub_bus) == 1
            and len(sub_bus) == 1
        )

    result["extra_publisher_present"] = any(
        publishers.get(topic) != [BAG_PLAYER] for topic in TOPICS
    )
    result["extra_subscriber_present"] = any(
        subscribers.get(topic) != [LASER_MAPPING] for topic in TOPICS
    )
    result["snapshot_pass"] = bool(
        result["lidar_connected"]
        and result["imu_connected"]
        and result["pause_service_present"]
        and result["pause_service_type"] == PAUSE_SERVICE_TYPE
        and not result["extra_publisher_present"]
        and not result["extra_subscriber_present"]
    )
    return result


def unpause_succeeded(returncode: int, response: str) -> bool:
    return returncode == 0 and re.search(r"success:\s*(True|true)", response) is not None


def _response_message(response: str) -> str | None:
    match = re.search(r"^message:\s*[\"']?(.*?)[\"']?\s*$", response, re.MULTILINE)
    return match.group(1) if match else None


def invoke_unpause_service(
    *,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    wall_now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    command_runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    start = monotonic_ns()
    wall_time = wall_now()
    response = ""
    returncode: int | None = None
    exception: str | None = None
    try:
        completed = command_runner(
            ["rosservice", "call", PAUSE_SERVICE, "data: false"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        returncode = int(completed.returncode)
        response = str(completed.stdout or "")
    except Exception as exc:  # Fail closed and preserve the service exception.
        exception = f"{type(exc).__name__}: {exc}"
    end = monotonic_ns()
    success = exception is None and returncode is not None and unpause_succeeded(returncode, response)
    return {
        "unpause_call_start_monotonic_ns": start,
        "unpause_call_end_monotonic_ns": end,
        "unpause_wall_time_utc": wall_time.astimezone(timezone.utc).isoformat(),
        "pause_service_name": PAUSE_SERVICE,
        "pause_service_type": PAUSE_SERVICE_TYPE,
        "request": {"data": False},
        "response_success": success,
        "response_message": _response_message(response),
        "pause_service_response": response,
        "subprocess_returncode": returncode,
        "service_exception": exception,
        "unpause_success": success,
    }


def wait_for_stable_handshake(
    fetch_snapshot: Callable[[], Mapping[str, Any]],
    *,
    stable_poll_required: int = 20,
    poll_interval_seconds: float = 0.1,
    timeout_seconds: float = 30.0,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if stable_poll_required <= 0 or poll_interval_seconds <= 0 or timeout_seconds <= 0:
        raise ValueError("handshake timing values must be positive")
    started = monotonic_ns()
    deadline = started + int(timeout_seconds * 1_000_000_000)
    stable = 0
    last_snapshot: Mapping[str, Any] | None = None
    last_evaluation: dict[str, Any] | None = None
    while monotonic_ns() <= deadline:
        try:
            last_snapshot = fetch_snapshot()
            last_evaluation = evaluate_snapshot(last_snapshot)
        except Exception as exc:  # Fail closed while allowing transient startup.
            last_snapshot = {"fetch_error": f"{type(exc).__name__}: {exc}"}
            last_evaluation = {"snapshot_pass": False}
        stable = stable + 1 if last_evaluation["snapshot_pass"] else 0
        if stable >= stable_poll_required:
            ready = monotonic_ns()
            return {
                "handshake_pass": True,
                "failure_reason": "NONE",
                "stable_poll_required": stable_poll_required,
                "stable_poll_observed": stable,
                "handshake_start_monotonic_ns": started,
                "handshake_ready_monotonic_ns": ready,
                "snapshot": last_snapshot,
                "evaluation": last_evaluation,
            }
        sleep(poll_interval_seconds)
    return {
        "handshake_pass": False,
        "failure_reason": "CONNECTION_STATE_NOT_STABLE_BEFORE_TIMEOUT",
        "stable_poll_required": stable_poll_required,
        "stable_poll_observed": stable,
        "handshake_start_monotonic_ns": started,
        "handshake_ready_monotonic_ns": None,
        "snapshot": last_snapshot,
        "evaluation": last_evaluation,
    }


def perform_handshake_and_unpause(
    fetch_snapshot: Callable[[], Mapping[str, Any]],
    *,
    stable_poll_required: int = 20,
    poll_interval_seconds: float = 0.1,
    timeout_seconds: float = 30.0,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    sleep: Callable[[float], None] = time.sleep,
    unpause: Callable[[], Mapping[str, Any]] = invoke_unpause_service,
) -> dict[str, Any]:
    result = wait_for_stable_handshake(
        fetch_snapshot,
        stable_poll_required=stable_poll_required,
        poll_interval_seconds=poll_interval_seconds,
        timeout_seconds=timeout_seconds,
        monotonic_ns=monotonic_ns,
        sleep=sleep,
    )
    if not result["handshake_pass"]:
        result.update(
            {
                "unpause_call_start_monotonic_ns": None,
                "unpause_call_end_monotonic_ns": None,
                "unpause_wall_time_utc": None,
                "pause_service_name": PAUSE_SERVICE,
                "pause_service_type": PAUSE_SERVICE_TYPE,
                "request": {"data": False},
                "response_success": False,
                "response_message": None,
                "pause_service_response": "",
                "subprocess_returncode": None,
                "service_exception": None,
                "unpause_success": False,
            }
        )
        return result
    service = dict(unpause())
    result.update(service)
    ordered = (
        result["handshake_start_monotonic_ns"]
        <= result["handshake_ready_monotonic_ns"]
        <= result["unpause_call_start_monotonic_ns"]
        <= result["unpause_call_end_monotonic_ns"]
    )
    if not result.get("unpause_success") or not ordered:
        result["handshake_pass"] = False
        result["failure_reason"] = (
            "PAUSE_SERVICE_CALL_FAILED" if not result.get("unpause_success") else "MONOTONIC_TIME_ORDER_INVALID"
        )
    return result


def _xmlrpc_call(uri: str, method: str, *args: Any) -> Any:
    proxy = xmlrpc.client.ServerProxy(
        uri, allow_none=True, transport=TimeoutTransport()
    )
    code, message, value = getattr(proxy, method)(*args)
    if code != 1:
        raise HandshakeError(f"{method} failed: {message}")
    return value


@dataclass
class RosSnapshotFetcher:
    master_uri: str
    caller_id: str = "/day5_startup_sync_handshake"

    def __call__(self) -> Mapping[str, Any]:
        state = _xmlrpc_call(self.master_uri, "getSystemState", self.caller_id)
        bag_uri = _xmlrpc_call(
            self.master_uri, "lookupNode", self.caller_id, BAG_PLAYER
        )
        laser_uri = _xmlrpc_call(
            self.master_uri, "lookupNode", self.caller_id, LASER_MAPPING
        )
        try:
            import rosservice  # type: ignore

            pause_type = rosservice.get_service_type(PAUSE_SERVICE)
        except Exception:
            pause_type = None
        return {
            "publisher_state": state[0],
            "subscriber_state": state[1],
            "service_state": state[2],
            "publisher_bus_info": _xmlrpc_call(
                bag_uri, "getBusInfo", self.caller_id
            ),
            "subscriber_bus_info": _xmlrpc_call(
                laser_uri, "getBusInfo", self.caller_id
            ),
            "bag_player_node_uri": bag_uri,
            "laser_mapping_node_uri": laser_uri,
            "pause_service_type": pause_type,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--sequence-id", required=True)
    parser.add_argument("--repeat-id", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--master-uri", default=os.environ.get("ROS_MASTER_URI"))
    parser.add_argument("--stable-polls", type=int, default=20)
    parser.add_argument("--poll-interval", type=float, default=0.1)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.master_uri:
        raise SystemExit("ERROR: ROS_MASTER_URI is required")
    result = perform_handshake_and_unpause(
        RosSnapshotFetcher(args.master_uri),
        stable_poll_required=args.stable_polls,
        poll_interval_seconds=args.poll_interval,
        timeout_seconds=args.timeout,
    )
    snapshot = result.pop("snapshot") or {}
    evaluation = result.pop("evaluation") or {}
    output = {
        "protocol_version": PROTOCOL_VERSION,
        "run_id": args.run_id,
        "sequence_id": args.sequence_id,
        "repeat_id": args.repeat_id,
        "ros_master_uri": args.master_uri,
        "ros_master_port": int(args.master_uri.rsplit(":", 1)[1]),
        "laser_mapping_node_uri": snapshot.get("laser_mapping_node_uri"),
        "bag_player_node_uri": snapshot.get("bag_player_node_uri"),
        "publisher_state": snapshot.get("publisher_state", []),
        "subscriber_state": snapshot.get("subscriber_state", []),
        "publisher_bus_info": snapshot.get("publisher_bus_info", []),
        "subscriber_bus_info": snapshot.get("subscriber_bus_info", []),
        **evaluation,
        **result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0 if output["handshake_pass"] and output["unpause_success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
