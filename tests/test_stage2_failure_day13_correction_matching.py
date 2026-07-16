import math

import pytest

from eval.stage2_failure_day13_correction_v2 import (
    build_matched_analysis_population,
)


def _row(stress, frame, score, *, active=False, sweep="geometry", timestamp=None):
    return {
        "role": "evaluation", "case_id": f"{stress}-{frame}", "sweep": sweep,
        "level": "L3" if sweep == "geometry" else "O3", "stress": stress,
        "geometry_seed": 1, "sensor_seed": 2, "process_seed": 3,
        "method": "huber_full", "frame_index": frame,
        "timestamp": frame / 10 if timestamp is None else timestamp,
        "stress_active": active, "stat_input_valid": True, "window_ready": True,
        "primary_score": score, "abs_huber_window_mean": abs(score),
    }


def test_one_to_one_matching_excludes_surplus_clean_and_controls():
    rows = [_row("clean", frame, frame) for frame in range(1, 5)]
    rows += [
        _row("coherent_subhuber_slip", 1, 10, active=True),
        _row("coherent_subhuber_slip", 2, 20, active=True),
        _row("coherent_subhuber_slip", 3, 30, active=False),
        _row("gross_outlier_control", 1, 100, active=True),
        _row("clean", 1, 100, sweep="open_control"),
    ]
    result = build_matched_analysis_population(rows, "geometry", "huber_cusum_max")
    audit = result["audit"]
    assert audit["matched_pair_count"] == 2
    assert audit["positive_frame_count"] == 2
    assert audit["negative_frame_count"] == 2
    assert audit["excluded_unmatched_clean_count"] == 2
    assert len({row["pair_id"] for row in result["rows"]}) == 2
    assert {row["analysis_pair_role"] for row in result["rows"]} == {
        "coherent_positive", "matched_clean_negative",
    }


def test_missing_match_and_timestamp_disagreement_are_errors():
    with pytest.raises(ValueError, match="no matched clean"):
        build_matched_analysis_population(
            [_row("coherent_subhuber_slip", 1, 2, active=True)],
            "geometry", "huber_cusum_max",
        )
    with pytest.raises(ValueError, match="timestamps differ"):
        build_matched_analysis_population(
            [
                _row("clean", 1, 1, timestamp=0.2),
                _row("coherent_subhuber_slip", 1, 2, active=True, timestamp=0.1),
            ],
            "geometry", "huber_cusum_max",
        )


def test_nonfinite_secondary_invalidates_both_sides_of_pair():
    rows = [
        _row("clean", 1, 1),
        _row("coherent_subhuber_slip", 1, 2, active=True),
        _row("clean", 2, 3),
        _row("coherent_subhuber_slip", 2, 4, active=True),
    ]
    rows[0]["abs_huber_window_mean"] = math.nan
    result = build_matched_analysis_population(
        rows, "geometry", "abs_huber_window_mean"
    )
    assert result["audit"]["invalid_pair_count"] == 1
    assert result["audit"]["matched_pair_count"] == 1
    assert len(result["rows"]) == 2

