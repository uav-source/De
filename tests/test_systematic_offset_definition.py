import pytest

from zero_perturbation.statistics import aggregate_repeated_measurements


def test_systematic_offset_is_norm_of_mean_vector_not_mean_norm():
    rows = []
    for x in (-1.0, 1.0):
        rows.append(
            {
                "scene_variant": "S",
                "geometry_seed": 1,
                "noise_condition": "C",
                "registration_backend": "native_full",
                "translation_x_m": x,
                "translation_y_m": 0.0,
                "translation_z_m": 0.0,
                "rotation_x_rad": 0.0,
                "rotation_y_rad": 0.0,
                "rotation_z_rad": 0.0,
                "translation_error_m": 1.0,
                "rotation_error_rad": 0.0,
            }
        )
    summary = aggregate_repeated_measurements(rows)[0]
    assert summary["systematic_translation_offset_m"] == pytest.approx(0.0)
    assert summary["systematic_fraction_translation"] == pytest.approx(0.0)
