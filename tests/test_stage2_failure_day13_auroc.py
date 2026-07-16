import pytest

from eval.stage2_failure_day13_statistics import analysis_population_rows, tie_aware_auroc


def test_tie_aware_auroc_known_vectors():
    assert tie_aware_auroc([0, 1, 2, 3], [0, 0, 1, 1]) == 1.0
    assert tie_aware_auroc([0, 1, 2, 3], [1, 0, 1, 0]) == 0.25
    assert tie_aware_auroc([1, 1, 1, 1], [0, 0, 1, 1]) == 0.5


def test_auroc_rejects_missing_class_and_nonfinite():
    with pytest.raises(ValueError):
        tie_aware_auroc([1, 2], [1, 1])
    with pytest.raises(ValueError):
        tie_aware_auroc([1, float("nan")], [0, 1])


def test_open_control_and_gross_rows_never_enter_auroc():
    base = {"role": "evaluation", "level": "L3", "geometry_seed": 1, "sensor_seed": 2, "process_seed": 3, "frame_index": 4, "stat_input_valid": True, "window_ready": True}
    rows = [
        {**base, "sweep": "geometry", "stress": "clean", "stress_active": False, "primary_score": 0.0},
        {**base, "sweep": "geometry", "stress": "coherent_subhuber_slip", "stress_active": True, "primary_score": 1.0},
        {**base, "sweep": "geometry", "stress": "gross_outlier_control", "stress_active": True, "primary_score": 99.0},
        {**base, "sweep": "open_control", "stress": "clean", "stress_active": False, "primary_score": -99.0},
    ]
    selected = analysis_population_rows(rows, "geometry", "huber_cusum_max")
    assert len(selected) == 2
    assert {row["stress"] for row in selected} == {"clean", "coherent_subhuber_slip"}
