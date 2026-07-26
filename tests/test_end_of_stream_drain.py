from __future__ import annotations

from collections import OrderedDict

import pytest

from fastlio2_adapter.end_of_stream_drain import (
    STATUS_FIELDS,
    DrainError,
    DrainTracker,
    expected_status_checksum,
    validate_status,
)


ENDPOINT = {
    "expected_lidar_message_count": 2,
    "expected_imu_message_count": 3,
    "last_lidar_header_stamp_ns": 20,
    "last_imu_header_stamp_ns": 30,
}


def snapshot(**changes: object) -> OrderedDict[str, object]:
    value: OrderedDict[str, object] = OrderedDict(
        [
            ("schema_version", "fastlio2_end_of_stream_status_v1"),
            ("lidar_callback_count", 2),
            ("imu_callback_count", 3),
            ("last_lidar_header_stamp_ns", 20),
            ("last_imu_raw_header_stamp_ns", 30),
            ("last_imu_adjusted_header_stamp_ns", 29),
            ("processed_measure_group_count", 1),
            ("last_processed_lidar_begin_stamp_ns", 10),
            ("last_processed_lidar_end_stamp_ns", 19),
            ("lidar_buffer_size", 1),
            ("imu_buffer_size", 0),
            ("time_buffer_size", 1),
            ("lidar_pushed", True),
            ("current_lidar_end_time_ns", 40),
            ("last_timestamp_imu_ns", 29),
            ("front_scan_evaluated", True),
            ("processable_measure_group", False),
            ("main_loop_iteration_count", 100),
            ("runtime_audit_record_count", 1),
        ]
    )
    value.update(changes)
    value["status_checksum"] = expected_status_checksum(value)
    value["service_wall_time_utc"] = "2026-01-01T00:00:00.000000Z"
    return value


def test_status_schema_order_and_checksum() -> None:
    value = snapshot()
    assert tuple(value) == STATUS_FIELDS + ("status_checksum", "service_wall_time_utc")
    assert validate_status(value)["lidar_buffer_size"] == 1
    changed = snapshot()
    changed["status_checksum"] = "FNV1A64:0000000000000000"
    with pytest.raises(DrainError, match="checksum"):
        validate_status(changed)


@pytest.mark.parametrize(
    ("changes", "failure"),
    [
        ({"lidar_callback_count": 1}, "LIDAR_CALLBACK_COUNT_INCOMPLETE"),
        ({"imu_callback_count": 2}, "IMU_CALLBACK_COUNT_INCOMPLETE"),
        ({"lidar_callback_count": 3}, "CALLBACK_COUNT_EXCEEDED_EXPECTATION"),
        ({"last_lidar_header_stamp_ns": 21}, "LAST_LIDAR_STAMP_MISMATCH"),
        ({"last_imu_raw_header_stamp_ns": 31}, "LAST_IMU_STAMP_MISMATCH"),
        ({"front_scan_evaluated": False}, "FRONT_SCAN_NOT_EVALUATED"),
        ({"processable_measure_group": True}, "PROCESSABLE_MEASURE_GROUP_REMAINS"),
        ({"time_buffer_size": 0}, "DRAIN_STATE_NOT_STABLE"),
    ],
)
def test_gate_failure_classes(changes: dict[str, object], failure: str) -> None:
    tracker = DrainTracker(ENDPOINT)
    assert not tracker.observe(snapshot(**changes))
    assert tracker.last_failure == failure


def test_nonempty_unprocessable_tail_is_allowed() -> None:
    tracker = DrainTracker(ENDPOINT, stable_required=2)
    assert not tracker.observe(snapshot(main_loop_iteration_count=1))
    assert tracker.observe(snapshot(main_loop_iteration_count=2))


def test_main_loop_must_advance() -> None:
    tracker = DrainTracker(ENDPOINT, stable_required=2)
    assert not tracker.observe(snapshot(main_loop_iteration_count=7))
    assert not tracker.observe(snapshot(main_loop_iteration_count=7))
    assert tracker.last_failure == "MAIN_LOOP_HEARTBEAT_STALLED"
