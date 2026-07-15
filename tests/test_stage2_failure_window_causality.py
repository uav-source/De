import json

import pytest

from eval.stage2_failure_day9 import compute_window_records
from eval.stage2_failure_schema import ONLINE_SCHEMA_VERSION
from eval.stage2_failure_window_stats import WindowStatisticConfig


CONFIG = WindowStatisticConfig(5, 0.5, 1.0e-12, 1.0e-12)


def _row(frame, timestamp, raw, huber, method="huber_full", valid=True):
    return {
        "schema_version": ONLINE_SCHEMA_VERSION,
        "run_id": "source",
        "sequence_id": "sequence",
        "sweep": "quick",
        "level": "unit",
        "stress": "fixture",
        "geometry_seed": 1,
        "sensor_seed": 2,
        "process_seed": 3,
        "method": method,
        "frame_index": frame,
        "timestamp": timestamp,
        "weak_direction_valid": valid,
        "weak_innovation_valid": valid,
        "primary_direction_stable": valid,
        "degeneracy_triggered": False,
        "actionable_direction": False,
        "odi_trans": 0.1,
        "primary_eigengap_ratio": 0.2,
        "weak_innovation_z_raw": raw,
        "weak_innovation_z_huber": huber,
    }


def _canonical(records):
    return json.dumps(list(records), sort_keys=True, allow_nan=True)


def test_every_prefix_is_unchanged_when_future_rows_are_appended():
    rows = [
        _row(1, 0.1, 1.0, 0.8),
        _row(2, 0.2, 2.0, 1.5),
        _row(3, 0.3, float("nan"), float("nan"), valid=False),
        _row(4, 0.4, -1.0, -0.7),
        _row(5, 0.5, -2.0, -1.2),
    ]
    extended = compute_window_records(rows, CONFIG)
    for prefix_length in range(1, len(rows) + 1):
        prefix = compute_window_records(rows[:prefix_length], CONFIG)
        assert _canonical(prefix) == _canonical(extended[:prefix_length])


def test_duplicate_and_out_of_order_rows_raise_instead_of_being_sorted():
    duplicate = _row(1, 0.1, 1.0, 1.0)
    with pytest.raises(ValueError, match="duplicate"):
        compute_window_records([duplicate, dict(duplicate)], CONFIG)
    with pytest.raises(ValueError, match="frame_index"):
        compute_window_records(
            [_row(2, 0.1, 1.0, 1.0), _row(1, 0.2, 1.0, 1.0)],
            CONFIG,
        )
    with pytest.raises(ValueError, match="timestamp"):
        compute_window_records(
            [_row(1, 0.2, 1.0, 1.0), _row(2, 0.1, 1.0, 1.0)],
            CONFIG,
        )
    with pytest.raises(ValueError, match="frame_index"):
        compute_window_records(
            [_row(1, 0.1, 1.0, 1.0), _row(1, 0.2, 1.0, 1.0)],
            CONFIG,
        )
