import pytest

from fastlio2_adapter.day6_continuity_metrics import (
    ContinuityError,
    output_continuity,
)


def rows(count=5):
    return [
        {
            "scan_index": index + 3,
            "timestamp_begin": float(index),
            "timestamp_end": float(index) + 0.1,
        }
        for index in range(count)
    ]


def test_complete_monotonic_output_stream_passes():
    summary = output_continuity(rows(), rows())
    assert summary["missing_output_count"] == 0
    assert summary["duplicate_scan_index_count"] == 0
    assert summary["output_continuity_diagnostics_pass"] is True


def test_missing_output_fails():
    with pytest.raises(ContinuityError, match="continuity"):
        output_continuity(rows(), rows()[:-1])


def test_timestamp_backward_fails():
    outputs = rows()
    outputs[3]["timestamp_begin"] = -1.0
    with pytest.raises(ContinuityError, match="continuity"):
        output_continuity(rows(), outputs)


def test_duplicate_scan_fails():
    outputs = rows()
    outputs[3]["scan_index"] = outputs[2]["scan_index"]
    with pytest.raises(ContinuityError, match="continuity"):
        output_continuity(rows(), outputs)
