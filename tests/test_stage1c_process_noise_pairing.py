from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minibench.motion_simulator import process_noise_checksum, simulate_motion_measurements  # noqa: E402


def test_stage1c_same_pairing_unit_is_identical_across_levels():
    poses = np.column_stack([np.arange(5) * 0.1, np.arange(5), np.zeros((5, 2)), np.zeros((5, 3)), np.ones(5)])
    config = {"axis_sigma": 0.01, "cross_sigma": 0.003, "yaw_sigma": 0.001}
    checksums = []
    for _level in ["L1", "L2", "L3", "L4"]:
        motion = simulate_motion_measurements(
            poses, 2001, config, motion_profile_id="m1", experiment_family="stage1c_geometry", geometry_seed=606, sensor_seed=33
        )
        checksums.append(process_noise_checksum(motion))
    assert len(set(checksums)) == 1
