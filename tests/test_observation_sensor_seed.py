from pathlib import Path

import numpy as np
import yaml

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minibench.observation_simulator import simulate_sequence_observations  # noqa: E402
from minibench.scene_generator import generate_straight_tunnel, load_scene_config, save_sequence  # noqa: E402


def make_sequence(tmp_path):
    config = {
        "sequence_id": "ST-L2-G01",
        "scene_family": "ST",
        "difficulty": "L2",
        "seed_id": "G01",
        "motion_id": "M1",
        "random_seed": 101,
        "geometry_seed": 101,
        "axis": [1, 0, 0],
        "tunnel_length_m": 8.0,
        "width_m": 4.0,
        "height_m": 3.0,
        "frames": 8,
        "dt_s": 0.1,
        "axial_support_fraction": 0.10,
        "axial_patch_count": 4,
        "expected_degeneracy": "test",
        "scientific_role": "test",
    }
    config_path = tmp_path / "scene.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    save_sequence(generate_straight_tunnel(load_scene_config(config_path)), tmp_path)
    detector = {
        "points_per_frame": 64,
        "point_noise_std_m": 0.02,
        "sensor": {"max_range_m": 30.0, "dropout_probability": 0.02},
    }
    detector_path = tmp_path / "detector.yaml"
    detector_path.write_text(yaml.safe_dump(detector), encoding="utf-8")
    return detector_path


def test_sensor_seed_reproducibility_and_independence(tmp_path):
    detector = make_sequence(tmp_path)
    first = simulate_sequence_observations(tmp_path, detector, sensor_seed=11)
    same = simulate_sequence_observations(tmp_path, detector, sensor_seed=11)
    different = simulate_sequence_observations(tmp_path, detector, sensor_seed=22)
    assert np.array_equal(first["points_lidar"], same["points_lidar"])
    assert np.array_equal(first["r_list"], same["r_list"])
    assert not np.array_equal(first["points_lidar"], different["points_lidar"])
    assert not np.array_equal(first["r_list"], different["r_list"])

