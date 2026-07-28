import numpy as np

from backend_phase_a_v1_2_test_support import target_points, transform
from zero_perturbation.backend_phase_a_v1_2 import source_from_parent_indices


def test_parent_points_are_exact_index_reads_from_canonical_target():
    target = target_points()
    indices = np.ascontiguousarray([1, 4, 9, 16, 25], dtype="<i8")
    _, _, parents = source_from_parent_indices(target, indices, transform())
    assert np.array_equal(parents, target[indices].astype(np.float64))
