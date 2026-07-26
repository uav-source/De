import pytest

from fastlio2_adapter.day6_fallback_functional_diagnostics import (
    Day6FallbackError,
)
from fastlio2_adapter.day6_reference_alignment import align_reference_run


def index_rows():
    return [
        {
            "scan_index": index + 3,
            "timestamp_begin": float(index),
            "timestamp_end": float(index) + 0.1,
        }
        for index in range(487)
    ]


def output_rows():
    return [
        {
            **row,
            "valid": True,
            "degeneracy_triggered": False,
            "primary_direction_stable": True,
            "actionable_direction": False,
            "odi_trans": 1.0,
            "ais_trans": 2.0,
            "lambda_min_trans": 3.0,
            "condition_number_trans": 4.0,
            "primary_eigengap_ratio": 0.5,
            "primary_weak_direction": [1.0, 0.0, 0.0],
        }
        for row in index_rows()
    ]


def test_reference_alignment_uses_scan_and_timestamps():
    rows, summary = align_reference_run(
        index_rows(), output_rows(), index_rows(), output_rows()
    )
    assert len(rows) == 487
    assert summary["aligned_count"] == 487
    assert summary["REFERENCE_OUTPUT_BITWISE_EQUALITY_REQUIRED"] is False


def test_reference_missing_record_fails():
    with pytest.raises(Day6FallbackError, match="alignment failed"):
        align_reference_run(
            index_rows(), output_rows(), index_rows()[:-1], output_rows()[:-1]
        )
