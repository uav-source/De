import pytest

from eval.stage2_failure_day13_correction_v2 import (
    build_matched_analysis_population,
)


def _row(stress, score, active=False):
    return {
        "role": "evaluation", "sweep": "geometry", "level": "L3",
        "stress": stress, "geometry_seed": 1, "sensor_seed": 2,
        "process_seed": 3, "method": "huber_full", "frame_index": 7,
        "timestamp": 0.7, "stress_active": active, "stat_input_valid": True,
        "window_ready": True, "primary_score": score,
    }


def test_duplicate_clean_key_is_rejected():
    rows = [
        _row("clean", 1), _row("clean", 2),
        _row("coherent_subhuber_slip", 3, active=True),
    ]
    with pytest.raises(ValueError, match="duplicate clean"):
        build_matched_analysis_population(rows, "geometry", "huber_cusum_max")


def test_duplicate_positive_key_is_rejected():
    rows = [
        _row("clean", 1),
        _row("coherent_subhuber_slip", 2, active=True),
        _row("coherent_subhuber_slip", 3, active=True),
    ]
    with pytest.raises(ValueError, match="duplicate coherent"):
        build_matched_analysis_population(rows, "geometry", "huber_cusum_max")

