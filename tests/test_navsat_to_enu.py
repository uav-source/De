import numpy as np
import pytest

from eval.navsat_reference import (
    ALIGNMENT_METHOD,
    NavSatSample,
    navsat_to_enu,
    rigid_align_positions,
)


def test_first_valid_rtk_fix_is_exact_enu_origin_and_metadata_is_position_only():
    samples = [
        NavSatSample(1.0, 47.0, -52.0, 10.0, status=0),
        NavSatSample(2.0, 47.0, -52.0, 10.0, status=2),
        NavSatSample(3.0, 47.001, -52.0, 10.0, status=2),
    ]
    reference = navsat_to_enu(samples)
    assert reference.origin.timestamp == 2.0
    np.testing.assert_allclose(reference.positions_enu_m[1], np.zeros(3), atol=1e-9)
    assert reference.positions_enu_m[2, 1] == pytest.approx(111.17, rel=0.01)
    assert reference.metadata["reference_is_position_only"] is True
    assert reference.metadata["reference_orientation_available"] is False
    assert reference.metadata["alignment_method"] == ALIGNMENT_METHOD


def test_enu_east_axis_has_correct_longitude_sign():
    reference = navsat_to_enu(
        [
            NavSatSample(1.0, 47.0, -52.0, 0.0, status=2),
            NavSatSample(2.0, 47.0, -51.999, 0.0, status=2),
        ]
    )
    assert reference.positions_enu_m[1, 0] > 70.0
    assert abs(reference.positions_enu_m[1, 1]) < 0.1


def test_rigid_alignment_does_not_estimate_scale():
    estimated = np.asarray([[0, 0, 0], [1, 0, 0], [0, 2, 0], [1, 2, 1]], dtype=float)
    rotation = np.asarray([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
    translation = np.asarray([5.0, -2.0, 3.0])
    reference = estimated @ rotation.T + translation
    aligned, fitted_rotation, fitted_translation = rigid_align_positions(
        estimated, reference
    )
    np.testing.assert_allclose(aligned, reference, atol=1e-12)
    np.testing.assert_allclose(fitted_rotation, rotation, atol=1e-12)
    np.testing.assert_allclose(fitted_translation, translation, atol=1e-12)

