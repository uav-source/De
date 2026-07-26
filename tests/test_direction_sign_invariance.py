import numpy as np
import pytest

from eval.frame_contract import sign_invariant_angle_deg


def test_direction_angle_is_invariant_to_both_axis_signs():
    weak = np.asarray([0.2, 0.8, -0.3])
    reference = np.asarray([0.1, 0.9, 0.4])
    expected = sign_invariant_angle_deg(weak, reference)
    assert sign_invariant_angle_deg(-weak, reference) == pytest.approx(expected)
    assert sign_invariant_angle_deg(weak, -reference) == pytest.approx(expected)
    assert sign_invariant_angle_deg(-weak, -reference) == pytest.approx(expected)
