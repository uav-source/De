from eval.weak_update_stage2c import select_attenuation_alpha
from stage2c_helpers import selection_trials


def test_all_negative_alpha_candidates_are_a_development_no_go():
    common = {"attenuation_alpha_candidates": [0.0, 0.25, 0.5]}
    losses = {0.0: -0.05, 0.25: -0.03, 0.5: -0.01}
    base, candidates = selection_trials(losses, losses)
    table, selected = select_attenuation_alpha(base, candidates, common)
    assert selected is None
    assert not any(row["feasible"] for row in table)
    assert not any(row["selected"] for row in table)
