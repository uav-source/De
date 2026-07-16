import pytest

from eval.stage2_failure_day13_statistics import build_geometry_effects


def _rows():
    rows = []
    for seed in range(10):
        for sweep, level in (("geometry", "L3"), ("observation", "O3")):
            base = {"role": "evaluation", "sweep": sweep, "level": level, "geometry_seed": seed, "sensor_seed": 1, "process_seed": 2, "frame_index": 5, "stat_input_valid": True, "window_ready": True}
            rows.append({**base, "stress": "clean", "stress_active": False, "primary_score": 1.0})
            rows.append({**base, "stress": "coherent_subhuber_slip", "stress_active": True, "primary_score": 2.0})
    return rows


def test_all_ten_geometries_and_both_sweeps_are_retained():
    effects = build_geometry_effects(_rows())
    assert len(effects) == 20
    assert all(row["positive_effect"] for row in effects)


def test_dropping_one_geometry_is_rejected():
    with pytest.raises(ValueError):
        build_geometry_effects([row for row in _rows() if row["geometry_seed"] != 9])
