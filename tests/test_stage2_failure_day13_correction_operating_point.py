from eval.stage2_failure_day13_correction_v2 import (
    LOCKED_THRESHOLD,
    build_locked_threshold_operating_points_v2,
)


def _row(sweep, stress, frame, score, active=False):
    return {
        "role": "evaluation", "sweep": sweep,
        "level": "L3" if sweep == "geometry" else "O3", "stress": stress,
        "geometry_seed": 1, "sensor_seed": 2, "process_seed": 3,
        "method": "huber_full", "frame_index": frame, "timestamp": frame / 10,
        "stress_active": active, "stat_input_valid": True, "window_ready": True,
        "primary_score": score,
    }


def test_locked_operating_point_reports_tpr_and_matched_clean_fpr():
    rows = []
    for sweep in ("geometry", "observation"):
        rows.extend((
            _row(sweep, "clean", 1, LOCKED_THRESHOLD + 1),
            _row(sweep, "coherent_subhuber_slip", 1, LOCKED_THRESHOLD + 2, True),
            _row(sweep, "clean", 2, 0),
            _row(sweep, "coherent_subhuber_slip", 2, 0, True),
        ))
    result = build_locked_threshold_operating_points_v2(rows)
    assert len(result) == 2
    assert all(row["true_positive_rate"] == 0.5 for row in result)
    assert all(row["matched_clean_false_positive_rate"] == 0.5 for row in result)
    assert all(row["operator"] == ">" for row in result)

