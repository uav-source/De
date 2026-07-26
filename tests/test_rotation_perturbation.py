import numpy as np

from capture_range.perturbation import apply_rotation_perturbation
from minibench.motion_simulator import quat_multiply, rotvec_to_quat
from minibench.observation_simulator import quat_to_rot


def native_pose(rotation_vector=(0.0, 0.0, 0.0)) -> np.ndarray:
    return np.array([2.0, 1.0, -2.0, 3.0, *rotvec_to_quat(rotation_vector)])


def test_rotation_boxplus_is_right_multiplicative_for_native_pose():
    pose = native_pose((0.0, 0.0, np.pi / 2))
    angle = 0.2
    updated = apply_rotation_perturbation(pose, [1.0, 0.0, 0.0], angle)
    expected = quat_multiply(pose[4:8], rotvec_to_quat([angle, 0.0, 0.0]))
    assert np.allclose(updated[4:8], expected)
    assert np.allclose(updated[1:4], pose[1:4])


def test_rotation_boxplus_is_right_multiplicative_for_matrix_pose():
    pose = np.eye(4)
    pose[:3, :3] = quat_to_rot(rotvec_to_quat([0.0, 0.0, np.pi / 2]))
    updated = apply_rotation_perturbation(pose, [1.0, 0.0, 0.0], 0.2)
    expected = pose[:3, :3] @ quat_to_rot(rotvec_to_quat([0.2, 0.0, 0.0]))
    assert np.allclose(updated[:3, :3], expected)
    assert np.allclose(updated[:3, 3], pose[:3, 3])


def test_negative_rotation_amplitude_is_not_made_absolute():
    positive = apply_rotation_perturbation(native_pose(), [0.0, 1.0, 0.0], 0.1)
    negative = apply_rotation_perturbation(native_pose(), [0.0, 1.0, 0.0], -0.1)
    assert positive[5] == -negative[5]
    assert positive[7] == negative[7]
