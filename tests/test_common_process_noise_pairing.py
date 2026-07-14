from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minibench.motion_simulator import process_noise_checksum, simulate_motion_measurements  # noqa: E402


def test_same_process_seed_across_levels_has_identical_noise_checksum():
    poses = np.column_stack(
        [
            np.arange(6) * 0.1,
            np.arange(6),
            np.zeros(6),
            np.zeros(6),
            np.zeros((6, 3)),
            np.ones(6),
        ]
    )
    config = {"axis_sigma": 0.01, "cross_sigma": 0.003, "yaw_sigma": 0.001}
    checksums = [
        process_noise_checksum(simulate_motion_measurements(poses, 1001, config, motion_profile_id="stage1b_m1"))
        for _level in ["L1", "L2", "L3", "L4", "O1", "O4"]
    ]
    assert len(set(checksums)) == 1
