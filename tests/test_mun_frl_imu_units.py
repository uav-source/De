import numpy as np

from fastlio2_adapter.mun_frl_contract import convert_imu_units


def test_mun_frl_imu_unit_conversion_is_identity():
    angular_source = [0.1, -0.2, 0.3]
    acceleration_source = [1.2, -2.3, 9.7]
    angular, acceleration = convert_imu_units(
        angular_source, acceleration_source
    )
    np.testing.assert_array_equal(angular, angular_source)
    np.testing.assert_array_equal(acceleration, acceleration_source)

