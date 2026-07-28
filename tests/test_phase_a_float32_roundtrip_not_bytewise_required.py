import numpy as np

from backend_phase_a_v1_2_test_support import target_points, transform
from zero_perturbation.backend_phase_a_v1_2 import source_from_parent_indices


def test_general_float32_se3_roundtrip_need_not_be_bytewise_equal():
    target = target_points()
    pose = transform()
    indices = np.arange(len(target), dtype="<i8")
    source, _, parents = source_from_parent_indices(target, indices, pose)
    roundtrip = ((pose[:3, :3] @ source.astype(float).T).T + pose[:3, 3]).astype("<f4")
    assert np.count_nonzero(roundtrip.view(np.uint32) != parents.astype("<f4").view(np.uint32)) > 0
