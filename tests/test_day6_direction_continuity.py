import math

from fastlio2_adapter.day6_continuity_metrics import (
    direction_continuity,
    sign_invariant_angle_deg,
)


def test_sign_invariant_angle_treats_u_and_minus_u_as_zero():
    assert sign_invariant_angle_deg([1, 0, 0], [-1, 0, 0]) == 0.0
    assert math.isclose(
        sign_invariant_angle_deg([1, 0, 0], [0, 1, 0]), 90.0
    )


def test_null_and_unstable_directions_are_not_eligible():
    outputs = [
        {
            "record_index": 0,
            "scan_index": 3,
            "valid": True,
            "primary_direction_stable": True,
            "primary_weak_direction": [1, 0, 0],
        },
        {
            "record_index": 1,
            "scan_index": 4,
            "valid": False,
            "primary_direction_stable": False,
            "primary_weak_direction": None,
        },
        {
            "record_index": 2,
            "scan_index": 5,
            "valid": True,
            "primary_direction_stable": True,
            "primary_weak_direction": [-1, 0, 0],
        },
    ]
    rows, summary = direction_continuity(outputs)
    assert len(rows) == 1
    assert summary["eligible_direction_record_count"] == 2
    assert summary["null_direction_count"] == 1
    assert summary["angle_max_deg"] == 0.0
