from __future__ import annotations

import numpy as np


def simple_pose(x: float = 0.0) -> np.ndarray:
    return np.array([0.0, x, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], dtype=float)


def simple_observations(frames: int = 4, points: int = 12):
    normals_one = np.asarray(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]] * (points // 3),
        dtype=float,
    )
    points_one = np.linspace(-1.0, 1.0, points * 3).reshape(points, 3)
    return {
        "timestamps": np.arange(frames, dtype=float) * 0.1,
        "points_lidar": np.tile(points_one, (frames, 1, 1)),
        "normals_world": np.tile(normals_one, (frames, 1, 1)),
        "plane_points_world": np.tile(points_one, (frames, 1, 1)),
        "r_list": np.zeros((frames, points)),
        "R_diag_list": np.full((frames, points), 0.0004),
        "is_axial_support": np.tile(normals_one[:, 0] != 0.0, (frames, 1)),
    }


def simple_motion(frames: int = 4):
    return {
        "initial_pose": simple_pose(),
        "delta_translation_body": np.zeros((frames - 1, 3)),
        "delta_rotation_vector": np.zeros((frames - 1, 3)),
        "translation_covariance_body": np.diag([1.44e-4, 9e-6, 9e-6]),
        "rotation_covariance_local": np.diag([1.6e-7, 1.6e-7, 6.4e-7]),
    }


def detector_config():
    return {
        "s_theta": 0.05,
        "s_p": 0.5,
        "epsilon_mode": "relative_trace",
        "epsilon_ratio": 1.0e-6,
        "translation_schur_damping_ratio": 1.0e-6,
        "tau_w": 0.02,
        "primary_direction_min_eigengap_ratio": 0.02,
    }


def update_config():
    return {
        "lidar_update_iterations": 1,
        "initial_covariance_diag": [1.0e-6] * 6,
        "huber_delta_sigma": 2.5,
    }


def stress_config():
    return {
        "stress_regimes": {
            "clean": {"enabled": False},
            "axial_correspondence_slip": {
                "enabled": True,
                "corrupted_axial_patch_fraction": 0.25,
                "burst_length_frames": 8,
                "slip_distance_m": 0.08,
            },
        }
    }
