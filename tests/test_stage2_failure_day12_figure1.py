from pathlib import Path
from eval.stage2_failure_day12_plot_data import build_all_plot_data, read_merged_rows

ROOT = Path(__file__).resolve().parents[1]
MERGED = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2/replay_frame_diagnostics_merged.csv"


def test_figure1_contains_all_cases_and_required_signals():
    fields, merged = read_merged_rows(MERGED)
    rows = build_all_plot_data(fields, merged)["day12_fig01_innovation_timeline"]
    assert len({row["case_id"] for row in rows}) == 8
    assert all("weak_innovation_z_huber" in row and "huber_window_mean" in row for row in rows)
