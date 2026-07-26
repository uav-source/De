import csv

import pytest

from fastlio2_adapter.day7_rebuild_logger_analysis import (
    compare_logger_runs,
    load_logger_events,
    logger_event_checksum,
)


FIELDS = (
    "event_sequence",
    "logger_sequence_id",
    "phase",
    "operation_set",
    "scan_index",
    "call_index",
    "batch_point_index",
    "generation",
    "apply_order_index",
    "outcome",
    "point_sha256",
    "box_identity",
    "ordered_logger_checksum_after_append",
    "logical_count_before",
    "logical_count_after",
    "event_checksum",
)


def logger_row(sequence, *, phase="APPEND", point="11" * 32, outcome=None):
    value = {
        "event_sequence": sequence,
        "logger_sequence_id": sequence,
        "phase": phase,
        "operation_set": 0,
        "scan_index": 150 if phase == "APPEND" else 0,
        "call_index": 0,
        "batch_point_index": sequence - 1,
        "generation": 2,
        "apply_order_index": sequence - 1 if phase == "APPLY" else 0,
        "outcome": outcome or (
            "LOGGER_APPEND_ADD_POINT"
            if phase == "APPEND"
            else "REBUILD_LOG_ADD_POINT_APPLIED"
        ),
        "point_sha256": point,
        "box_identity": "",
        "ordered_logger_checksum_after_append": 9 if phase == "APPEND" else 0,
        "logical_count_before": 10 if phase == "APPLY" else 0,
        "logical_count_after": 11 if phase == "APPLY" else 0,
        "event_checksum": 0,
    }
    value["event_checksum"] = logger_event_checksum(value)
    return value


def write_run(directory, rows):
    directory.mkdir()
    with (
        directory / "day7_rebuild_logger_event_index.csv"
    ).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_logger_checksum_validation(tmp_path):
    path = tmp_path / "logger.csv"
    row = logger_row(1)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(row)
    assert load_logger_events(path)[0]["logger_sequence_id"] == 1
    row["event_checksum"] += 1
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(row)
    with pytest.raises(ValueError, match="checksum"):
        load_logger_events(path)


def test_logger_apply_order_difference_is_detected(tmp_path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    rows = [
        logger_row(1, phase="APPLY", point="11" * 32),
        logger_row(2, phase="APPLY", point="22" * 32),
    ]
    write_run(left, rows)
    write_run(right, [rows[1], rows[0]])
    result = compare_logger_runs(left, right)
    assert result["apply_entry_multiset_equal"] is True
    assert result["apply_order_equal"] is False


def test_logger_apply_result_difference_is_detected(tmp_path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_run(left, [logger_row(1, phase="APPLY")])
    write_run(right, [
        logger_row(
            1,
            phase="APPLY",
            outcome="REBUILD_LOG_DELETE_POINT_APPLIED",
        )
    ])
    result = compare_logger_runs(left, right)
    assert result["apply_order_equal"] is True
    assert result["apply_result_equal"] is False
