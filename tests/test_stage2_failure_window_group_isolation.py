import json

from eval.stage2_failure_day9 import compute_window_records
from eval.stage2_failure_schema import ONLINE_SCHEMA_VERSION
from eval.stage2_failure_window_schema import window_frame_key
from eval.stage2_failure_window_stats import WindowStatisticConfig


CONFIG = WindowStatisticConfig(5, 0.5, 1.0e-12, 1.0e-12)


def _row(frame, method, raw, huber):
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
        "timestamp": frame * 0.1,
        "weak_direction_valid": True,
        "weak_innovation_valid": True,
        "primary_direction_stable": True,
        "degeneracy_triggered": False,
        "actionable_direction": False,
        "odi_trans": 0.1,
        "primary_eigengap_ratio": 0.2,
        "weak_innovation_z_raw": raw,
        "weak_innovation_z_huber": huber,
    }


def _canonical(record):
    return json.dumps(record, sort_keys=True, allow_nan=True)


def test_interleaved_methods_match_independent_processing():
    full = [_row(i, "huber_full", float(i), float(i) * 0.8) for i in range(1, 4)]
    projected = [
        _row(i, "huber_projected_gain", -float(i), -float(i) * 0.8)
        for i in range(1, 4)
    ]
    interleaved = [item for pair in zip(full, projected) for item in pair]
    combined = compute_window_records(interleaved, CONFIG)
    indexed = {window_frame_key(row): row for row in combined}
    for isolated_rows in [full, projected]:
        for record in compute_window_records(isolated_rows, CONFIG):
            assert _canonical(record) == _canonical(indexed[window_frame_key(record)])


def test_raw_and_huber_cusum_and_run_states_are_independent():
    rows = [_row(i, "huber_full", 1.0, -1.0) for i in range(1, 4)]
    result = compute_window_records(rows, CONFIG)[-1]
    assert result["raw_current_sign"] == 1
    assert result["raw_current_same_sign_run_length"] == 3
    assert result["raw_cusum_positive"] == 1.5
    assert result["raw_cusum_negative"] == 0.0
    assert result["huber_current_sign"] == -1
    assert result["huber_current_same_sign_run_length"] == 3
    assert result["huber_cusum_positive"] == 0.0
    assert result["huber_cusum_negative"] == 1.5
