import math
from pathlib import Path

import pytest

from eval.stage2_failure_day12_axis_audit import audit_axis_contracts
from eval.stage2_failure_day12_figures import nonnegative_integer_limits
from eval.stage2_failure_day12_plot_data import build_all_plot_data, read_merged_rows
from eval.stage2_failure_day12_schema import padded_limits


ROOT = Path(__file__).resolve().parents[1]
MERGED = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2/replay_frame_diagnostics_merged.csv"


@pytest.mark.parametrize(
    ("values", "expected"),
    (([], (0, 1)), ([0, 0], (0, 1)), ([1, 2, 5], (0, 5)), ([1.2, 4.1], (0, 5))),
)
def test_nonnegative_integer_limits(values, expected):
    original = list(values)
    assert nonnegative_integer_limits(values) == expected
    assert values == original


def _audit():
    fields, merged = read_merged_rows(MERGED)
    return audit_axis_contracts(build_all_plot_data(fields, merged))


def test_figure3_and_figure4_run_axes_are_nonnegative_and_data_driven():
    audit = _audit()
    assert audit["axis_contract_comparison_count"] == 12
    assert audit["axis_contract_failure_count"] == 0
    assert audit["figure3_actual_run_max"] == 5.0
    assert (audit["figure3_ylim_lower"], audit["figure3_ylim_upper"]) == (0.0, 5.0)
    assert audit["figure4_run_row_actual_max"] == 5.0
    assert (
        audit["figure4_run_row_ylim_lower"], audit["figure4_run_row_ylim_upper"]
    ) == (0.0, 5.0)


def test_figure3_uses_current_run_and_figure4_continuous_ranges_are_unchanged():
    fields, merged = read_merged_rows(MERGED)
    data = build_all_plot_data(fields, merged)
    figure3 = data["day12_fig03_same_sign_run_timeline"]
    assert any(
        row["huber_current_same_sign_run_length"]
        != row["huber_max_same_sign_run_length"]
        for row in figure3
    )
    audit = audit_axis_contracts(data)
    records = audit["records"]
    for metric in (
        "abs_weak_innovation_z_huber", "abs_huber_window_mean",
        "abs_huber_cusum_signed",
    ):
        values = [
            float(row["metric_value"]) for row in data["day12_fig04_clean_stress_distributions"]
            if row["metric_name"] == metric and bool(row["included"])
            and math.isfinite(float(row["metric_value"]))
        ]
        expected = padded_limits(values)
        selected = [row for row in records if row["metric_name"] == metric]
        assert len(selected) == 2
        assert all(
            (row["expected_lower"], row["expected_upper"]) == expected
            for row in selected
        )
