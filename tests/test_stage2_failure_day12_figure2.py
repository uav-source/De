from pathlib import Path
from eval.stage2_failure_day12_plot_data import build_all_plot_data, read_merged_rows

ROOT = Path(__file__).resolve().parents[1]
MERGED = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2/replay_frame_diagnostics_merged.csv"


def test_figure2_preserves_prior_and_posterior_fields():
    fields, merged = read_merged_rows(MERGED)
    rows = build_all_plot_data(fields, merged)["day12_fig02_prior_posterior_axis_error"]
    source = {(row["case_id"], row["frame_index"]): row for row in merged}
    first = rows[0]
    original = source[(first["case_id"], first["frame_index"])]
    assert first["prior_axis_error_abs_m"] == original["prior_axis_error_abs_m"]
    assert first["posterior_axis_error_abs_m"] == original["posterior_axis_error_abs_m"]
