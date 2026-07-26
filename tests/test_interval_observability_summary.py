from eval.interval_validity_audit import information_supports_label_invalidation


def test_absolute_and_shape_information_families_invalidate_reversed_label():
    structural = {
        "ODI_trans": 0.69,
        "AIS_trans": 3.57,
        "lambda_min_trans": 11.9,
        "condition_number_trans": 16.9,
        "lambda_min_over_lambda_max": 0.059,
        "spectral_entropy_trans": 0.48,
        "effective_rank_trans": 1.62,
    }
    control = {
        "ODI_trans": 0.81,
        "AIS_trans": 3.02,
        "lambda_min_trans": 3.70,
        "condition_number_trans": 52.6,
        "lambda_min_over_lambda_max": 0.019,
        "spectral_entropy_trans": 0.32,
        "effective_rank_trans": 1.37,
    }
    rows = []
    for label, values in (
        ("structural_degeneracy_candidate", structural),
        ("geometry_rich_control", control),
    ):
        rows.extend(
            {"interval_label": label, "metric": metric, "median": value}
            for metric, value in values.items()
        )
    invalidated, comparisons = information_supports_label_invalidation(rows)
    assert invalidated is True
    assert all(row["control_more_degenerate"] for row in comparisons)
