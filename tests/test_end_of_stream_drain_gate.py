from __future__ import annotations

from collections import OrderedDict

import pytest

from fastlio2_adapter.end_of_stream_drain import (
    DrainError,
    expected_status_checksum,
    wait_for_drain,
)


ENDPOINT = {
    "expected_lidar_message_count": 1,
    "expected_imu_message_count": 1,
    "last_lidar_header_stamp_ns": 10,
    "last_imu_header_stamp_ns": 20,
}


def make_snapshot(heartbeat: int, processed: int = 1) -> OrderedDict[str, object]:
    value: OrderedDict[str, object] = OrderedDict(
        schema_version="fastlio2_end_of_stream_status_v1",
        lidar_callback_count=1,
        imu_callback_count=1,
        last_lidar_header_stamp_ns=10,
        last_imu_raw_header_stamp_ns=20,
        last_imu_adjusted_header_stamp_ns=20,
        processed_measure_group_count=processed,
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


def test_twenty_stable_polls_pass() -> None:
    heartbeat = iter(range(1, 30))
    result, trace = wait_for_drain(
        lambda: make_snapshot(next(heartbeat)),
        ENDPOINT,
        sleep=lambda _seconds: None,
        monotonic_ns=iter(range(0, 1_000_000_000, 1_000_000)).__next__,
    )
    assert result["drain_pass"]
    assert result["stable_poll_observed"] == 20
    assert len(trace) == 20


def test_nineteen_stable_polls_do_not_pass() -> None:
    heartbeat = iter(range(1, 100))
    clock = iter(range(0, 22_000_000, 1_000_000))
    with pytest.raises(DrainError) as error:
        wait_for_drain(
            lambda: make_snapshot(next(heartbeat)),
            ENDPOINT,
            timeout_sec=0.019,
            sleep=lambda _seconds: None,
            monotonic_ns=clock.__next__,
        )
    assert error.value.classification == "END_OF_STREAM_DRAIN_TIMEOUT"


def test_state_change_resets_window() -> None:
    states = [make_snapshot(index, processed=1) for index in range(1, 5)]
    states += [make_snapshot(index, processed=2) for index in range(5, 30)]
    iterator = iter(states)
    result, trace = wait_for_drain(
        lambda: next(iterator),
        ENDPOINT,
        stable_required=5,
        sleep=lambda _seconds: None,
        monotonic_ns=iter(range(0, 1_000_000_000, 1_000_000)).__next__,
    )
    assert result["stable_poll_observed"] == 5
    assert len(trace) == 9
