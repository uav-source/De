from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minibench.motion_simulator import process_noise_checksum, simulate_motion_measurements  # noqa: E402


def test_stage1c_noise_is_independent_across_geometry_sensor_and_family():
    poses = np.column_stack(
        [np.arange(5) * 0.1, np.arange(5), np.zeros((5, 2)), np.zeros((5, 3)), np.ones(5)]
    )
    config = {"axis_sigma": 0.01, "cross_sigma": 0.003, "yaw_sigma": 0.001}
    contexts = [
        ("stage1c_geometry", 606, 33),
        ("stage1c_geometry", 707, 33),
        ("stage1c_geometry", 606, 44),
        ("stage1c_observation", 606, 33),
    ]
    checksums = {
        process_noise_checksum(
            simulate_motion_measurements(
                poses,
                2001,
                config,
                motion_profile_id="m1",
                experiment_family=family,
                geometry_seed=geometry,
                sensor_seed=sensor,
            )
        )
        for family, geometry, sensor in contexts
    }
    assert len(checksums) == 4
