import numpy as np

from eval.navsat_reference import EnuReference, NavSatSample, interpolate_reference


def test_reference_is_interpolated_at_fast_lio_header_times():
    origin = NavSatSample(1.0e9, 0.0, 0.0, 0.0, status=2)
    reference = EnuReference(
        timestamps=np.asarray([1.0e9, 1.0e9 + 2.0]),
        positions_enu_m=np.asarray([[0.0, 0.0, 0.0], [2.0, 4.0, 6.0]]),
        rtk_quality=np.asarray([True, True]),
        covariance_diagonal_m2=np.zeros((2, 3)),
        origin=origin,
    )
    positions, quality = interpolate_reference(reference, np.asarray([1.0e9 + 1.0]))
    np.testing.assert_allclose(positions[0], [1.0, 2.0, 3.0])
    assert quality[0]
