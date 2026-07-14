import numpy as np

from minibench.motion_simulator import process_noise_checksum, simulate_motion_measurements
from stage2c_helpers import simple_pose


def test_process_noise_is_reproducible_and_method_independent():
    poses = np.tile(simple_pose(), (5, 1))
    poses[:, 0] = np.arange(5) * 0.1
    poses[:, 1] = np.arange(5) * 0.05
    config = {
        "translation_noise_frame": "body",
        "forward_sigma_m": 0.012,
        "lateral_sigma_m": 0.003,
        "vertical_sigma_m": 0.003,
        "rotation_sigma_rad": [0.0004, 0.0004, 0.0008],
    }
    first = simulate_motion_measurements(
        poses, 4001, config, experiment_family="weak_update_stage2c",
        geometry_seed=2801, sensor_seed=77,
    )
    second = simulate_motion_measurements(
        poses, 4001, config, experiment_family="weak_update_stage2c",
        geometry_seed=2801, sensor_seed=77,
    )
    assert process_noise_checksum(first) == process_noise_checksum(second)
    assert np.array_equal(first["delta_translation_body"], second["delta_translation_body"])
    assert np.array_equal(first["delta_rotation_vector"], second["delta_rotation_vector"])
