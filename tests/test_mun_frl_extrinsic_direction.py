import numpy as np

from fastlio2_adapter.mun_frl_contract import (
    R_IMU_LIDAR,
    T_IMU_LIDAR,
    transform_lidar_points_to_imu,
)


def test_mun_frl_extrinsic_maps_lidar_points_into_imu_frame():
    lidar_point = np.asarray([1.5, -0.2, 3.0])
    expected_imu_point = R_IMU_LIDAR @ lidar_point + T_IMU_LIDAR
    actual = transform_lidar_points_to_imu(lidar_point)
    np.testing.assert_allclose(actual, expected_imu_point, rtol=0.0, atol=1e-15)


def test_mun_frl_extrinsic_is_not_inverted():
    lidar_origin_in_imu = transform_lidar_points_to_imu(np.zeros(3))
    np.testing.assert_array_equal(lidar_origin_in_imu, T_IMU_LIDAR)
    assert not np.allclose(lidar_origin_in_imu, -R_IMU_LIDAR.T @ T_IMU_LIDAR)

