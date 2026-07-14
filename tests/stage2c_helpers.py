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
            "coherent_subhuber_slip": {
                "enabled": True,
                "corrupted_axial_patch_fraction": 1.0,
                "burst_length_frames": 20,
                "slip_sigma": 1.5,
                "shared_burst_start": True,
                "shared_sign": True,
            },
            "gross_outlier_control": {
                "enabled": True,
                "corrupted_axial_patch_fraction": 0.25,
                "burst_length_frames": 8,
                "slip_sigma": 4.0,
                "shared_burst_start": True,
                "shared_sign": True,
            },
        }
    }


def patch_ids(observations):
    axial = observations["is_axial_support"]
    axial_ids = np.asarray([f"axial_{index % 4}" for index in range(axial.shape[1])])[None, :]
    shell_ids = np.asarray([f"shell_{index % 4}" for index in range(axial.shape[1])])[None, :]
    return np.where(axial, axial_ids, shell_ids)


def random_system(seed: int = 7, measurements: int = 18):
    from minibench.update_strategies import build_robust_linear_system

    rng = np.random.default_rng(seed)
    J = rng.normal(size=(measurements, 6))
    residual = rng.normal(scale=0.02, size=measurements)
    variance = np.full(measurements, 0.0004)
    return build_robust_linear_system(J, residual, variance, 2.5)


def selection_trials(geometry_reductions, observation_reductions):
    def row(sweep, level, stress, method, axis=1.0, geometry_seed=2801):
        return {
            "sweep": sweep,
            "level": level,
            "stress": stress,
            "geometry_seed": geometry_seed,
            "sensor_seed": 77,
            "process_seed": 4001,
            "method": method,
            "axis_rmse": axis,
            "strong_translation_rmse": 1.0,
            "orientation_rmse_rad": 1.0,
            "trajectory_rmse_3d": 1.0,
            "solver_failure": 0,
        }

    base = [
        row("open_control", "OC", "clean", "huber_full"),
        row("geometry", "L3", "coherent_subhuber_slip", "huber_full"),
        row("observation", "O3", "coherent_subhuber_slip", "huber_full"),
    ]
    candidates = []
    for alpha, geometry_reduction in geometry_reductions.items():
        observation_reduction = observation_reductions[alpha]
        values = [
            row("open_control", "OC", "clean", "huber_projected_gain"),
            row(
                "geometry", "L3", "coherent_subhuber_slip", "huber_projected_gain",
                1.0 - geometry_reduction,
            ),
            row(
                "observation", "O3", "coherent_subhuber_slip", "huber_projected_gain",
                1.0 - observation_reduction,
            ),
        ]
        for value in values:
            value["candidate_alpha"] = alpha
        candidates.extend(values)
    return base, candidates
