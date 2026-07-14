def test_legacy_column_scaling_can_amplify_the_correction():
    alpha = 0.25
    prior_information = 1.0
    information = 1.0e6
    gradient = 2.0
    delta_full = -gradient / (prior_information + information)
    delta_old = -(alpha ** 0.5) * gradient / (prior_information + alpha * information)
    assert abs(delta_old) > abs(delta_full)


def test_legacy_formula_is_absent_from_active_update_source():
    from pathlib import Path

    source = (Path(__file__).parents[1] / "src/minibench/update_strategies.py").read_text()
    assert "operator.T @ H @ operator" not in source
    forbidden_helper = "selective_attenuation_" + "operator"
    assert forbidden_helper not in source
