import numpy as np

from zero_perturbation.backend_phase_a_metrics import (
    canonical_backend_inputs,
    source_is_exact_target_subset,
)


def test_shared_input_boundary_is_little_endian_float32_c_contiguous():
    target = np.arange(36, dtype=np.float64).reshape(12, 3) / 7.0
    source = target[[0, 2, 5, 9]]
    bundle = canonical_backend_inputs(source, target, np.eye(4))
    assert bundle["source_points"].dtype.str == "<f4"
    assert bundle["target_points"].dtype.str == "<f4"
    assert bundle["source_points"].flags.c_contiguous
    assert bundle["target_points"].flags.c_contiguous
    assert source_is_exact_target_subset(source, target) is True
    assert np.array_equal(
        bundle["source_points"].astype(np.float64),
        bundle["source_points"].astype(np.float64),
    )
