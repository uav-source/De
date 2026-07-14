from eval.weak_update_stage2c import select_attenuation_alpha
from stage2c_helpers import selection_trials


def test_alpha_requires_positive_geometry_and_observation_sweeps():
    common = {"attenuation_alpha_candidates": [0.25, 0.5]}
    base, candidates = selection_trials(
        {0.25: 0.20, 0.5: 0.10},
        {0.25: -0.01, 0.5: 0.04},
    )
    table, selected = select_attenuation_alpha(base, candidates, common)
    assert selected == 0.5
    assert table[0]["feasible"] is False
    assert table[0]["observation_severe_axis_reduction"] < 0.0
