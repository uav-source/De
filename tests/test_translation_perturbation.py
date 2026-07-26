import numpy as np
import pytest

from capture_range.perturbation import apply_perturbation, apply_translation_perturbation
from capture_range.types import PerturbationSpec, RegistrationSnapshot
from minibench.motion_simulator import rotvec_to_quat


def native_pose() -> np.ndarray:
    return np.array([7.0, 1.0, 2.0, 3.0, *rotvec_to_quat([0.0, 0.0, np.pi / 2])])


def test_translation_boxplus_is_world_additive_and_preserves_rotation():
    pose = native_pose()
    updated = apply_translation_perturbation(pose, [1.0, 0.0, 0.0], 0.2)
    assert np.allclose(updated[1:4], [1.2, 2.0, 3.0])
    assert np.allclose(updated[4:8], pose[4:8])
    assert updated[0] == pose[0]


def test_translation_boxplus_supports_homogeneous_pose_and_negative_side():
    pose = np.eye(4)
    pose[:3, 3] = [1.0, 2.0, 3.0]
    updated = apply_translation_perturbation(pose, [0.0, 1.0, 0.0], -0.05)
    assert np.allclose(updated[:3, 3], [1.0, 1.95, 3.0])
    assert np.allclose(updated[:3, :3], np.eye(3))
    assert np.allclose(pose[:3, 3], [1.0, 2.0, 3.0])


def test_perturbation_spec_canonicalizes_direction_and_applies_sign_once():
    spec = PerturbationSpec(
        perturbation_type="translation",
        direction=np.array([-1.0, 0.0, 0.0]),
        signed_amplitude=-0.1,
        repeat_index=0,
        seed=4,
        direction_id="translation_x_negative",
        signed_side=-1,
    )
    assert np.array_equal(spec.direction, [1.0, 0.0, 0.0])
    updated = apply_perturbation(native_pose(), spec)
    assert updated[1] == pytest.approx(0.9)


def test_snapshot_arrays_are_defensive_copies_and_read_only():
    scan = np.array([[1.0, 2.0, 3.0]])
    local_map = np.array([[3.0, 2.0, 1.0]])
    pose = np.eye(4)
    snapshot = RegistrationSnapshot("s", scan, local_map, pose, {}, {})
    scan[0, 0] = 99.0
    pose[0, 3] = 99.0
    assert snapshot.scan_points[0, 0] == 1.0
    assert snapshot.reference_pose[0, 3] == 0.0
    with pytest.raises(ValueError):
        snapshot.scan_points[0, 0] = 2.0


def test_snapshot_configuration_and_metadata_are_recursively_immutable():
    snapshot = RegistrationSnapshot(
        "s",
        [[1.0, 2.0, 3.0]],
        [[3.0, 2.0, 1.0]],
        np.eye(4),
        {"registration": {"max_iterations": 20}, "levels": [1, 2]},
        {"scene_name": "box", "labels": ["smoke"]},
    )
    with pytest.raises(TypeError, match="frozen mapping"):
        snapshot.registration_config["registration"]["max_iterations"] = 99
    with pytest.raises(TypeError, match="frozen mapping"):
        snapshot.metadata["scene_name"] = "changed"
    assert snapshot.registration_config["levels"] == (1, 2)
    assert snapshot.metadata["labels"] == ("smoke",)
