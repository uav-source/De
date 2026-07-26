import struct

import pytest

from fastlio2_adapter.mun_frl_contract import (
    decode_point_record,
    point_time_seconds,
    validate_point_times,
)


def test_point_time_is_returned_as_scan_relative_seconds_without_scaling():
    raw = struct.pack("<ffffHf", 1.0, 2.0, 3.0, 4.0, 7, 0.075)
    decoded = decode_point_record(raw)
    assert decoded[5] == pytest.approx(0.075)
    assert point_time_seconds(decoded[5]) == pytest.approx(0.075)


def test_scan_relative_seconds_match_ten_hz_scan_duration():
    summary = validate_point_times([0.0, 0.025, 0.0999], scan_rate_hz=10)
    assert summary["maximum_seconds"] == pytest.approx(0.0999)
    assert summary["span_seconds"] == pytest.approx(0.0999)


def test_millisecond_interpretation_is_not_silently_accepted():
    with pytest.raises(ValueError, match="scan-relative seconds"):
        validate_point_times([0.0, 25.0, 99.9], scan_rate_hz=10)

