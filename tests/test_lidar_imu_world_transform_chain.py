import numpy as np
from scipy.spatial.transform import Rotation

from eval.frame_contract import transform_lidar_axis_to_world


def test_lidar_to_imu_then_imu_to_world_chain_uses_forward_extrinsic():
    rotation_imu_from_lidar = Rotation.from_euler("z", 90, degrees=True).as_matrix()
    rotation_world_from_imu = Rotation.from_euler("x", 90, degrees=True).as_matrix()
    actual = transform_lidar_axis_to_world(
        [1.0, 0.0, 0.0], rotation_imu_from_lidar, rotation_world_from_imu
    )
    expected = rotation_world_from_imu @ rotation_imu_from_lidar @ np.asarray([1.0, 0.0, 0.0])
    np.testing.assert_allclose(actual, expected, atol=1e-12)
