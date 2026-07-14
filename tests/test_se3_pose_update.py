from pathlib import Path

import numpy as np

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from minibench.motion_simulator import apply_se3_increment, compose_pose_with_body_increment  # noqa: E402
from minibench.observation_simulator import quat_to_rot  # noqa: E402


def identity_pose():
    return np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])


def test_roll_pitch_yaw_and_translation_all_apply():
    for index in range(3):
        delta = np.zeros(6)
        delta[index] = 0.1
        updated = apply_se3_increment(identity_pose(), delta)
        assert not np.allclose(quat_to_rot(updated[4:8]), np.eye(3))
        assert np.isclose(np.linalg.norm(updated[4:8]), 1.0)
    delta = np.array([0.1, -0.2, 0.3, 1.0, 2.0, 3.0])
    updated = apply_se3_increment(identity_pose(), delta)
    assert np.allclose(updated[1:4], [1.0, 2.0, 3.0])
    assert np.isclose(np.linalg.norm(updated[4:8]), 1.0)


def test_body_increment_uses_current_orientation():
    pose = apply_se3_increment(identity_pose(), np.array([0.0, 0.0, np.pi / 2, 0.0, 0.0, 0.0]))
    updated = compose_pose_with_body_increment(pose, np.array([1.0, 0.0, 0.0]), np.zeros(3))
    assert np.allclose(updated[1:4], [0.0, 1.0, 0.0], atol=1.0e-7)

