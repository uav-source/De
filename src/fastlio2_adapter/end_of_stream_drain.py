"""Read-only end-of-stream drain protocol and deterministic gate logic."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


SCHEMA_VERSION = "fastlio2_end_of_stream_status_v1"
STABLE_POLL_COUNT = 20
POLL_INTERVAL_SEC = 0.1
DRAIN_TIMEOUT_SEC = 60.0
SERVICE_CALL_TIMEOUT_SEC = 2.0
MAX_CONSECUTIVE_SERVICE_TIMEOUTS = 3
STATUS_FIELDS = (
    "schema_version",
    "lidar_callback_count",
    "imu_callback_count",
    "last_lidar_header_stamp_ns",
    "last_imu_raw_header_stamp_ns",
    "last_imu_adjusted_header_stamp_ns",
    "processed_measure_group_count",
    "last_processed_lidar_begin_stamp_ns",
    "last_processed_lidar_end_stamp_ns",
    "lidar_buffer_size",
    "imu_buffer_size",
    "time_buffer_size",
    "lidar_pushed",
    "current_lidar_end_time_ns",
    "last_timestamp_imu_ns",
    "front_scan_evaluated",
    "processable_measure_group",
    "main_loop_iteration_count",
    "runtime_audit_record_count",
)
STABLE_FIELDS = (
    "processed_measure_group_count",
    "last_processed_lidar_begin_stamp_ns",
    "last_processed_lidar_end_stamp_ns",
    "lidar_buffer_size",
    "imu_buffer_size",
    "time_buffer_size",
    "lidar_pushed",
    "current_lidar_end_time_ns",
    "last_timestamp_imu_ns",
    "runtime_audit_record_count",
)
FAILURES = {
    "ENDPOINT_CONTRACT_MISMATCH",
    "LIDAR_CALLBACK_COUNT_INCOMPLETE",
    "IMU_CALLBACK_COUNT_INCOMPLETE",
    "CALLBACK_COUNT_EXCEEDED_EXPECTATION",
    "LAST_LIDAR_STAMP_MISMATCH",
    "LAST_IMU_STAMP_MISMATCH",
    "FRONT_SCAN_NOT_EVALUATED",
    "PROCESSABLE_MEASURE_GROUP_REMAINS",
    "MAIN_LOOP_HEARTBEAT_STALLED",
    "DRAIN_STATE_NOT_STABLE",
    "DRAIN_SERVICE_UNAVAILABLE",
    "DRAIN_SERVICE_SCHEMA_INVALID",
    "DRAIN_STATUS_CHECKSUM_INVALID",
    "DRAIN_SERVICE_CALL_TIMEOUT",
    "DRAIN_SERVICE_INVALID_RESPONSE",
    "END_OF_STREAM_DRAIN_TIMEOUT",
    "NONE",
}


class DrainError(RuntimeError):
    def __init__(
        self,
        classification: str,
        message: str,
        *,
        trace: Iterable[Mapping[str, Any]] = (),
        service_call_timeout_count: int = 0,
        max_consecutive_service_timeouts: int = 0,
    ) -> None:
        super().__init__(message)
        if classification not in FAILURES:
            raise ValueError(f"unknown drain classification: {classification}")
        self.classification = classification
        self.trace = [dict(row) for row in trace]
        self.service_call_timeout_count = int(service_call_timeout_count)
        self.max_consecutive_service_timeouts = int(
            max_consecutive_service_timeouts
        )


@dataclass(frozen=True)
class ServicePoll:
    snapshot: Mapping[str, Any] | None
    evidence: Mapping[str, Any]


def _trigger_response(stdout: str) -> tuple[Mapping[str, Any], bool]:
    try:
        import yaml

        parsed = yaml.safe_load(stdout)
    except Exception as error:
        raise DrainError(
            "DRAIN_SERVICE_INVALID_RESPONSE",
            f"cannot parse Trigger response YAML: {error}",
        ) from error
    if not isinstance(parsed, Mapping):
        raise DrainError(
            "DRAIN_SERVICE_INVALID_RESPONSE",
            "Trigger response is not a mapping",
        )
    trigger_success = parsed.get("success")
    if not isinstance(trigger_success, bool):
        raise DrainError(
            "DRAIN_SERVICE_INVALID_RESPONSE",
            "Trigger success is not boolean",
        )
    message = parsed.get("message")
    if not isinstance(message, str):
        raise DrainError(
            "DRAIN_SERVICE_INVALID_RESPONSE",
            "Trigger message is not text",
        )
    try:
        snapshot = json.loads(message)
    except json.JSONDecodeError as error:
        raise DrainError(
            "DRAIN_SERVICE_INVALID_RESPONSE",
            f"Trigger message is not JSON: {error}",
        ) from error
    if not isinstance(snapshot, Mapping):
        raise DrainError(
            "DRAIN_SERVICE_INVALID_RESPONSE",
            "Trigger JSON is not an object",
        )
    return snapshot, trigger_success


def bounded_trigger_call(
    service_name: str,
    *,
    environment: Mapping[str, str] | None = None,
    timeout_sec: float = SERVICE_CALL_TIMEOUT_SEC,
    command_prefix: Sequence[str] = ("rosservice", "call"),
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
) -> ServicePoll:
    if timeout_sec <= 0:
        raise ValueError("service call timeout must be positive")
    started = monotonic_ns()
    command = [*command_prefix, service_name]
    returncode: int | None = None
    stdout = ""
    timed_out = False
    exception = ""
    parse_pass = False
    trigger_success = False
    snapshot: Mapping[str, Any] | None = None
    try:
        completed = run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=(dict(environment) if environment is not None else os.environ.copy()),
        )
        returncode = int(completed.returncode)
        stdout = (completed.stdout or "") + (completed.stderr or "")
        if returncode == 0:
            snapshot, trigger_success = _trigger_response(stdout)
            parse_pass = True
        else:
            exception = f"rosservice exit code {returncode}: {stdout.strip()}"
    except subprocess.TimeoutExpired as error:
        timed_out = True
        exception = f"service call exceeded {timeout_sec:.3f}s wall timeout"
        stdout = str(error.stdout or "")
    except DrainError as error:
        exception = str(error)
    except Exception as error:
        exception = f"{type(error).__name__}: {error}"
    ended = monotonic_ns()
    return ServicePoll(
        snapshot=snapshot,
        evidence={
            "call_start_monotonic_ns": started,
            "call_end_monotonic_ns": ended,
            "call_duration_ms": (ended - started) / 1_000_000.0,
            "service_returncode": returncode,
            "service_success": trigger_success,
            "service_message_parse_pass": parse_pass,
            "service_timeout": timed_out,
            "service_exception": exception,
        },
    )


def fnv1a64(data: bytes) -> int:
    value = 14695981039346656037
    for byte in data:
        value ^= byte
        value = (value * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return value


def status_checksum_payload(snapshot: Mapping[str, Any]) -> bytes:
    values = []
    for field in STATUS_FIELDS:
        value = snapshot[field]
        if isinstance(value, bool):
            encoded = "true" if value else "false"
        else:
            encoded = str(value)
        values.append(f"{field}={encoded}")
    return ("\n".join(values) + "\n").encode("utf-8")


def expected_status_checksum(snapshot: Mapping[str, Any]) -> str:
    return f"FNV1A64:{fnv1a64(status_checksum_payload(snapshot)):016x}"


def validate_status(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if tuple(snapshot) != STATUS_FIELDS + ("status_checksum", "service_wall_time_utc"):
        raise DrainError("DRAIN_SERVICE_SCHEMA_INVALID", "status field order/schema mismatch")
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise DrainError("DRAIN_SERVICE_SCHEMA_INVALID", "status schema version mismatch")
    if snapshot.get("status_checksum") != expected_status_checksum(snapshot):
        raise DrainError("DRAIN_STATUS_CHECKSUM_INVALID", "status checksum mismatch")
    return dict(snapshot)


def readiness_failure(snapshot: Mapping[str, Any], endpoint: Mapping[str, Any]) -> str:
    lidar = int(snapshot["lidar_callback_count"])
    imu = int(snapshot["imu_callback_count"])
    expected_lidar = int(endpoint["expected_lidar_message_count"])
    expected_imu = int(endpoint["expected_imu_message_count"])
    if lidar > expected_lidar or imu > expected_imu:
        return "CALLBACK_COUNT_EXCEEDED_EXPECTATION"
    if lidar < expected_lidar:
        return "LIDAR_CALLBACK_COUNT_INCOMPLETE"
    if imu < expected_imu:
        return "IMU_CALLBACK_COUNT_INCOMPLETE"
    if int(snapshot["last_lidar_header_stamp_ns"]) != int(endpoint["last_lidar_header_stamp_ns"]):
        return "LAST_LIDAR_STAMP_MISMATCH"
    if int(snapshot["last_imu_raw_header_stamp_ns"]) != int(endpoint["last_imu_header_stamp_ns"]):
        return "LAST_IMU_STAMP_MISMATCH"
    if not bool(snapshot["front_scan_evaluated"]):
        return "FRONT_SCAN_NOT_EVALUATED"
    if bool(snapshot["processable_measure_group"]):
        return "PROCESSABLE_MEASURE_GROUP_REMAINS"
    if int(snapshot["time_buffer_size"]) != int(snapshot["lidar_buffer_size"]):
        return "DRAIN_STATE_NOT_STABLE"
    return "NONE"


@dataclass
class DrainTracker:
    endpoint: Mapping[str, Any]
    stable_required: int = STABLE_POLL_COUNT
    stable_observed: int = 0
    prior_stable: tuple[Any, ...] | None = None
    prior_heartbeat: int | None = None
    heartbeat_start: int | None = None
    heartbeat_end: int | None = None
    last_failure: str = "DRAIN_STATE_NOT_STABLE"

    def observe(self, raw_snapshot: Mapping[str, Any]) -> bool:
        snapshot = validate_status(raw_snapshot)
        heartbeat = int(snapshot["main_loop_iteration_count"])
        if self.heartbeat_start is None:
            self.heartbeat_start = heartbeat
        self.heartbeat_end = heartbeat
        failure = readiness_failure(snapshot, self.endpoint)
        heartbeat_ok = self.prior_heartbeat is None or heartbeat > self.prior_heartbeat
        self.prior_heartbeat = heartbeat
        if not heartbeat_ok:
            self.stable_observed = 0
            self.prior_stable = None
            self.last_failure = "MAIN_LOOP_HEARTBEAT_STALLED"
            return False
        if failure != "NONE":
            self.stable_observed = 0
            self.prior_stable = None
            self.last_failure = failure
            return False
        stable = tuple(snapshot[field] for field in STABLE_FIELDS)
        if self.prior_stable is None or stable != self.prior_stable:
            self.stable_observed = 1
            self.prior_stable = stable
        else:
            self.stable_observed += 1
        self.last_failure = "NONE" if self.stable_observed >= self.stable_required else "DRAIN_STATE_NOT_STABLE"
        return self.stable_observed >= self.stable_required


def wait_for_drain(
    fetch_snapshot: Callable[[], Mapping[str, Any] | ServicePoll],
    endpoint: Mapping[str, Any],
    *,
    stable_required: int = STABLE_POLL_COUNT,
    poll_interval_sec: float = POLL_INTERVAL_SEC,
    timeout_sec: float = DRAIN_TIMEOUT_SEC,
    max_consecutive_service_timeouts: int = MAX_CONSECUTIVE_SERVICE_TIMEOUTS,
    monotonic_ns: Callable[[], int] = time.monotonic_ns,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if max_consecutive_service_timeouts <= 0:
        raise ValueError("max consecutive service timeouts must be positive")
    tracker = DrainTracker(endpoint=endpoint, stable_required=stable_required)
    started = monotonic_ns()
    deadline = started + int(timeout_sec * 1_000_000_000)
    trace: list[dict[str, Any]] = []
    last: dict[str, Any] | None = None
    service_call_timeout_count = 0
    consecutive_service_timeouts = 0
    observed_max_consecutive_timeouts = 0
    while monotonic_ns() <= deadline:
        call_started = monotonic_ns()
        try:
            fetched = fetch_snapshot()
        except DrainError as error:
            error.trace = [*trace, *error.trace]
            error.service_call_timeout_count += service_call_timeout_count
            error.max_consecutive_service_timeouts = max(
                error.max_consecutive_service_timeouts,
                observed_max_consecutive_timeouts,
            )
            raise
        except Exception as error:
            raise DrainError(
                "DRAIN_SERVICE_INVALID_RESPONSE",
                str(error),
                trace=trace,
                service_call_timeout_count=service_call_timeout_count,
                max_consecutive_service_timeouts=observed_max_consecutive_timeouts,
            ) from error
        call_ended = monotonic_ns()
        if isinstance(fetched, ServicePoll):
            evidence = dict(fetched.evidence)
            if bool(evidence.get("service_timeout")):
                service_call_timeout_count += 1
                consecutive_service_timeouts += 1
                observed_max_consecutive_timeouts = max(
                    observed_max_consecutive_timeouts,
                    consecutive_service_timeouts,
                )
                tracker.stable_observed = 0
                tracker.prior_stable = None
                tracker.last_failure = "DRAIN_SERVICE_CALL_TIMEOUT"
                trace.append(
                    {
                        "poll_index": len(trace) + 1,
                        **evidence,
                        "consecutive_timeout_count": consecutive_service_timeouts,
                        "stable_poll_observed": tracker.stable_observed,
                        "ready": False,
                        "readiness_failure": tracker.last_failure,
                    }
                )
                if (
                    consecutive_service_timeouts
                    >= max_consecutive_service_timeouts
                ):
                    raise DrainError(
                        "DRAIN_SERVICE_CALL_TIMEOUT",
                        "maximum consecutive wall-time service call timeouts reached",
                        trace=trace,
                        service_call_timeout_count=service_call_timeout_count,
                        max_consecutive_service_timeouts=observed_max_consecutive_timeouts,
                    )
                sleep(poll_interval_sec)
                continue
            consecutive_service_timeouts = 0
            if (
                fetched.snapshot is None
                or evidence.get("service_success") is not True
            ):
                trace.append(
                    {
                        "poll_index": len(trace) + 1,
                        **evidence,
                        "consecutive_timeout_count": 0,
                        "stable_poll_observed": 0,
                        "ready": False,
                        "readiness_failure": "DRAIN_SERVICE_INVALID_RESPONSE",
                    }
                )
                raise DrainError(
                    "DRAIN_SERVICE_INVALID_RESPONSE",
                    str(evidence.get("service_exception") or "invalid service response"),
                    trace=trace,
                    service_call_timeout_count=service_call_timeout_count,
                    max_consecutive_service_timeouts=observed_max_consecutive_timeouts,
                )
            raw_snapshot = fetched.snapshot
        else:
            consecutive_service_timeouts = 0
            raw_snapshot = fetched
            evidence = {
                "call_start_monotonic_ns": call_started,
                "call_end_monotonic_ns": call_ended,
                "call_duration_ms": (call_ended - call_started) / 1_000_000.0,
                "service_returncode": 0,
                "service_success": True,
                "service_message_parse_pass": True,
                "service_timeout": False,
                "service_exception": "",
            }
        try:
            last = validate_status(raw_snapshot)
        except DrainError as error:
            trace.append(
                {
                    "poll_index": len(trace) + 1,
                    **evidence,
                    "consecutive_timeout_count": consecutive_service_timeouts,
                    "stable_poll_observed": 0,
                    "ready": False,
                    "readiness_failure": error.classification,
                }
            )
            raise DrainError(
                error.classification,
                str(error),
                trace=trace,
                service_call_timeout_count=service_call_timeout_count,
                max_consecutive_service_timeouts=observed_max_consecutive_timeouts,
            ) from error
        ready = tracker.observe(last)
        trace.append(
            {
                "poll_index": len(trace) + 1,
                "poll_monotonic_ns": monotonic_ns(),
                **evidence,
                "consecutive_timeout_count": consecutive_service_timeouts,
                "stable_poll_observed": tracker.stable_observed,
                "ready": ready,
                "readiness_failure": tracker.last_failure,
                **last,
            }
        )
        if ready:
            ready_ns = monotonic_ns()
            result = {
                "final_snapshot": last,
                "stable_poll_required": stable_required,
                "stable_poll_observed": tracker.stable_observed,
                "drain_start_monotonic_ns": started,
                "drain_ready_monotonic_ns": ready_ns,
                "drain_duration_ms": (ready_ns - started) / 1_000_000.0,
                "main_loop_heartbeat_start": tracker.heartbeat_start,
                "main_loop_heartbeat_end": tracker.heartbeat_end,
                "service_call_timeout_count": service_call_timeout_count,
                "max_consecutive_service_timeouts": (
                    observed_max_consecutive_timeouts
                ),
                "drain_pass": True,
                "failure_classification": "NONE",
            }
            return result, trace
        sleep(poll_interval_sec)
    raise DrainError(
        "END_OF_STREAM_DRAIN_TIMEOUT",
        f"drain timeout; last condition={tracker.last_failure}",
        trace=trace,
        service_call_timeout_count=service_call_timeout_count,
        max_consecutive_service_timeouts=observed_max_consecutive_timeouts,
    )


def write_poll_trace(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["poll_index"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
