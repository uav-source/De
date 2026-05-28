import math
from pathlib import Path

import numpy as np

import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.stats import (  # noqa: E402
    bootstrap_ci_corr,
    leave_one_sequence_out_correlation,
    make_high_axis_drift_flag,
    pearson_corr,
    rank_metrics_by_correlation,
    safe_auc_if_binary_available,
    spearman_corr,
)


def test_spearman_corr_monotonic_data_is_near_one():
    rho, p_value = spearman_corr([1, 2, 3, 4, 5], [10, 20, 30, 40, 50])

    assert rho > 0.999
    assert p_value <= 0.05


def test_constant_inputs_return_nan_instead_of_crashing():
    rho, p_value = spearman_corr([1, 1, 1, 1], [0, 1, 2, 3])
    pearson = pearson_corr([0, 1, 2, 3], [2, 2, 2, 2])

    assert math.isnan(rho)
    assert math.isnan(p_value)
    assert math.isnan(pearson)


def test_bootstrap_ci_corr_orders_bounds():
    low, high = bootstrap_ci_corr([1, 2, 3, 4, 5, 6], [1, 2, 2, 4, 5, 7], n_boot=50, random_seed=7)

    assert np.isfinite(low)
    assert np.isfinite(high)
    assert low <= high


def test_high_axis_drift_flag_uses_global_75th_percentile():
    flags = make_high_axis_drift_flag([0.0, 1.0, 2.0, 3.0])

    assert np.array_equal(flags, np.array([0, 0, 0, 1]))


def test_auc_for_binary_labels_is_finite_when_available():
    auc = safe_auc_if_binary_available([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1])

    assert auc == 1.0


def test_ranking_does_not_treat_nan_as_best():
    rows = [
        {"metric_name": "nan_metric", "target_name": "axis_drift_rate", "spearman_rho": float("nan")},
        {"metric_name": "weak_metric", "target_name": "axis_drift_rate", "spearman_rho": 0.2},
        {"metric_name": "strong_metric", "target_name": "axis_drift_rate", "spearman_rho": -0.8},
    ]

    ranked = rank_metrics_by_correlation(rows, "axis_drift_rate")

    assert ranked[0]["metric_name"] == "strong_metric"
    assert ranked[-1]["metric_name"] == "nan_metric"


def test_leave_one_sequence_out_handles_small_or_constant_sequences():
    rows = [
        {"sequence_id": "A", "ODI": 1.0, "axis_drift_rate": 0.0},
        {"sequence_id": "A", "ODI": 1.0, "axis_drift_rate": 1.0},
        {"sequence_id": "B", "ODI": 2.0, "axis_drift_rate": 2.0},
        {"sequence_id": "B", "ODI": 3.0, "axis_drift_rate": 3.0},
        {"sequence_id": "B", "ODI": 4.0, "axis_drift_rate": 4.0},
    ]

    loso = leave_one_sequence_out_correlation(rows, "ODI", "axis_drift_rate")

    assert len(loso) == 2
    held_a = next(row for row in loso if row["held_out_sequence"] == "A")
    held_b = next(row for row in loso if row["held_out_sequence"] == "B")
    assert held_a["valid_test_sample_count"] == 2
    assert math.isnan(held_a["test_spearman_rho_or_auc"])
    assert held_b["valid_train_sample_count"] == 2
    assert math.isnan(held_b["train_spearman_rho"])
