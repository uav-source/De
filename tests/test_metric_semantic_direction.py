import numpy as np

from eval.metric_semantics import METRIC_SEMANTICS, orient_risk_score


def test_frozen_metric_risk_directions_follow_formula_contracts():
    signs = {item.metric_name: item.risk_sign for item in METRIC_SEMANTICS}
    assert signs == {
        "ODI_trans": 1.0,
        "AIS_trans": -1.0,
        "lambda_min_trans": -1.0,
        "condition_number_trans": 1.0,
        "lambda_min_over_lambda_max": -1.0,
        "spectral_entropy_trans": -1.0,
        "effective_rank_trans": -1.0,
        "primary_eigengap": None,
        "primary_eigengap_ratio": None,
    }
    np.testing.assert_array_equal(
        orient_risk_score("lambda_min_trans", [1.0, 2.0]), [-1.0, -2.0]
    )


def test_eigengap_is_direction_identifiability_not_degeneracy_risk():
    rows = {item.metric_name: item for item in METRIC_SEMANTICS}
    assert rows["primary_eigengap_ratio"].formal_degeneracy_score is False
    assert rows["primary_eigengap_ratio"].contract_consistent is False
