import numpy as np
import pytest

from eval.navsat_reference import weak_direction_angle_error_deg


def test_weak_direction_reference_error_is_invariant_to_eigenvector_sign():
    reference = np.asarray([0.2, 0.9, 0.4])
    weak = np.asarray([0.1, 0.8, 0.55])
    positive = weak_direction_angle_error_deg(weak, reference)
    negative = weak_direction_angle_error_deg(-weak, reference)
    assert positive == pytest.approx(negative, abs=1e-14)


def test_parallel_and_antiparallel_axes_both_have_zero_error():
    reference = np.asarray([1.0, 2.0, 3.0])
    assert weak_direction_angle_error_deg(reference, reference) == pytest.approx(0.0)
    assert weak_direction_angle_error_deg(-reference, reference) == pytest.approx(0.0)

