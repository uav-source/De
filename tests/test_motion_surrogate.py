from pathlib import Path

import numpy as np

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minibench.motion_simulator import simulate_motion_measurements  # noqa: E402


def poses():
    timestamps = np.arange(6, dtype=float) * 0.1
    positions = np.column_stack([np.arange(6, dtype=float), np.zeros(6), np.zeros(6)])
    quaternions = np.tile(np.array([0.0, 0.0, 0.0, 1.0]), (6, 1))
    return np.column_stack([timestamps, positions, quaternions])


def test_process_seed_only_changes_motion_measurement_noise():
    config = {"axis_sigma": 0.01, "cross_sigma": 0.003, "yaw_sigma": 0.001}
    first = simulate_motion_measurements(poses(), 1001, config)
    same = simulate_motion_measurements(poses(), 1001, config)
    different = simulate_motion_measurements(poses(), 1002, config)
    assert np.array_equal(first["delta_translation_body"], same["delta_translation_body"])
    assert np.array_equal(first["delta_rotation_vector"], same["delta_rotation_vector"])
    assert not np.array_equal(first["delta_translation_body"], different["delta_translation_body"])
    assert np.array_equal(first["timestamps"], different["timestamps"])

