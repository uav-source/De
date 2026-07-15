import math

import numpy as np

from eval.stage2_failure_logging import compute_directional_score


def test_directional_score_matches_day8_contract_and_changes_sign():
    H = np.diag([1.0, 1.0, 1.0, 4.0, 9.0, 16.0])
    b = np.array([0.0, 0.0, 0.0, -2.0, 0.0, 0.0])

    positive = compute_directional_score(H, b, np.array([1.0, 0.0, 0.0]))
    negative = compute_directional_score(H, b, np.array([-1.0, 0.0, 0.0]))

    assert positive.information == 4.0
    assert positive.gradient == 2.0
    assert positive.z == 1.0
    assert positive.valid
    assert negative.information == 4.0
    assert negative.gradient == -2.0
    assert negative.z == -1.0


def test_directional_score_does_not_divide_by_epsilon():
    score = compute_directional_score(
        np.zeros((6, 6)),
        np.ones(6),
        np.array([1.0, 0.0, 0.0]),
    )
    assert not score.valid
    assert score.information == 0.0
    assert math.isnan(score.z)
