import numpy as np

from backend_phase_a_v1_2_test_support import target_points, transform
from zero_perturbation.backend_phase_a_v1_2 import source_from_parent_indices


def test_source_float64_is_inverse_reference_transform_of_parent():
    target = target_points()
    pose = transform()
    indices = np.arange(len(target), dtype="<i8")
    _, source_f64, parents = source_from_parent_indices(target, indices, pose)
    reconstructed = (pose[:3, :3] @ source_f64.T).T + pose[:3, 3]
    assert np.allclose(reconstructed, parents, rtol=0.0, atol=3e-15)
