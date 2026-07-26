import pytest

from fastlio2_adapter.day6_eigenspace_stability import (
    sign_invariant_angle_deg,
)


def test_vector_and_negative_vector_have_zero_angle():
    assert sign_invariant_angle_deg([1, 0, 0], [-1, 0, 0]) == 0.0


def test_orthogonal_directions_have_ninety_degree_angle():
    assert sign_invariant_angle_deg([1, 0, 0], [0, 1, 0]) == pytest.approx(
        90.0
    )
