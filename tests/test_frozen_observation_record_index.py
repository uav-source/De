import pytest

from fastlio2_adapter.frozen_observation import (
    FrozenObservationError,
    validate_record_index,
)


def rows():
    return [
        {
            "record_index": index,
            "scan_index": index + 10,
            "measurement_call_index": 1,
            "binary_offset": 16 + index * 20,
            "binary_record_length": 20,
        }
        for index in range(3)
    ]


def validate(value):
    return validate_record_index(
        value, binary_size=16 + 3 * 20 + 24, trailer_offset=16 + 3 * 20
    )


def test_index_is_contiguous_and_offsets_are_bounded():
    assert validate(rows())["record_index_pass"] is True


def test_noncontiguous_index_fails():
    value = rows()
    value[1]["record_index"] = 4
    with pytest.raises(FrozenObservationError):
        validate(value)


def test_scan_index_must_increase():
    value = rows()
    value[2]["scan_index"] = value[1]["scan_index"]
    with pytest.raises(FrozenObservationError):
        validate(value)


def test_duplicate_record_fails():
    value = rows()
    value[1]["scan_index"] = value[0]["scan_index"]
    with pytest.raises(FrozenObservationError):
        validate(value)


def test_offset_gap_fails():
    value = rows()
    value[1]["binary_offset"] += 1
    with pytest.raises(FrozenObservationError):
        validate(value)


def test_offset_beyond_trailer_fails():
    value = rows()
    value[-1]["binary_record_length"] += 1
    with pytest.raises(FrozenObservationError):
        validate(value)
