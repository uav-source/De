import pytest

from eval.measurement_real_analysis import binary_ranking_metrics
from eval.metric_semantics import auc_direction_rows


def _row(label, odi, entropy):
    return {
        "detector_valid": "True",
        "interval_label": label,
        "ODI_trans": odi,
        "AIS_trans": -odi,
        "lambda_min_trans": -odi,
        "condition_number_trans": odi,
        "lambda_min_over_lambda_max": -odi,
        "spectral_entropy_trans": entropy,
        "effective_rank_trans": entropy,
        "primary_eigengap": odi,
        "primary_eigengap_ratio": odi,
    }


def test_auc_uses_high_score_for_positive_class_without_automatic_reversal():
    result = binary_ranking_metrics([1, 1, 0, 0], [0.1, 0.2, 0.8, 0.9])
    assert result["auroc"] == 0.0
    rows = [
        _row("structural_degeneracy_candidate", 0.1, 0.9),
        _row("structural_degeneracy_candidate", 0.2, 0.8),
        _row("geometry_rich_control", 0.8, 0.2),
        _row("geometry_rich_control", 0.9, 0.1),
    ]
    odi = next(row for row in auc_direction_rows(rows) if row["metric_name"] == "ODI_trans")
    assert odi["AUC_semantically_oriented"] == 0.0
    assert odi["AUC_reversed_diagnostic"] == 1.0
    assert odi["reversed_is_formal_result"] is False
    assert odi["PR_AUC_semantically_oriented"] == pytest.approx(5.0 / 12.0)
