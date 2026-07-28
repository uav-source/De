import numpy as np

from zero_perturbation.backend_phase_a_v1_2 import canonical_target


def test_canonical_target_is_one_little_endian_contiguous_float32_array():
    original = np.asarray([[0.1, np.pi, -np.e], [1.0 / 3.0, 7.1, -9.2]])
    target = canonical_target(original)
    assert target.dtype == np.dtype("<f4")
    assert target.flags.c_contiguous
    assert np.array_equal(target, original.astype("<f4"))
