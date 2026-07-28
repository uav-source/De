import pytest

from zero_perturbation.statistics import aggregate_repeated_measurements


def test_development_statistics_aggregate_measurement_and_repeat_rows():
    rows = []
    for measurement in (1, 2):
        for repeat in range(5):
            value = float(measurement + repeat)
            rows.append(
                {
                    "scene_variant": "S", "geometry_seed": 1, "measurement_seed": measurement,
                    "repeat_index": repeat, "noise_condition": "C", "registration_backend": "B",
                    "translation_x_m": value, "translation_y_m": 0.0, "translation_z_m": 0.0,
                    "rotation_x_rad": 0.0, "rotation_y_rad": 0.0, "rotation_z_rad": 0.0,
                    "translation_error_m": value, "rotation_error_rad": 0.0,
                }
            )
    result = aggregate_repeated_measurements(rows)[0]
    assert result["trial_count"] == 10
    assert result["systematic_translation_offset_m"] == pytest.approx(3.5)
    assert result["translation_error_median_m"] == pytest.approx(3.5)
