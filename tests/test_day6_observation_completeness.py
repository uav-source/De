import pytest

from fastlio2_adapter.day6_fallback_functional_diagnostics import (
    Day6FallbackError,
    validate_record_index,
)


def row(index):
    return {
        "record_index": index,
        "scan_index": index + 3,
        "timestamp_begin": repr(float(index)),
        "timestamp_end": repr(float(index) + 0.1),
    }


def record(index):
    return {
        "scan_index": index + 3,
        "timestamp_begin": float(index),
        "timestamp_end": float(index) + 0.1,
    }


def test_complete_record_index_is_accepted():
    rows = [row(index) for index in range(487)]
    records = [record(index) for index in range(487)]
    assert validate_record_index(rows, records)["record_index_pass"] is True


def test_non_487_record_index_is_rejected():
    with pytest.raises(Day6FallbackError, match="count mismatch"):
        validate_record_index([row(0)], [record(0)])


def test_duplicate_or_reordered_record_index_is_rejected():
    rows = [row(index) for index in range(487)]
    records = [record(index) for index in range(487)]
    rows[10]["record_index"] = 9
    with pytest.raises(Day6FallbackError, match="contiguous"):
        validate_record_index(rows, records)
