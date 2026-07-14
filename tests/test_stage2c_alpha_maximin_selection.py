from eval.weak_update_stage2c import select_attenuation_alpha
from stage2c_helpers import selection_trials


def test_alpha_maximizes_worst_sweep_and_uses_largest_alpha_within_one_point():
    common = {"attenuation_alpha_candidates": [0.25, 0.5, 0.75]}
    base, candidates = selection_trials(
        {0.25: 0.20, 0.5: 0.19, 0.75: 0.14},
        {0.25: 0.18, 0.5: 0.175, 0.75: 0.14},
    )
    table, selected = select_attenuation_alpha(base, candidates, common)
    assert selected == 0.5
    assert [row["attenuation_alpha"] for row in table if row["selected"]] == [0.5]
