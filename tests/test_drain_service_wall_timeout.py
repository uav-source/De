from __future__ import annotations

import json
import subprocess
from collections import OrderedDict

import pytest

from fastlio2_adapter.end_of_stream_drain import (
    SERVICE_CALL_TIMEOUT_SEC,
    DrainError,
    ServicePoll,
    bounded_trigger_call,
    expected_status_checksum,
    wait_for_drain,
)


ENDPOINT = {
    "expected_lidar_message_count": 1,
    "expected_imu_message_count": 1,
    "last_lidar_header_stamp_ns": 10,
    "last_imu_header_stamp_ns": 20,
}


def snapshot(heartbeat: int) -> OrderedDict[str, object]:
    value: OrderedDict[str, object] = OrderedDict(
        schema_version="fastlio2_end_of_stream_status_v1",
        lidar_callback_count=1,
        imu_callback_count=1,
        last_lidar_header_stamp_ns=10,
        last_imu_raw_header_stamp_ns=20,
        last_imu_adjusted_header_stamp_ns=20,
        processed_measure_group_count=1,
        last_processed_lidar_begin_stamp_ns=10,
        last_processed_lidar_end_stamp_ns=11,
        lidar_buffer_size=0,
        imu_buffer_size=0,
        time_buffer_size=0,
        lidar_pushed=False,
        current_lidar_end_time_ns=11,
        last_timestamp_imu_ns=20,
        front_scan_evaluated=True,
        processable_measure_group=False,
        main_loop_iteration_count=heartbeat,
        runtime_audit_record_count=1,
    )
    value["status_checksum"] = expected_status_checksum(value)
    value["service_wall_time_utc"] = "2026-01-01T00:00:00.000000Z"
    return value


def timeout_poll(index: int) -> ServicePoll:
    return ServicePoll(
        snapshot=None,
        evidence={
            "call_start_monotonic_ns": index * 10,
            "call_end_monotonic_ns": index * 10 + 2,
            "call_duration_ms": 2000.0,
            "service_returncode": None,
            "service_success": False,
            "service_message_parse_pass": False,
            "service_timeout": True,
            "service_exception": "timeout",
        },
    )


def test_bounded_call_passes_exact_wall_timeout_to_subprocess() -> None:
    observed: dict[str, object] = {}

    def fake_run(command, **kwargs):
        observed["command"] = command
        observed["timeout"] = kwargs["timeout"]
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    poll = bounded_trigger_call(
        "/harmful_bias/end_of_stream_status",
        timeout_sec=SERVICE_CALL_TIMEOUT_SEC,
        run=fake_run,
        monotonic_ns=iter((1, 2)).__next__,
    )
    assert observed["timeout"] == 2.0
    assert poll.evidence["service_timeout"] is True
    assert poll.snapshot is None


def test_three_consecutive_timeouts_fail_immediately() -> None:
    polls = iter(timeout_poll(index) for index in range(3))
    with pytest.raises(DrainError) as caught:
        wait_for_drain(
            lambda: next(polls),
            ENDPOINT,
            sleep=lambda _seconds: None,
            monotonic_ns=iter(range(100)).__next__,
        )
    assert caught.value.classification == "DRAIN_SERVICE_CALL_TIMEOUT"
    assert caught.value.service_call_timeout_count == 3
    assert caught.value.max_consecutive_service_timeouts == 3
    assert len(caught.value.trace) == 3


def test_successful_call_resets_consecutive_timeout_count() -> None:
    heartbeat = iter(range(1, 30))
    polls = iter(
        [
            timeout_poll(1),
            ServicePoll(snapshot(1), {
                "call_start_monotonic_ns": 1,
                "call_end_monotonic_ns": 2,
                "call_duration_ms": 1.0,
                "service_returncode": 0,
                "service_success": True,
                "service_message_parse_pass": True,
                "service_timeout": False,
                "service_exception": "",
            }),
            timeout_poll(2),
            *[
                ServicePoll(snapshot(next(heartbeat) + 1), {
                    "call_start_monotonic_ns": 1,
                    "call_end_monotonic_ns": 2,
                    "call_duration_ms": 1.0,
                    "service_returncode": 0,
                    "service_success": True,
                    "service_message_parse_pass": True,
                    "service_timeout": False,
                    "service_exception": "",
                })
                for _ in range(25)
            ],
        ]
    )
    result, trace = wait_for_drain(
        lambda: next(polls),
        ENDPOINT,
        stable_required=3,
        sleep=lambda _seconds: None,
        monotonic_ns=iter(range(1000)).__next__,
    )
    assert result["drain_pass"]
    assert result["service_call_timeout_count"] == 2
    assert result["max_consecutive_service_timeouts"] == 1
    assert any(row["service_timeout"] for row in trace)


def test_nonzero_service_result_fails_as_invalid_response() -> None:
    def fake_run(_command, **_kwargs):
        return subprocess.CompletedProcess([], 1, stdout="failure", stderr="")

    poll = bounded_trigger_call(
        "/harmful_bias/end_of_stream_status",
        run=fake_run,
        monotonic_ns=iter((1, 2)).__next__,
    )
    with pytest.raises(DrainError) as caught:
        wait_for_drain(
            lambda: poll,
            ENDPOINT,
            sleep=lambda _seconds: None,
            monotonic_ns=iter(range(20)).__next__,
        )
    assert caught.value.classification == "DRAIN_SERVICE_INVALID_RESPONSE"
    assert caught.value.trace[0]["service_returncode"] == 1


def test_trigger_failure_payload_is_parsed_but_drain_rejects_it() -> None:
    payload = json.dumps({"failure_reason": "TAIL_CLOCK_NO_BAG_CLOCK"})

    def fake_run(_command, **_kwargs):
        return subprocess.CompletedProcess(
            [],
            0,
            stdout=f"success: false\nmessage: '{payload}'\n",
            stderr="",
        )

    poll = bounded_trigger_call(
        "/day5_tail_clock/start",
        run=fake_run,
        monotonic_ns=iter((1, 2)).__next__,
    )
    assert poll.snapshot == {"failure_reason": "TAIL_CLOCK_NO_BAG_CLOCK"}
    assert poll.evidence["service_success"] is False
    with pytest.raises(DrainError) as caught:
        wait_for_drain(
            lambda: poll,
            ENDPOINT,
            sleep=lambda _seconds: None,
            monotonic_ns=iter(range(20)).__next__,
        )
    assert caught.value.classification == "DRAIN_SERVICE_INVALID_RESPONSE"


def test_poll_trace_contains_all_wall_time_fields() -> None:
    polls = iter(timeout_poll(index) for index in range(3))
    with pytest.raises(DrainError) as caught:
        wait_for_drain(
            lambda: next(polls),
            ENDPOINT,
            sleep=lambda _seconds: None,
            monotonic_ns=iter(range(100)).__next__,
        )
    required = {
        "poll_index",
        "call_start_monotonic_ns",
        "call_end_monotonic_ns",
        "call_duration_ms",
        "service_returncode",
        "service_success",
        "service_message_parse_pass",
        "service_timeout",
        "service_exception",
        "consecutive_timeout_count",
    }
    assert required <= set(caught.value.trace[0])
