import math

import pytest

from eval.stage2_failure_day9 import compute_window_records
from eval.stage2_failure_schema import ONLINE_SCHEMA_VERSION
from eval.stage2_failure_window_schema import (
    WINDOW_FIELDS,
    WINDOW_SCHEMA_VERSION,
    validate_window_record,
)
from eval.stage2_failure_window_stats import WindowStatisticConfig


CONFIG = WindowStatisticConfig(5, 0.5, 1.0e-12, 1.0e-12)


def _row(frame=1, valid=True):
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
        "method": "huber_full",
        "frame_index": frame,
        "timestamp": frame * 0.1,
        "weak_direction_valid": valid,
        "weak_innovation_valid": valid,
        "primary_direction_stable": valid,
        "degeneracy_triggered": False,
        "actionable_direction": False,
        "odi_trans": 0.1,
        "primary_eigengap_ratio": 0.2,
        "weak_innovation_z_raw": 1.0 if valid else float("nan"),
        "weak_innovation_z_huber": 0.8 if valid else float("nan"),
    }


def test_window_schema_is_exact_and_validates_partial_row():
    record = compute_window_records([_row()], CONFIG)[0]
    assert list(record) == WINDOW_FIELDS
    assert record["schema_version"] == WINDOW_SCHEMA_VERSION
    validate_window_record(record)
    extra = dict(record)
    extra["scene_label"] = "forbidden"
    with pytest.raises(ValueError):
        validate_window_record(extra)


def test_invalid_frame_exposes_only_reset_state_and_nan_float_statistics():
    records = compute_window_records([_row(1), _row(2, valid=False)], CONFIG)
    invalid = records[-1]
    assert invalid["stat_input_valid"] is False
    assert invalid["stat_reset_reason"] == "invalid_direction"
    assert invalid["window_count"] == 0
    assert invalid["consecutive_valid_count"] == 0
    assert not invalid["window_ready"]
    assert math.isnan(invalid["raw_window_mean"])
    assert math.isnan(invalid["huber_cusum_positive"])
    validate_window_record(invalid)

    fake_zero = dict(invalid)
    fake_zero["raw_window_mean"] = 0.0
    with pytest.raises(ValueError, match="NaN"):
        validate_window_record(fake_zero)


def test_schema_rejects_infinite_statistics():
    record = dict(compute_window_records([_row()], CONFIG)[0])
    record["raw_window_energy"] = float("inf")
    with pytest.raises(ValueError, match="infinite"):
        validate_window_record(record)
