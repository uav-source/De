import numpy as np

from minibench.motion_simulator import simulate_motion_measurements


def test_body_frame_motion_noise_exports_locked_covariance():
    poses = np.zeros((3, 8))
    poses[:, 0] = [0.0, 0.1, 0.2]
    poses[:, 1] = [0.0, 1.0, 2.0]
    poses[:, 7] = 1.0
    config = {
        "translation_noise_frame": "body", "forward_sigma_m": 0.012,
        "lateral_sigma_m": 0.003, "vertical_sigma_m": 0.003,
        "roll_sigma_rad": 0.0004, "pitch_sigma_rad": 0.0004, "yaw_sigma_rad": 0.0008,
    }
    output = simulate_motion_measurements(poses, 3001, config)
    assert np.allclose(np.diag(output["translation_covariance_body"]), [0.012**2, 0.003**2, 0.003**2])
    assert np.allclose(np.diag(output["rotation_covariance_local"]), [0.0004**2, 0.0004**2, 0.0008**2])
